"""
Analytical engine: deterministic screening rules + the file contract that
hands the qualitative analysis to the ZCode harness.

DESIGN DECISION (2026-09-15): this project intentionally contains NO LLM API
code. All narrative analysis (Moat Impairment Test, deep-dives, tranche plans,
mini-lessons) is performed by a ZCode automation session that reads the pending
file under src/data/pending/ and writes src/data/analysis/ (merged by
`python main.py --mode finalize`). The automation prompts live in
plan/stock.md + knowledge/falling_angle.md drive the analysis methodology.

The rule-based layer below is NOT an LLM — it is deterministic arithmetic on
the fetched financials. It always produces a first-pass verdict so the pipeline
works even before the harness analysis is merged.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math

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
ACTION_RESEARCH = "Research Further"

# Ranking used for drift detection: higher = healthier
VERDICT_RANK = {VERDICT_PASS: 2, VERDICT_WATCH: 1, VERDICT_FAIL: 0}

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
    "Valuation Source",
    "Financial Period",
    "Quarterly Period",
    "News Status",
    "Interest Expense Negligible",
    "Valuation Status",
    "Portfolio Fit",
    "Quote Currency",
    "Financial Currency",
    "Analysis Status",
]


# ---------------------------------------------------------------------------
# Deterministic screening rules
# ---------------------------------------------------------------------------

def data_quality_flags(snap: FinancialSnapshot) -> list[str]:
    """Missing/implausible evidence blocks a positive screen, not just prose."""
    flags = list(snap.warnings)
    if not snap.quote_currency or snap.quote_currency != snap.financial_currency:
        flags.append("quote/financial currencies must match before comparing ratios")
    if snap.news_status != "ok":
        flags.append("news coverage unverified")
    for name, value, max_age in (("annual period", snap.financial_period, 550),
                                 ("quarterly period", snap.quarterly_periods[0] if snap.quarterly_periods else "", 180)):
        try:
            age = (datetime.fromisoformat(snap.as_of).date() - datetime.fromisoformat(value).date()).days
            if age < 0 or age > max_age:
                flags.append(f"{name} stale or in future")
        except ValueError:
            flags.append(f"{name} unknown")
    for name in ("price", "gross_margin", "operating_margin", "roic", "wacc", "net_debt_ebitda", "fcf_yield"):
        value = getattr(snap, name)
        if value is None or not math.isfinite(value):
            flags.append(f"{name} unavailable or non-finite")
    if not snap.interest_expense_negligible and (snap.interest_coverage is None or not math.isfinite(snap.interest_coverage)):
        flags.append("interest coverage unknown (not confirmed negligible)")
    # ponytail: broad sanity bounds flag unusual businesses for manual validation, not a value-trap verdict.
    if snap.roic is not None and abs(snap.roic) > 1:
        flags.append("ROIC outside sanity range; verify invested capital")
    if snap.fcf_yield is not None and abs(snap.fcf_yield) > 0.30:
        flags.append("FCF yield outside sanity range; verify currency and period")
    return flags

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
        return "eroding"
    if delta > 0.03:
        return "improving"
    return "stable"


def heuristic_verdict(snap: FinancialSnapshot) -> tuple[str, list[str]]:
    """Rule-based classification — the first-pass verdict before the harness
    analysis is merged (and the standing verdict if no analysis arrives)."""
    flags = balance_sheet_flags(snap)
    reasons = list(flags)
    discount = snap.discount
    quality_flags = data_quality_flags(snap)
    if quality_flags:
        return VERDICT_WATCH, reasons + quality_flags

    hard_fail = (
        (snap.interest_coverage is not None and snap.interest_coverage < 2.0)
        or (snap.net_debt_ebitda is not None and snap.net_debt_ebitda > 5.0)
        or (snap.fcf is not None and snap.fcf < 0 and (snap.net_debt_ebitda or 0) > 3.0)
    )
    if hard_fail:
        return VERDICT_FAIL, reasons or ["balance sheet in the danger zone"]
    if not flags and margin_trend(snap) in ("stable", "improving") and discount is not None \
            and discount >= config.MIN_DISCOUNT_FOR_BUY:
        reasons.append(f"discount to fair value {discount:.0%} with clean balance sheet")
        return VERDICT_PASS, reasons
    if discount is not None and discount >= config.MIN_DISCOUNT_FOR_BUY:
        reasons.append(f"discount {discount:.0%} but flags present")
    return VERDICT_WATCH, reasons or ["insufficient edge on current numbers"]


def verdict_drift(history_rows: list[dict], latest_verdict: str) -> str:
    """Compare the latest verdict against the best verdict earlier in history.

    Returns '🔼 Upgrade' (e.g. Watch -> Pass), '🔽 Downgrade' (e.g. Pass -> Watch),
    or '' when unchanged/unknown. Feeds the weekly tracking table — possible
    only because daily runs accumulate verdict history in the CSV.
    """
    cur = VERDICT_RANK.get(str(latest_verdict).strip(), 1)
    if not history_rows:
        return ""
    best = max(
        VERDICT_RANK.get(str(r.get("Moat Impairment Verdict", "")).strip(), cur)
        for r in history_rows
    )
    if cur > best:
        return "🔼 Upgrade"
    if cur < best:
        return "🔽 Downgrade"
    return ""


def strategic_action(verdict: str, snap: FinancialSnapshot) -> str:
    if verdict == VERDICT_FAIL:
        return ACTION_AVOID
    if verdict == VERDICT_WATCH:
        return ACTION_WAIT
    if snap.discount is None or snap.discount < config.MIN_DISCOUNT_FOR_BUY:
        return ACTION_WAIT
    return ACTION_RESEARCH


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
        VERDICT_PASS: "Quantitative screen passed; temporary impairment and moat still need source verification.",
        VERDICT_WATCH: "Evidence is mixed or incomplete; no conclusion on intrinsic-value discount.",
        VERDICT_FAIL: "Quantitative risk flags require review; they do not alone prove permanent business damage.",
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
        f"Research only: verify primary sources, independent valuation and portfolio fit before buying. "
        f"Conditional Tranche 1: {lo}-{hi}% of intended full position. "
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
        f"src/data/pending/daily-{snap.as_of}.json, then run "
        f"`python main.py --mode finalize`.)"
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
        "Data Warnings": "; ".join(data_quality_flags(snap)),
        "Valuation Source": snap.fair_value_source,
        "Financial Period": snap.financial_period,
        "Quarterly Period": snap.quarterly_periods[0] if snap.quarterly_periods else "",
        "News Status": snap.news_status,
        "Interest Expense Negligible": str(snap.interest_expense_negligible).lower(),
        "Valuation Status": "Proxy only" if snap.fair_value is not None else "Unknown",
        "Portfolio Fit": "Unverified",
        "Quote Currency": snap.quote_currency,
        "Financial Currency": snap.financial_currency,
        "Analysis Status": "Pending",
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
            "Monitor changes against existing research. Run the Moat Impairment Test only with sourced evidence: classify headwinds as "
            "'Transitory / Surface-level' vs 'Structural Damage', give a verdict "
            "(Pass - Temporary | Watch | Fail - Value Trap), and draft the strategic "
            "conditional research plan. Separate business quality, independent valuation and portfolio fit. "
            "Read existing research and primary sources for material events; missing news is not absence of risk."
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
    if row.get("Data Warnings"):
        return ACTION_WAIT
    return ACTION_RESEARCH


# ---------------------------------------------------------------------------
# Weekly digest building blocks
# ---------------------------------------------------------------------------

def _row_float(row: dict, key: str) -> float | None:
    try:
        raw = row.get(key, "")
        number = float(raw) if raw not in ("", None) else None
        return number if number is not None and math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def select_top_picks(recent_rows: list[dict], limit: int = 2) -> list[dict]:
    """Research candidates only: complete, plausible Pass rows, best first.

    Dedupes by ticker (latest row wins) so a ticker logged on several days of
    the lookback window cannot fill the whole picks list.
    """
    latest_by_ticker: dict[str, dict] = {}
    for row in recent_rows:
        ticker = str(row.get("Ticker", "")).upper()
        if ticker:
            latest_by_ticker[ticker] = row  # later rows overwrite = latest
    candidates: list[tuple[float, dict]] = []
    for row in latest_by_ticker.values():
        verdict = str(row.get("Moat Impairment Verdict", ""))
        if verdict != VERDICT_PASS or row.get("Data Warnings") or row.get("Analysis Status") != "Reviewed":
            continue
        if (not row.get("Valuation Source") or not row.get("Financial Period")
                or not row.get("Quarterly Period") or row.get("News Status") != "ok"
                or not row.get("Quote Currency") or row.get("Quote Currency") != row.get("Financial Currency")):
            continue
        price = _row_float(row, "Market Price ($)")
        if price is None or price <= 0:
            continue
        coverage = _row_float(row, "Interest Coverage Ratio")
        leverage = _row_float(row, "Net Debt / EBITDA")
        balance_ok = (
            (str(row.get("Interest Expense Negligible", "")).lower() == "true"
             or coverage is not None and coverage >= config.MIN_INTEREST_COVERAGE)
            and leverage is not None and leverage <= config.MAX_NET_DEBT_EBITDA
        )
        if not balance_ok:
            continue
        discount = _row_float(row, "Discount (%)")
        fcf_yield = _row_float(row, "FCF Yield (%)")
        roic = _row_float(row, "ROIC (%)")
        wacc = _row_float(row, "WACC (%)")
        if any(v is None for v in (discount, fcf_yield, roic, wacc)):
            continue
        if not (0 <= discount < 100 and 3 <= fcf_yield <= 30 and 0 < roic <= 100 and roic > wacc):
            continue
        # This is research priority, never a measure of expected investment return.
        score = discount * 2 + fcf_yield + roic * 0.5 - leverage * 2
        candidates.append((score, {**row, "Strategic Action": ACTION_RESEARCH}))
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
