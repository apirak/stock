"""analyzer.py — deterministic screening rules and row building (no LLM paths)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import analyzer
import config


# ---------------------------------------------------------------------------
# balance_sheet_flags
# ---------------------------------------------------------------------------

def test_clean_snapshot_has_no_flags(make_snapshot):
    assert analyzer.balance_sheet_flags(make_snapshot()) == []


def test_high_leverage_flagged(make_snapshot):
    flags = analyzer.balance_sheet_flags(make_snapshot(net_debt_ebitda=4.0))
    assert any("Net Debt/EBITDA 4.0x > 3x" in f for f in flags)


def test_negative_fcf_without_leverage_data_flagged(make_snapshot):
    flags = analyzer.balance_sheet_flags(
        make_snapshot(fcf=-100.0, net_debt_ebitda=None))
    assert "leverage unknown and FCF negative" in flags
    assert "FCF <= 0" in flags


def test_weak_interest_coverage_flagged(make_snapshot):
    flags = analyzer.balance_sheet_flags(make_snapshot(interest_coverage=3.0))
    assert any("Interest coverage 3.0x < 5x" in f for f in flags)


def test_negligible_interest_expense_skips_coverage_check(make_snapshot):
    flags = analyzer.balance_sheet_flags(
        make_snapshot(interest_coverage=None, interest_expense_negligible=True))
    assert not any("Interest coverage" in f for f in flags)


def test_thin_fcf_yield_flagged(make_snapshot):
    flags = analyzer.balance_sheet_flags(make_snapshot(fcf_yield=0.01))
    assert any("FCF yield 1.0%" in f for f in flags)


def test_roic_below_wacc_flagged(make_snapshot):
    flags = analyzer.balance_sheet_flags(make_snapshot(roic=0.05, wacc=0.08))
    assert any("ROIC 5.0% below WACC 8.0%" in f for f in flags)


# ---------------------------------------------------------------------------
# margin_trend
# ---------------------------------------------------------------------------

def test_margin_trend_stable_within_band(make_snapshot):
    assert analyzer.margin_trend(make_snapshot(gross_margin_history=[0.60, 0.61])) == "stable"


def test_margin_trend_unknown_without_history(make_snapshot):
    assert analyzer.margin_trend(make_snapshot(gross_margin_history=[])) == "unknown"
    assert analyzer.margin_trend(make_snapshot(gross_margin_history=[0.5])) == "unknown"


def test_margin_trend_ignores_none_entries(make_snapshot):
    assert analyzer.margin_trend(
        make_snapshot(gross_margin_history=[0.61, None, 0.60])) == "stable"


# gross_margin_history is newest-first, so delta = newest - oldest.
# Falling margins (delta < -0.03) must be "eroding", rising "improving".
def test_margin_trend_falling_margins_are_eroding(make_snapshot):
    assert analyzer.margin_trend(
        make_snapshot(gross_margin_history=[0.50, 0.60])) == "eroding"


def test_margin_trend_rising_margins_are_improving(make_snapshot):
    assert analyzer.margin_trend(
        make_snapshot(gross_margin_history=[0.60, 0.50])) == "improving"


# ---------------------------------------------------------------------------
# heuristic_verdict / strategic_action
# ---------------------------------------------------------------------------

def test_clean_snapshot_with_discount_passes(make_snapshot):
    verdict, reasons = analyzer.heuristic_verdict(make_snapshot())
    assert verdict == analyzer.VERDICT_PASS
    assert any("clean balance sheet" in r for r in reasons)


def test_eroding_margins_block_pass_verdict(make_snapshot):
    # regression guard for the margin_trend label swap: a clean balance sheet
    # with collapsing gross margins must downgrade Pass -> Watch
    snap = make_snapshot(gross_margin_history=[0.45, 0.60])   # newest much lower
    assert analyzer.margin_trend(snap) == "eroding"
    verdict, _ = analyzer.heuristic_verdict(snap)
    assert verdict == analyzer.VERDICT_WATCH


@pytest.mark.parametrize("field,overrides", [
    ("coverage", {"interest_coverage": 1.5}),
    ("leverage", {"net_debt_ebitda": 5.5}),
    ("fcf_and_leverage", {"fcf": -100.0, "net_debt_ebitda": 3.5}),
])
def test_danger_zone_hard_fails(make_snapshot, field, overrides):
    verdict, reasons = analyzer.heuristic_verdict(make_snapshot(**overrides))
    assert verdict == analyzer.VERDICT_FAIL
    assert reasons  # always explains why


def test_flags_with_discount_becomes_watch(make_snapshot):
    verdict, reasons = analyzer.heuristic_verdict(make_snapshot(net_debt_ebitda=4.0))
    assert verdict == analyzer.VERDICT_WATCH
    assert any("flags present" in r for r in reasons)


def test_no_discount_becomes_watch(make_snapshot):
    verdict, reasons = analyzer.heuristic_verdict(make_snapshot(fair_value=None))
    assert verdict == analyzer.VERDICT_WATCH
    assert reasons == ["insufficient edge on current numbers"]


def test_strategic_action_matrix(make_snapshot):
    assert analyzer.strategic_action(analyzer.VERDICT_FAIL, make_snapshot()) == analyzer.ACTION_AVOID
    assert analyzer.strategic_action(analyzer.VERDICT_WATCH, make_snapshot()) == analyzer.ACTION_WAIT
    assert analyzer.strategic_action(
        analyzer.VERDICT_PASS, make_snapshot()) == analyzer.ACTION_ACCUMULATE
    assert analyzer.strategic_action(
        analyzer.VERDICT_PASS, make_snapshot(fair_value=None)) == analyzer.ACTION_WAIT
    assert analyzer.strategic_action(
        analyzer.VERDICT_PASS, make_snapshot(price=90.0)) == analyzer.ACTION_WAIT  # 10% < 15%


# ---------------------------------------------------------------------------
# analyze_ticker (rule-based row building)
# ---------------------------------------------------------------------------

def test_analyze_row_has_exactly_the_log_columns(make_snapshot):
    row = analyzer.analyze_ticker(make_snapshot())
    assert set(row) == set(analyzer.COLUMNS)


def test_analyze_row_pass_verdict_and_action(make_snapshot):
    row = analyzer.analyze_ticker(make_snapshot())
    assert row["Moat Impairment Verdict"] == analyzer.VERDICT_PASS
    assert row["Strategic Action"] == analyzer.ACTION_ACCUMULATE
    assert row["Suggested Position Cap (%)"] == config.POSITION_CAP_MIN
    assert "discount to fair value 20% with clean balance sheet" in row["Core Headwinds / Catalyst"]


def test_analyze_row_numeric_cells(make_snapshot):
    row = analyzer.analyze_ticker(make_snapshot())
    assert row["Market Price ($)"] == 80.0
    assert row["Fair Value ($)"] == 100.0
    assert row["Discount (%)"] == "20.00"
    assert row["Gross Margin (%)"] == "60.00"
    assert row["Net Debt / EBITDA"] == 1.5
    assert row["Interest Coverage Ratio"] == 12.0
    assert row["Date"] == "2026-09-14"
    assert row["Data Warnings"] == ""


def test_analyze_row_fail_verdict_propagates(make_snapshot):
    snap = make_snapshot(interest_coverage=1.2)
    row = analyzer.analyze_ticker(snap)
    assert row["Moat Impairment Verdict"] == analyzer.VERDICT_FAIL
    assert row["Strategic Action"] == analyzer.ACTION_AVOID


def test_analyze_row_missing_metrics_become_empty_cells(make_snapshot):
    snap = make_snapshot(gross_margin=None, wacc=None, net_debt_ebitda=None,
                         interest_coverage=None, fcf_yield=None,
                         fair_value=None, price=None,
                         warnings=["fair value could not be estimated"])
    row = analyzer.analyze_ticker(snap)
    assert row["Gross Margin (%)"] == ""
    assert row["WACC (%)"] == ""
    assert row["Market Price ($)"] == ""
    assert "fair value could not be estimated" in row["Data Warnings"]


def test_analyze_row_pending_note_mentions_finalize(make_snapshot):
    row = analyzer.analyze_ticker(make_snapshot())
    assert "deep-dive pending" in row["Deep-Dive"]
    assert "finalize" in row["Deep-Dive"]


# ---------------------------------------------------------------------------
# pending_entry / action_from_row
# ---------------------------------------------------------------------------

def test_pending_entry_carries_task_and_rule_verdict(make_snapshot):
    row = analyzer.analyze_ticker(make_snapshot())
    entry = analyzer.pending_entry(make_snapshot(), row)
    assert entry["ticker"] == "TEST"
    assert "Moat Impairment Test" in entry["task"]
    assert entry["rule_based_verdict"] == analyzer.VERDICT_PASS
    assert isinstance(entry["rule_based_flags"], list)


def test_action_from_row_uses_discount_cell(make_row):
    assert analyzer.action_from_row(
        analyzer.VERDICT_FAIL, make_row()) == analyzer.ACTION_AVOID
    assert analyzer.action_from_row(
        analyzer.VERDICT_WATCH, make_row()) == analyzer.ACTION_WAIT
    assert analyzer.action_from_row(
        analyzer.VERDICT_PASS, make_row()) == analyzer.ACTION_ACCUMULATE
    assert analyzer.action_from_row(
        analyzer.VERDICT_PASS, make_row(**{"Discount (%)": "5.00"})) == analyzer.ACTION_WAIT
    assert analyzer.action_from_row(
        analyzer.VERDICT_PASS, make_row(**{"Discount (%)": ""})) == analyzer.ACTION_WAIT


# ---------------------------------------------------------------------------
# weekly building blocks
# ---------------------------------------------------------------------------

class TestSelectTopPicks:
    def test_excludes_weak_balance_sheet_and_ranks(self, make_row):
        strong = make_row({"ticker": "STRNG"})                                     # Pass, clean
        watch_deep = make_row({"ticker": "WATCH", "price": 60.0},
                              **{"Moat Impairment Verdict": "Watch"})
        trap = make_row({"ticker": "TRAP", "interest_coverage": 1.2})              # coverage < 5

        picks = analyzer.select_top_picks([watch_deep, trap, strong], limit=2)
        assert [p["Ticker"] for p in picks] == ["STRNG", "WATCH"]
        assert "TRAP" not in [p["Ticker"] for p in picks]

    def test_limit_is_respected(self, make_row):
        rows = [make_row({"ticker": f"T{i}"}) for i in range(3)]
        assert len(analyzer.select_top_picks(rows, limit=2)) == 2

    def test_missing_numeric_cells_count_as_neutral(self, make_row):
        blank = make_row(**{"Interest Coverage Ratio": "", "Net Debt / EBITDA": "",
                            "Discount (%)": "", "FCF Yield (%)": "", "ROIC (%)": ""})
        picks = analyzer.select_top_picks([blank], limit=1)
        assert picks == [blank]


def test_generate_mini_lesson_rotates_by_iso_week():
    topics = config.MINI_LESSON_TOPICS
    idx = datetime.now(timezone.utc).isocalendar()[1] % len(topics)
    lesson = analyzer.generate_mini_lesson()
    assert lesson["title"] == topics[idx]["title"]
    assert lesson["body"] == topics[idx]["brief"]


def test_fallback_tranche_plan_respects_config_bounds():
    plan = analyzer.fallback_tranche_plan()
    assert f"{config.FIRST_TRANCHE_MIN}-{config.FIRST_TRANCHE_MAX}%" in plan
