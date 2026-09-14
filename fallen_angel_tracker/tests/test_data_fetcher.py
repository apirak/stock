"""data_fetcher.py — pure helpers + fetch_snapshot against a fake yfinance Ticker.

No network: `yf.Ticker` is monkeypatched to a FakeTicker serving small
pandas DataFrames, mirroring yfinance's newest-column-first statement layout.
"""
from __future__ import annotations

import pandas as pd
import pytest

import config
import data_fetcher
from data_fetcher import FinancialSnapshot, _latest, _num, _ratio_series, _return_over


# ---------------------------------------------------------------------------
# chart URLs / links
# ---------------------------------------------------------------------------

def test_chart_urls_cover_three_sites():
    urls = data_fetcher.chart_urls("unh")
    assert urls["TradingView"] == "https://www.tradingview.com/chart/?symbol=UNH"
    assert urls["Yahoo Finance"] == "https://finance.yahoo.com/quote/UNH"
    assert urls["StockAnalysis"] == "https://stockanalysis.com/stocks/unh/"


def test_chart_links_md_renders_markdown_row():
    md = data_fetcher.chart_links_md("TGT")
    assert md == (
        "[TradingView](https://www.tradingview.com/chart/?symbol=TGT) · "
        "[Yahoo Finance](https://finance.yahoo.com/quote/TGT) · "
        "[StockAnalysis](https://stockanalysis.com/stocks/tgt/)"
    )


# ---------------------------------------------------------------------------
# FinancialSnapshot
# ---------------------------------------------------------------------------

def test_discount_property(make_snapshot):
    assert make_snapshot().discount == pytest.approx(0.20)


def test_discount_none_when_price_or_fair_value_missing(make_snapshot):
    assert make_snapshot(price=None).discount is None
    assert make_snapshot(fair_value=None).discount is None
    assert make_snapshot(fair_value=0).discount is None


def test_to_prompt_dict_converts_fractions_to_percent(make_snapshot):
    d = make_snapshot().to_prompt_dict()
    assert d["gross_margin_pct"] == 60.0
    assert d["discount_pct"] == 20.0
    assert d["net_debt_to_ebitda"] == 1.5          # ratios stay raw
    assert d["gross_margin_history_pct"] == [60.0, 59.0, 61.0]


def test_to_prompt_dict_filters_none_from_histories(make_snapshot):
    snap = make_snapshot(gross_margin_history=[0.6, None, 0.58], return_1m=None)
    d = snap.to_prompt_dict()
    assert d["gross_margin_history_pct"] == [60.0, 58.0]
    assert d["return_1m_pct"] is None


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------

def test_num_handles_none_nan_and_garbage():
    assert _num(None) is None
    assert _num(float("nan")) is None
    assert _num("12.5") == 12.5
    assert _num("abc") is None
    assert _num([1, 2]) is None


def test_latest_takes_newest_column():
    df = pd.DataFrame({"FY2025": [100, 90], "FY2024": [80, 70]},
                      index=["Total Revenue", "Gross Profit"])
    assert _latest(df, "Total Revenue") == 100


def test_latest_returns_none_for_missing_row_or_empty():
    df = pd.DataFrame({"A": [1]}, index=["X"])
    assert _latest(df, "Missing") is None
    assert _latest(pd.DataFrame(), "X") is None
    assert _latest(None, "X") is None


def test_latest_skips_non_numeric_values():
    df = pd.DataFrame([["bad", 42]], index=["X"], columns=["FY2025", "FY2024"])
    assert _latest(df, "X") == 42


def test_ratio_series_skips_zero_and_nan_denominators():
    df = pd.DataFrame(
        [[300, None, 600, 300], [100, 50, 1000, 0]],
        index=["Gross Profit", "Total Revenue"],
        columns=["FY4", "FY3", "FY2", "FY1"],   # newest first
    )
    # FY3 skipped (nan numerator), FY1 skipped (zero denominator)
    assert _ratio_series(df, "Gross Profit", "Total Revenue") == [3.0, 0.6]


def test_ratio_series_respects_limit():
    df = pd.DataFrame([[1, 1, 1, 1, 1], [2, 2, 2, 2, 2]],
                      index=["N", "D"], columns=list("abcde"))
    assert _ratio_series(df, "N", "D", limit=2) == [0.5, 0.5]


def test_return_over_basic_and_edge_cases():
    closes = pd.Series([100.0, 110.0, 90.0, 120.0])  # len 4
    assert _return_over(closes, 3) == pytest.approx(0.20)  # 120 vs base 100
    assert _return_over(closes, 4) is None           # not enough history
    assert _return_over(None, 3) is None
    assert _return_over(pd.Series([0.0, 1.0]), 1) is None  # base <= 0


# ---------------------------------------------------------------------------
# FakeTicker + fetch_snapshot
# ---------------------------------------------------------------------------

def _income_df():
    return pd.DataFrame(
        [
            [1000.0, 900.0],   # Total Revenue
            [600.0, 522.0],    # Gross Profit
            [200.0, 171.0],    # Operating Income
            [20.0, 18.0],      # Interest Expense
            [150.0, 130.0],    # Pretax Income
            [30.0, 26.0],      # Tax Provision
            [300.0, 280.0],    # EBITDA
        ],
        index=["Total Revenue", "Gross Profit", "Operating Income",
               "Interest Expense", "Pretax Income", "Tax Provision", "EBITDA"],
        columns=["FY2025", "FY2024"],   # newest first, like yfinance
    )


def _balance_df():
    return pd.DataFrame(
        [[800.0], [400.0], [100.0], [50.0]],
        index=["Stockholders Equity", "Total Debt",
               "Cash And Cash Equivalents", "Other Short Term Investments"],
        columns=["FY2025"],
    )


def _cashflow_df():
    return pd.DataFrame(
        [[250.0], [-80.0]],
        index=["Operating Cash Flow", "Capital Expenditure"],
        columns=["FY2025"],
    )


class FakeTicker:
    def __init__(self, info=None, income=None, balance=None, cashflow=None,
                 closes=None, news=None, info_error=False):
        self._info = info if info is not None else {}
        self.income_stmt = income
        self.balance_sheet = balance
        self.cashflow = cashflow
        self._closes = closes
        self._news = news
        self._info_error = info_error

    @property
    def info(self):
        if self._info_error:
            raise RuntimeError("yahoo exploded")
        return self._info

    def history(self, period=None):
        if self._closes is None:
            return pd.DataFrame()
        idx = pd.date_range("2026-01-01", periods=len(self._closes), freq="D")
        return pd.DataFrame({"Close": self._closes}, index=idx)

    def get_news(self, count=6):
        if isinstance(self._news, Exception):
            raise self._news
        return self._news or []


@pytest.fixture
def patch_ticker(monkeypatch):
    def _patch(fake):
        monkeypatch.setattr(data_fetcher.yf, "Ticker", lambda tk: fake)
    return _patch


class TestFairValueHierarchy:
    def test_manual_override_wins(self, patch_ticker):
        patch_ticker(FakeTicker(info={"targetMeanPrice": 120.0}))
        snap = data_fetcher.fetch_snapshot("TEST", fair_value_override=123.0)
        assert snap.fair_value == 123.0
        assert snap.fair_value_source == "manual_override"

    def test_analyst_target_mean_second(self, patch_ticker):
        patch_ticker(FakeTicker(info={"targetMeanPrice": 120.0, "forwardEps": 5.0}))
        snap = data_fetcher.fetch_snapshot("TEST")
        assert snap.fair_value == 120.0
        assert snap.fair_value_source == "analyst_target_mean"

    def test_earnings_based_estimate_last(self, patch_ticker):
        patch_ticker(FakeTicker(info={"forwardEps": 5.0, "forwardPE": 20.0}))
        snap = data_fetcher.fetch_snapshot("TEST")
        assert snap.fair_value == 100.0
        assert snap.fair_value_source == "earnings_based_estimate"

    def test_earnings_estimate_floors_pe_at_fallback(self, patch_ticker):
        patch_ticker(FakeTicker(info={"forwardEps": 5.0, "forwardPE": 8.0}))
        snap = data_fetcher.fetch_snapshot("TEST")
        assert snap.fair_value == 5.0 * config.FALLBACK_JUSTIFIED_PE

    def test_no_fair_value_possible_appends_warning(self, patch_ticker):
        patch_ticker(FakeTicker(info={}))
        snap = data_fetcher.fetch_snapshot("TEST")
        assert snap.fair_value is None
        assert "fair value could not be estimated" in snap.warnings


class TestFetchSnapshot:
    def test_full_snapshot_computes_all_ratios(self, patch_ticker):
        info = {
            "longName": "Test Corp", "currentPrice": 80.0, "marketCap": 2000.0,
            "beta": 1.2, "ebitda": 300.0, "targetMeanPrice": 120.0,
        }
        closes = [100.0 + i for i in range(200)]        # slow uptrend
        patch_ticker(FakeTicker(info=info, income=_income_df(), balance=_balance_df(),
                                cashflow=_cashflow_df(), closes=closes,
                                news=[{"content": {"title": "Headline A"}},
                                      {"title": "Headline B"},
                                      "not-a-dict",
                                      {"content": {}}]))
        snap = data_fetcher.fetch_snapshot("TEST")

        assert snap.company == "Test Corp"
        assert snap.price == 80.0
        assert snap.warnings == []

        # margins from income statement (newest year first)
        assert snap.gross_margin == pytest.approx(0.60)
        assert snap.operating_margin == pytest.approx(0.20)
        assert snap.gross_margin_history == pytest.approx([0.60, 0.58])
        assert snap.operating_margin_history == pytest.approx([0.20, 0.19])

        # effective tax rate 30/150 = 0.2 -> ROIC = 200*0.8 / (400+800-100-50)
        assert snap.roic == pytest.approx(160.0 / 1050.0)

        # WACC from weights: equity 2000 / debt 400, cost of debt = 20/400
        coe = config.RISK_FREE_RATE + 1.2 * config.EQUITY_RISK_PREMIUM
        cod = min(20.0 / 400.0, 0.15)
        we = 2000.0 / 2400.0
        tax = 0.2
        assert snap.wacc == pytest.approx(we * coe + (1 - we) * cod * (1 - tax))

        assert snap.net_debt_ebitda == pytest.approx((400 - 100 - 50) / 300)
        assert snap.interest_coverage == pytest.approx(200.0 / 20.0)
        assert snap.interest_expense_negligible is False

        # FCF = OCF + (negative) capex
        assert snap.fcf == pytest.approx(170.0)
        assert snap.fcf_yield == pytest.approx(170.0 / 2000.0)

        assert snap.return_1m == pytest.approx(closes[-1] / closes[-22] - 1)
        assert snap.return_3m == pytest.approx(closes[-1] / closes[-64] - 1)
        assert snap.return_6m == pytest.approx(closes[-1] / closes[-127] - 1)

        assert snap.news_headlines == ["Headline A", "Headline B"]

    def test_info_failure_degrades_without_raising(self, patch_ticker):
        patch_ticker(FakeTicker(info_error=True, closes=[10.0, 11.0, 12.0]))
        snap = data_fetcher.fetch_snapshot("TEST")
        assert snap.company == "TEST"                     # falls back to ticker
        assert snap.price == 12.0                         # from 1mo close history
        assert any("info unavailable" in w for w in snap.warnings)

    def test_news_fetch_failure_is_swallowed(self, patch_ticker):
        patch_ticker(FakeTicker(info={"currentPrice": 5.0}, news=RuntimeError("rss down")))
        snap = data_fetcher.fetch_snapshot("TEST")
        assert snap.news_headlines == []

    def test_include_news_false_skips_news(self, patch_ticker):
        patch_ticker(FakeTicker(info={"currentPrice": 5.0},
                                news=[{"content": {"title": "ignored"}}]))
        snap = data_fetcher.fetch_snapshot("TEST", include_news=False)
        assert snap.news_headlines == []

    def test_negligible_interest_expense_flag(self, patch_ticker):
        income = pd.DataFrame([[1000.0], [200.0], [0.0]],
                              index=["Total Revenue", "Operating Income", "Interest Expense"],
                              columns=["FY2025"])
        patch_ticker(FakeTicker(info={"currentPrice": 5.0}, income=income))
        snap = data_fetcher.fetch_snapshot("TEST")
        assert snap.interest_expense_negligible is True
        assert snap.interest_coverage is None


class TestFetchPriceStats:
    def test_price_and_returns_from_history(self, patch_ticker):
        closes = [100.0 + i for i in range(200)]
        patch_ticker(FakeTicker(closes=closes))
        stats = data_fetcher.fetch_price_stats("TEST")
        assert stats["price"] == pytest.approx(closes[-1])
        assert stats["return_1m"] == pytest.approx(closes[-1] / closes[-22] - 1)
        assert stats["return_6m"] == pytest.approx(closes[-1] / closes[-127] - 1)

    def test_no_history_gives_none_everywhere(self, patch_ticker):
        patch_ticker(FakeTicker())
        stats = data_fetcher.fetch_price_stats("TEST")
        assert stats == {"price": None, "return_1m": None,
                         "return_3m": None, "return_6m": None}
