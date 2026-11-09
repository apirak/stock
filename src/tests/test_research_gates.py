"""Regression checks for evidence quality and the research/buy distinction."""
import analyzer


def test_weekly_excludes_fail_watch_and_missing_balance_data(make_row):
    for fields in (
        {"Moat Impairment Verdict": analyzer.VERDICT_FAIL},
        {"Moat Impairment Verdict": analyzer.VERDICT_WATCH},
        {"Interest Coverage Ratio": ""},
        {"Net Debt / EBITDA": ""},
        {"Data Warnings": "currency mismatch"},
        {"ROIC (%)": "691.73", "FCF Yield (%)": "64.87"},
        {"ROIC (%)": "nan"},
        {"Analysis Status": "Pending"},
        {"Analysis Status": ""},
    ):
        assert analyzer.select_top_picks([make_row(**fields)]) == []


def test_proxy_discount_never_becomes_buy_action(make_snapshot, make_row):
    snap = make_snapshot(fair_value_source="analyst_target_mean")
    assert analyzer.strategic_action(analyzer.VERDICT_PASS, snap) != analyzer.ACTION_ACCUMULATE
    assert analyzer.action_from_row(analyzer.VERDICT_PASS, make_row()) != analyzer.ACTION_ACCUMULATE


def test_missing_metrics_cannot_pass_daily_screen(make_snapshot):
    for field in ("net_debt_ebitda", "interest_coverage", "roic", "fcf_yield"):
        verdict, _ = analyzer.heuristic_verdict(make_snapshot(**{field: None}))
        assert verdict == analyzer.VERDICT_WATCH


def test_negligible_interest_is_explicit_exception(make_row):
    row = make_row(**{"Interest Coverage Ratio": "", "Interest Expense Negligible": "true"})
    assert analyzer.select_top_picks([row])[0]["Ticker"] == "TEST"


def test_legacy_rows_without_metadata_are_not_candidates(make_row):
    row = make_row()
    for key in ("Valuation Source", "Financial Period", "Quarterly Period", "News Status"):
        row.pop(key)
    assert analyzer.select_top_picks([row]) == []
