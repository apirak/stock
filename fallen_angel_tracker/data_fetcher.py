"""
Fetch prices, statement-derived ratios, historical returns and news headlines
from yfinance.

Fair value note: free data feeds do not publish Morningstar-style fair value,
so we use, in order of priority:
  1. A manual override (config.FAIR_VALUE_OVERRIDES, e.g. from Morningstar)
  2. The sell-side analyst target mean price (yfinance `targetMeanPrice`)
  3. An earnings-based estimate: forward EPS x a justified P/E multiple
All three are proxies — the discount% should be sanity-checked, not trusted blindly.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

import config

TRADING_DAYS = {"1m": 21, "3m": 63, "6m": 126}


@dataclass
class FinancialSnapshot:
    """Everything the analyzer needs about one company on one day."""

    ticker: str
    company: str = ""
    price: float | None = None
    fair_value: float | None = None
    fair_value_source: str = ""
    market_cap: float | None = None
    beta: float | None = None

    gross_margin: float | None = None            # fractions, e.g. 0.62
    operating_margin: float | None = None
    gross_margin_history: list[float] = field(default_factory=list)   # newest first
    operating_margin_history: list[float] = field(default_factory=list)

    roic: float | None = None
    wacc: float | None = None
    net_debt_ebitda: float | None = None
    interest_coverage: float | None = None
    interest_expense_negligible: bool = False
    fcf: float | None = None
    fcf_yield: float | None = None

    return_1m: float | None = None
    return_3m: float | None = None
    return_6m: float | None = None

    news_headlines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    as_of: str = field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    )

    @property
    def discount(self) -> float | None:
        if self.price is None or not self.fair_value:
            return None
        return (self.fair_value - self.price) / self.fair_value

    def to_prompt_dict(self) -> dict:
        """Compact JSON-safe view for the LLM prompt."""

        def pct(x):
            if x is None:
                return None
            if isinstance(x, (list, tuple)):
                return [round(v * 100, 2) for v in x if v is not None]
            return round(x * 100, 2)

        return {
            "ticker": self.ticker,
            "company": self.company,
            "price": self.price,
            "fair_value": self.fair_value,
            "fair_value_source": self.fair_value_source,
            "discount_pct": pct(self.discount),
            "gross_margin_pct": pct(self.gross_margin),
            "operating_margin_pct": pct(self.operating_margin),
            "gross_margin_history_pct": pct(self.gross_margin_history),
            "operating_margin_history_pct": pct(self.operating_margin_history),
            "roic_pct": pct(self.roic),
            "wacc_pct": pct(self.wacc),
            "net_debt_to_ebitda": self.net_debt_ebitda,
            "interest_coverage": self.interest_coverage,
            "interest_expense_negligible": self.interest_expense_negligible,
            "fcf_yield_pct": pct(self.fcf_yield),
            "return_1m_pct": pct(self.return_1m),
            "return_6m_pct": pct(self.return_6m),
            "recent_news_headlines": self.news_headlines,
            "data_warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Low-level helpers (defensive against yfinance's patchy data)
# ---------------------------------------------------------------------------

def _num(value) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest(df: pd.DataFrame | None, row: str) -> float | None:
    """Latest annual value of a statement row (columns run newest -> oldest)."""
    if df is None or df.empty or row not in df.index:
        return None
    series = pd.to_numeric(df.loc[row], errors="coerce").dropna()
    return _num(series.iloc[0]) if len(series) else None


def _ratio_series(df: pd.DataFrame | None, numerator: str, denominator: str,
                  limit: int = 4) -> list[float]:
    """Ratio per annual column, newest first; non-finite entries dropped."""
    if df is None or df.empty or numerator not in df.index or denominator not in df.index:
        return []
    out: list[float] = []
    num = pd.to_numeric(df.loc[numerator], errors="coerce")
    den = pd.to_numeric(df.loc[denominator], errors="coerce")
    for n, d in zip(num, den):
        if pd.isna(n) or pd.isna(d) or d == 0:
            continue
        out.append(float(n) / float(d))
        if len(out) >= limit:
            break
    return out


def _last_close(ticker: yf.Ticker) -> float | None:
    try:
        hist = ticker.history(period="1mo")
        if hist is not None and not hist.empty:
            return _num(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def _news_titles(ticker: yf.Ticker, limit: int = 6) -> list[str]:
    try:
        try:
            items = ticker.get_news(count=limit) or []
        except Exception:
            items = getattr(ticker, "news", []) or []
        titles: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            content = item.get("content") or {}
            title = content.get("title") or item.get("title")
            if title:
                titles.append(str(title))
        return titles[:limit]
    except Exception:
        return []


def _price_history(ticker: yf.Ticker) -> pd.Series | None:
    try:
        hist = ticker.history(period="8mo")
        if hist is None or hist.empty:
            return None
        return hist["Close"].dropna()
    except Exception:
        return None


def _return_over(closes: pd.Series | None, days: int) -> float | None:
    if closes is None or len(closes) <= days:
        return None
    base = float(closes.iloc[-1 - days])
    if base <= 0:
        return None
    return float(closes.iloc[-1]) / base - 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_snapshot(ticker: str, fair_value_override: float | None = None,
                   include_news: bool = True) -> FinancialSnapshot:
    """Build a FinancialSnapshot for one ticker. Missing pieces become None
    plus a warning; individual fetch failures never raise."""
    tk = ticker.upper()
    snap = FinancialSnapshot(ticker=tk)
    t = yf.Ticker(tk)

    try:
        info: dict = t.info or {}
    except Exception as exc:  # noqa: BLE001 - yfinance raises many shapes
        info = {}
        snap.warnings.append(f"info unavailable: {exc}")

    snap.company = info.get("longName") or info.get("shortName") or tk
    snap.price = (
        _num(info.get("currentPrice"))
        or _num(info.get("regularMarketPrice"))
        or _last_close(t)
    )
    snap.market_cap = _num(info.get("marketCap"))
    snap.beta = _num(info.get("beta"))

    # --- Fair value (proxy hierarchy) -----------------------------------
    if fair_value_override:
        snap.fair_value = float(fair_value_override)
        snap.fair_value_source = "manual_override"
    elif _num(info.get("targetMeanPrice")):
        snap.fair_value = _num(info.get("targetMeanPrice"))
        snap.fair_value_source = "analyst_target_mean"
    else:
        eps = _num(info.get("forwardEps")) or _num(info.get("trailingEps"))
        pe = _num(info.get("forwardPE")) or config.FALLBACK_JUSTIFIED_PE
        if eps and pe and eps > 0:
            snap.fair_value = eps * max(pe, config.FALLBACK_JUSTIFIED_PE)
            snap.fair_value_source = "earnings_based_estimate"
    if snap.fair_value is None:
        snap.warnings.append("fair value could not be estimated")

    # --- Statements -------------------------------------------------------
    try:
        income = t.income_stmt
    except Exception:
        income = None
    try:
        balance = t.balance_sheet
    except Exception:
        balance = None
    try:
        cashflow = t.cashflow
    except Exception:
        cashflow = None
    if income is None or (hasattr(income, "empty") and income.empty):
        snap.warnings.append("income statement unavailable")

    revenue = _latest(income, "Total Revenue")
    gross_profit = _latest(income, "Gross Profit")
    operating_income = _latest(income, "Operating Income")
    interest_expense = _latest(income, "Interest Expense")
    pretax_income = _latest(income, "Pretax Income")
    tax_provision = _latest(income, "Tax Provision")

    if revenue:
        snap.gross_margin_history = _ratio_series(income, "Gross Profit", "Total Revenue")
        snap.operating_margin_history = _ratio_series(income, "Operating Income", "Total Revenue")
        if gross_profit is not None:
            snap.gross_margin = gross_profit / revenue
        if operating_income is not None:
            snap.operating_margin = operating_income / revenue

    # --- Effective tax rate ----------------------------------------------
    tax_rate = config.FALLBACK_TAX_RATE
    if pretax_income and tax_provision is not None and pretax_income != 0:
        implied = tax_provision / pretax_income
        if 0.0 < implied < 0.6:
            tax_rate = implied

    # --- ROIC = NOPAT / Invested Capital ----------------------------------
    equity = (
        _latest(balance, "Stockholders Equity")
        or _latest(balance, "Total Equity Gross Minority Interest")
        or _num(info.get("stockholdersEquity"))
    )
    total_debt = (
        _latest(balance, "Total Debt")
        or _num(info.get("totalDebt"))
    )
    cash = _latest(balance, "Cash And Cash Equivalents")
    short_term_inv = _latest(balance, "Other Short Term Investments") or 0.0
    if operating_income and total_debt is not None and equity is not None:
        invested_capital = total_debt + equity - (cash or 0.0) - short_term_inv
        if invested_capital > 0:
            nopat = operating_income * (1 - tax_rate)
            snap.roic = nopat / invested_capital
        else:
            snap.warnings.append("invested capital not positive; ROIC skipped")

    # --- Simplified WACC ---------------------------------------------------
    cost_of_equity = config.RISK_FREE_RATE + (snap.beta or 1.0) * config.EQUITY_RISK_PREMIUM
    if total_debt and interest_expense and total_debt > 0:
        cost_of_debt = min(interest_expense / total_debt, 0.15)
    else:
        cost_of_debt = config.FALLBACK_COST_OF_DEBT
    equity_value = snap.market_cap or (
        snap.price * _num(info.get("sharesOutstanding")) if snap.price and info.get("sharesOutstanding") else None
    )
    if equity_value and total_debt is not None and (equity_value + total_debt) > 0:
        we = equity_value / (equity_value + total_debt)
        wd = 1 - we
        snap.wacc = we * cost_of_equity + wd * cost_of_debt * (1 - tax_rate)

    # --- Leverage & coverage ------------------------------------------------
    ebitda = _num(info.get("ebitda")) or _latest(income, "EBITDA")
    if total_debt is not None and ebitda:
        net_debt = total_debt - (cash or 0.0) - short_term_inv
        snap.net_debt_ebitda = net_debt / ebitda if ebitda > 0 else None
        if ebitda <= 0:
            snap.warnings.append("EBITDA <= 0; leverage ratio unavailable")
    if operating_income and interest_expense:
        snap.interest_coverage = operating_income / interest_expense if interest_expense > 0 else None
        if interest_expense <= 0:
            snap.interest_expense_negligible = True
    elif interest_expense is None or interest_expense <= 0:
        snap.interest_expense_negligible = True

    # --- Free cash flow -------------------------------------------------------
    ocf = _latest(cashflow, "Operating Cash Flow") or _num(info.get("operatingCashflow"))
    capex = _latest(cashflow, "Capital Expenditure")  # yfinance reports it negative
    if ocf is not None:
        snap.fcf = ocf + capex if (capex is not None and capex < 0) else (
            ocf - capex if capex is not None else ocf
        )
        if snap.market_cap:
            snap.fcf_yield = snap.fcf / snap.market_cap

    # --- Price history returns -------------------------------------------------
    closes = _price_history(t)
    snap.return_1m = _return_over(closes, TRADING_DAYS["1m"])
    snap.return_3m = _return_over(closes, TRADING_DAYS["3m"])
    snap.return_6m = _return_over(closes, TRADING_DAYS["6m"])

    if include_news:
        snap.news_headlines = _news_titles(t)

    return snap


def fetch_price_stats(ticker: str) -> dict:
    """Lightweight price + trailing returns; used by the weekly tracker."""
    t = yf.Ticker(ticker.upper())
    closes = _price_history(t)
    return {
        "price": float(closes.iloc[-1]) if closes is not None and len(closes) else None,
        "return_1m": _return_over(closes, TRADING_DAYS["1m"]),
        "return_3m": _return_over(closes, TRADING_DAYS["3m"]),
        "return_6m": _return_over(closes, TRADING_DAYS["6m"]),
    }
