"""
Analytical engine: deterministic screening rules + the file contract that
hands the qualitative analysis to the ZCode harness.

DESIGN DECISION (2026-09-15): this project intentionally contains NO LLM API
code. All narrative analysis (Moat Impairment Test, deep-dives, tranche plans,
mini-lessons) is performed by a ZCode automation session that reads the pending
file under data/pending/ and writes data/analysis/ (merged by
`python main.py --mode finalize`). See ai-node/README.md for the decision note
and ai-node/daily-prompt.md / ai-node/weekly-prompt.md for the automation
prompts.

The rule-based layer below is NOT an LLM — it is deterministic arithmetic on
the fetched financials. It always produces a first-pass verdict so the pipeline
works even before the harness analysis is merged.
"""
from __future__ import annotations

from datetime import datetime, timezone

import config
from data_fetcher import FinancialSnapshot

# Canonical verdict labels (stored verbatim in the log)
VERDICT_PASS = "Pass - Temporary"
VERDICT_WATCH = "Watch"
VERDICT_FAIL = "Fail - Value Trap"
VALID_VERDICTS = {VERDICT_PASS, VERDICT_WATCH, VERDICT_FAIL}

ACTION_ACCUMULATE = "Accumulate 1st Tranche"
ACTION_WAIT = "Wait for Next Earnings"
ACTION_AVOID = "Avoid"

# Daily_Log column schema (single source of truth, imported by storage/mailer)
COLUMNS = [
    "Date",
    "Ticker",
    "Company Name",
    "Market Price ($)",
    "Fair Value ($)",
    "Discount (%)",
    "Gross Margin (%)",
    "Operating Margin (%)",
    "ROIC (%)",
    "WACC (%)",
    "Net Debt / EBITDA",
    "Interest Coverage Ratio",
    "FCF Yield (%)",
    "Moat Impairment Verdict",
    "Core Headwinds / Catalyst",
    "Strategic Action",
    "Headwind Category",
    "Moat Sources",
    "Deep-Dive",
    "Tranche Plan",
    "Invalidation Criteria",
    "Suggested Position Cap (%)",
    "Data Warnings",
]


# ---------------------------------------------------------------------------
# Deterministic screening rules
# ---------------------------------------------------------------------------

def balance_sheet_flags(snap: FinancialSnapshot) -> list[str]:
    """Framework breaches from section 1 of the spec."""
    flags: list[str] = []
    if snap.net_debt_ebitda is not None:
        if snap.net_debt_ebitda > config.MAX_NET_DEBT_EBITDA:
            flags.append(f"Net Debt/EBITDA {snap.net_debt_ebitda:.1f}x > {config.MAX_NET_DEBT_EBITDA:.0f}x")
    elif snap.fcf is not None and snap.fcf < 0:
        flags.append("leverage unknown and FCF negative")
    if not snap.interest_expense_negligible and snap.interest_coverage is not None:
        if snap.interest_coverage < config.MIN_INTEREST_COVERAGE:
            flags.append(
                f"Interest coverage {snap.interest_coverage:.1f}x < {config.MIN_INTEREST_COVERAGE:.0f}x"
            )
    if snap.fcf is not None and snap.fcf <= 0:
        flags.append("FCF <= 0")
    elif snap.fcf_yield is not None and snap.fcf_yield < config.MIN_FCF_YIELD:
        flags.append(
            f"FCF yield {snap.fcf_yield:.1%} below healthy {config.MIN_FCF_YIELD:.0%} "
            "(cash flow positive but not strong)"
        )
    if snap.roic is not None and snap.wacc is not None and snap.roic < snap.wacc:
        flags.append(f"ROIC {snap.roic:.1%} below WACC {snap.wacc:.1%}")
    return flags


def margin_trend(snap: FinancialSnapshot) -> str:
    """'stable' | 'eroding' | 'improving' | 'unknown' from gross margin history."""
    hist = [m for m in snap.gross_margin_history if m is not None]
    if len(hist) < 2:
        return "unknown"
    delta = hist[0] - hist[-1]  # newest minus oldest
    if delta < -0.03:
        return "improving"
    if delta > 0.03:
        return "eroding"
    return "stable"


def heuristic_verdict(snap: FinancialSnapshot) -> tuple[str, list[str]]:
    """Rule-based classification — the first-pass verdict before the harness
    analysis is merged (and the standing verdict if no analysis arrives)."""
    flags = balance_sheet_flags(snap)
    reasons = list(flags)
    discount = snap.discount

    hard_fail = (
        (snap.interest_coverage is not None and snap.interest_coverage < 2.0)
        or (snap.net_debt_ebitda is not None and snap.net_debt_ebitda > 5.0)
        or (snap.fcf is not None and snap.fcf < 0 and (snap.net_debt_ebitda or 0) > 3.0)
    )
    if hard_fail:
        return VERDICT_FAIL, reasons or ["balance sheet in the danger zone"]
    if not flags and margin_trend(snap) != "eroding" and discount is not None \
            and discount >= config.MIN_DISCOUNT_FOR_BUY:
        reasons.append(f"discount to fair value {discount:.0%} with clean balance sheet")
        return VERDICT_PASS, reasons
    if discount is not None and discount >= config.MIN_DISCOUNT_FOR_BUY:
        reasons.append(f"discount {discount:.0%} but flags present")
    return VERDICT_WATCH, reasons or ["insufficient edge on current numbers"]


def strategic_action(verdict: str, snap: FinancialSnapshot) -> str:
    if verdict == VERDICT_FAIL:
        return ACTION_AVOID
    if verdict == VERDICT_WATCH:
        return ACTION_WAIT
    if snap.discount is None or snap.discount < config.MIN_DISCOUNT_FOR_BUY:
        return ACTION_WAIT
    return ACTION_ACCUMULATE


# ---------------------------------------------------------------------------
# Fallback narrative placeholders (replaced by the harness analysis at finalize)
# ---------------------------------------------------------------------------

def _fmt_pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "n/a"


def _fallback_deep_dive(snap: FinancialSnapshot, verdict: str, flags: list[str],
                        note: str) -> str:
    discount = snap.discount
    trend = margin_trend(snap)
    spread = (
        f"ROIC {_fmt_pct(snap.roic)} vs WACC {_fmt_pct(snap.wacc)}"
        if snap.roic is not None and snap.wacc is not None
        else "ROIC/WACC unavailable"
    )
    stance = {
        VERDICT_PASS: "The numbers support a temporary, not structural, impairment.",
        VERDICT_WATCH: "Signals are mixed; the discount is real but unproven.",
        VERDICT_FAIL: "Quantitative flags point toward structural impairment.",
    }[verdict]
    return (
        f"{snap.company} ({snap.ticker}) trades at {snap.price} vs an estimated fair value "
        f"of {snap.fair_value} ({_fmt_pct(discount)} discount, source: {snap.fair_value_source}). "
        f"Gross margin is {trend} at {_fmt_pct(snap.gross_margin)}, operating margin "
        f"{_fmt_pct(snap.operating_margin)}, {spread}, FCF yield {_fmt_pct(snap.fcf_yield)}. "
        f"Flags: {'; '.join(flags) if flags else 'none'}. {stance} {note}"
    )


def _fallback_tranche_plan() -> str:
    lo, hi = config.FIRST_TRANCHE_MIN, config.FIRST_TRANCHE_MAX
    return (
        f"Tranche 1: {lo}-{hi}% of intended full position to establish exposure. "
        f"Tranche 2: {lo+25}% after the next earnings report confirms stable margins. "
        f"Tranche 3: remainder only if ROIC stays above WACC and the discount persists."
    )


fallback_tranche_plan = _fallback_tranche_plan  # public alias for main.py finalize


def _fallback_invalidation(snap: FinancialSnapshot) -> list[str]:
    return [
        "Gross margin declines for 2 consecutive quarters (pricing power breaking)",
        "Net Debt/EBITDA rises above 4.0x or interest coverage falls below 3.0x",
        "A major customer segment publicly churns or switching-cost evidence reverses",
        "ROIC stays below WACC for 4 consecutive quarters",
    ]


def analyze_ticker(snap: FinancialSnapshot) -> dict:
    """Produce one Daily_Log row for a snapshot — rule-based only.

    Narrative fields are placeholders; a ZCode session replaces them when its
    analysis JSON is merged by `python main.py --mode finalize`.
    """
    verdict, reasons = heuristic_verdict(snap)
    flags = balance_sheet_flags(snap)
    action = strategic_action(verdict, snap)
    note = (
        f"(Data collected — deep-dive pending. A ZCode session should analyze "
        f"data/pending/daily-{snap.as_of}.json, then run `python main.py --mode finalize`.)"
    )
    invalidation = _fallback_invalidation(snap)

    def pct_cell(x: float | None) -> str:
        return f"{x * 100:.2f}" if x is not None else ""

    return {
        "Date": snap.as_of,
        "Ticker": snap.ticker,
        "Company Name": snap.company,
        "Market Price ($)": round(snap.price, 2) if snap.price is not None else "",
        "Fair Value ($)": round(snap.fair_value, 2) if snap.fair_value is not None else "",
        "Discount (%)": pct_cell(snap.discount),
        "Gross Margin (%)": pct_cell(snap.gross_margin),
        "Operating Margin (%)": pct_cell(snap.operating_margin),
        "ROIC (%)": pct_cell(snap.roic),
        "WACC (%)": pct_cell(snap.wacc),
        "Net Debt / EBITDA": (
            round(snap.net_debt_ebitda, 2) if snap.net_debt_ebitda is not None else ""
        ),
        "Interest Coverage Ratio": (
            round(snap.interest_coverage, 2) if snap.interest_coverage is not None else ""
        ),
        "FCF Yield (%)": pct_cell(snap.fcf_yield),
        "Moat Impairment Verdict": verdict,
        "Core Headwinds / Catalyst": "; ".join(reasons) or "n/a",
        "Strategic Action": action,
        "Headwind Category": "",
        "Moat Sources": "",
        "Deep-Dive": _fallback_deep_dive(snap, verdict, flags, note),
        "Tranche Plan": _fallback_tranche_plan(),
        "Invalidation Criteria": " | ".join(invalidation),
        "Suggested Position Cap (%)": config.POSITION_CAP_MIN,
        "Data Warnings": "; ".join(snap.warnings),
    }


def pending_entry(snap: FinancialSnapshot, row: dict) -> dict:
    """Payload written to data/pending/daily-<date>.json for the ZCode harness."""
    verdict, reasons = heuristic_verdict(snap)
    entry = snap.to_prompt_dict()
    entry.update({
        "rule_based_verdict": verdict,
        "rule_based_action": row.get("Strategic Action", ""),
        "rule_based_flags": reasons,
        "task": (
            "Run the Moat Impairment Test on this company: classify headwinds as "
            "'Transitory / Surface-level' vs 'Structural Damage', give a verdict "
            "(Pass - Temporary | Watch | Fail - Value Trap), and draft the strategic "
            "entry plan. Use only the facts in this file; do not invent numbers."
        ),
    })
    return entry


def action_from_row(verdict: str, row: dict) -> str:
    """Recompute the Strategic Action from CSV row values (used by finalize)."""
    if verdict == VERDICT_FAIL:
        return ACTION_AVOID
    if verdict == VERDICT_WATCH:
        return ACTION_WAIT
    discount = _row_float(row, "Discount (%)")
    if discount is None or discount / 100.0 < config.MIN_DISCOUNT_FOR_BUY:
        return ACTION_WAIT
    return ACTION_ACCUMULATE


# ---------------------------------------------------------------------------
# Weekly digest building blocks
# ---------------------------------------------------------------------------

def _row_float(row: dict, key: str) -> float | None:
    try:
        raw = row.get(key, "")
        return float(raw) if raw not in ("", None) else None
    except (TypeError, ValueError):
        return None


def select_top_picks(recent_rows: list[dict], limit: int = 2) -> list[dict]:
    """Pick Pass-verdict rows with the strongest balance sheets, best first."""
    candidates: list[tuple[float, dict]] = []
    for row in recent_rows:
        verdict = str(row.get("Moat Impairment Verdict", ""))
        coverage = _row_float(row, "Interest Coverage Ratio")
        leverage = _row_float(row, "Net Debt / EBITDA")
        balance_ok = (
            (coverage is None or coverage >= config.MIN_INTEREST_COVERAGE)
            and (leverage is None or leverage <= config.MAX_NET_DEBT_EBITDA)
        )
        if not balance_ok:
            continue
        discount = (_row_float(row, "Discount (%)") or 0.0) / 100.0
        fcf_yield = (_row_float(row, "FCF Yield (%)") or 0.0) / 100.0
        roic = (_row_float(row, "ROIC (%)") or 0.0) / 100.0
        score = discount * 200 + fcf_yield * 100 + roic * 50
        if leverage is not None:
            score -= leverage * 2
        tier = {VERDICT_PASS: 100, VERDICT_WATCH: 0}.get(verdict, -100)
        candidates.append((tier + score, row))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in candidates[:limit]]


def generate_mini_lesson() -> dict:
    """Rotating Buffett-style lesson seed (title + brief) from config.

    The ZCode harness expands this seed into the final Thai lesson for the
    weekly digest; the seed itself is the fallback when no analysis arrives.
    """
    week_index = datetime.now(timezone.utc).isocalendar()[1]
    topic = config.MINI_LESSON_TOPICS[week_index % len(config.MINI_LESSON_TOPICS)]
    return {"title": topic["title"], "body": topic["brief"]}
