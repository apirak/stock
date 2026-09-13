"""
Analytical engine: deterministic screening rules + LLM-powered Moat
Impairment Test, strategic plan and weekly narratives.

The LLM never gets the final say on arithmetic — all ratios are computed in
data_fetcher and passed as facts. The LLM classifies the *nature* of the
headwinds (transitory vs structural) and drafts the strategy; if no LLM is
configured, rule-based fallbacks keep the pipeline alive.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import requests

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

SYSTEM_PROMPT = """You are a disciplined Buffett-style quality-value analyst running a \
"Fallen Angel" screen: wide-moat companies whose share price has fallen below intrinsic \
value. Your job is to run a Moat Impairment Test and draft a strategic entry plan.

CLASSIFICATION TAXONOMY — judge every headwind as either:
- "Transitory / Surface-level": a wound to the skin, organs healthy. Examples: a one-off \
product-safety scare, a single missed quarter, a temporary regulatory investigation, a \
short-lived crisis of faith, macro-driven multiple compression. The reasons customers \
chose the business (brand, switching costs, network effects, cost advantage) are intact.
- "Structural Damage": a spreading cancer. Examples: permanent technology obsolescence \
(Kodak, Blackberry), lost pricing power to competitors, customers churning permanently, \
commoditization of the product, a moat eroded by secular change.

VERDICT RULES:
- "Pass - Temporary": headwinds are transitory AND the moat sources remain verifiable.
- "Watch": mixed evidence, or the balance sheet is stressed but survivable.
- "Fail - Value Trap": structural damage, or leverage/coverage suggests the business may \
not survive to see the recovery.

You must respect the quantitative facts given to you. Do not invent numbers. If a metric \
is null, reason qualitatively and say what to verify next.

Respond with ONLY a JSON object (no markdown fences, no commentary) matching this schema:
{
  "verdict": "Pass - Temporary" | "Watch" | "Fail - Value Trap",
  "headwind_category": "Transitory / Surface-level" | "Structural Damage" | "Mixed",
  "moat_sources": ["Intangible Assets" | "Switching Costs" | "Network Effect" | "Cost Advantage" | "Efficient Scale"],
  "moat_intact": true | false,
  "core_headwinds": "one or two sentences naming the specific headwinds and near-term catalyst",
  "deep_dive": "3-5 sentence moat deep-dive: why the moat is (or is not) intact, and how exactly the market is overreacting (or correctly repricing)",
  "tranche_plan": "concrete 3-tranche entry plan; first tranche should deploy 25-30% of the intended full position",
  "invalidation_criteria": ["specific, observable falsifier 1", "...", "at least 3 items"],
  "suggested_position_cap_pct": 5-8 (integer),
  "key_risk": "single biggest risk in one sentence"
}"""


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
    """Rule-based classification used as LLM fallback and as a sanity layer."""
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
# LLM plumbing (REST, provider-agnostic)
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _post(url: str, headers: dict, payload: dict) -> dict:
    resp = requests.post(url, headers=headers, json=payload, timeout=config.LLM_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _call_anthropic(system: str, user: str) -> str:
    payload = {
        "model": config.LLM_MODEL or config.DEFAULT_LLM_MODELS["anthropic"],
        "max_tokens": config.LLM_MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    data = _post(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": config.ANTHROPIC_API_KEY,
         "anthropic-version": "2023-06-01", "content-type": "application/json"},
        payload,
    )
    return "".join(b.get("text", "") for b in data.get("content", []))


def _call_openai(system: str, user: str) -> str:
    payload = {
        "model": config.LLM_MODEL or config.DEFAULT_LLM_MODELS["openai"],
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    data = _post(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        payload,
    )
    return data["choices"][0]["message"]["content"]


def _call_gemini(system: str, user: str) -> str:
    model = config.LLM_MODEL or config.DEFAULT_LLM_MODELS["gemini"]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={config.GEMINI_API_KEY}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": config.LLM_MAX_TOKENS},
    }
    data = _post(url, {}, payload)
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def call_llm_json(system: str, user: str) -> dict | None:
    if not config.llm_ready():
        return None
    callers = {"anthropic": _call_anthropic, "openai": _call_openai, "gemini": _call_gemini}
    try:
        return _extract_json(callers[config.LLM_PROVIDER](system, user))
    except Exception as exc:  # noqa: BLE001 - degrade instead of killing the run
        print(f"[analyzer] LLM call failed ({config.LLM_PROVIDER}): {exc}")
        return None


# ---------------------------------------------------------------------------
# Daily analysis
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
        f"Net Debt/EBITDA rises above 4.0x or interest coverage falls below 3.0x",
        "A major customer segment publicly churns or switching-cost evidence reverses",
        "ROIC stays below WACC for 4 consecutive quarters",
    ]


def analyze_ticker(snap: FinancialSnapshot, use_llm: bool = True) -> dict:
    """Produce one Daily_Log row for a snapshot.

    use_llm=False (the default hybrid flow) skips the paid API entirely — the
    narrative fields become placeholders until a ZCode analysis JSON is merged
    by `main.py --mode finalize`.
    """
    verdict_h, reasons = heuristic_verdict(snap)
    flags = balance_sheet_flags(snap)

    llm: dict = {}
    if use_llm:
        user_prompt = (
            "Analyze this fallen-angel candidate. Today: "
            f"{datetime.now(timezone.utc):%Y-%m-%d}. Framework thresholds: "
            f"Net Debt/EBITDA flag > {config.MAX_NET_DEBT_EBITDA}x, interest coverage must be > "
            f"{config.MIN_INTEREST_COVERAGE}x, buy only at >= {config.MIN_DISCOUNT_FOR_BUY:.0%} discount.\n"
            f"QUANTITATIVE FACTS:\n{json.dumps(snap.to_prompt_dict(), indent=2)}\n"
            f"RULE-BASED FLAGS (verify, then agree or refute): {reasons or 'none'}"
        )
        llm = call_llm_json(SYSTEM_PROMPT, user_prompt) or {}

    if use_llm and not llm:
        note = "(Rule-based analysis — configure an LLM key for narrative depth.)"
    elif not use_llm:
        note = (
            f"(Data collected — deep-dive pending. A ZCode session should analyze "
            f"data/pending/daily-{snap.as_of}.json, then run `python main.py --mode finalize`.)"
        )
    else:
        note = ""

    verdict = llm.get("verdict", verdict_h)
    if verdict not in VALID_VERDICTS:
        verdict = verdict_h
    action = strategic_action(verdict, snap)
    headwinds = llm.get("core_headwinds") or "; ".join(reasons) or "n/a"
    deep_dive = llm.get("deep_dive") or _fallback_deep_dive(snap, verdict, flags, note)
    tranche = llm.get("tranche_plan") or _fallback_tranche_plan()
    invalidation = llm.get("invalidation_criteria") or _fallback_invalidation(snap)
    if isinstance(invalidation, str):
        invalidation = [invalidation]
    cap = llm.get("suggested_position_cap_pct")
    try:
        cap = float(cap)
        cap = min(max(cap, config.POSITION_CAP_MIN), config.POSITION_CAP_MAX)
    except (TypeError, ValueError):
        cap = config.POSITION_CAP_MIN

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
        "Core Headwinds / Catalyst": headwinds,
        "Strategic Action": action,
        "Headwind Category": llm.get("headwind_category", ""),
        "Moat Sources": ", ".join(llm.get("moat_sources", []) or []),
        "Deep-Dive": deep_dive,
        "Tranche Plan": tranche,
        "Invalidation Criteria": " | ".join(invalidation),
        "Suggested Position Cap (%)": cap,
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


def generate_pick_narrative(pick_row: dict, use_llm: bool = True) -> dict:
    """Weekly deep-dive for one top pick (falls back to logged text without LLM)."""
    if not use_llm:
        return {
            "why_moat_intact": pick_row.get("Deep-Dive", ""),
            "market_overreaction": pick_row.get("Core Headwinds / Catalyst", ""),
            "tranche_strategy": pick_row.get("Tranche Plan", "") or _fallback_tranche_plan(),
            "invalidation_criteria": [
                c for c in str(pick_row.get("Invalidation Criteria", "")).split(" | ") if c
            ] or _fallback_invalidation(FinancialSnapshot(ticker=pick_row.get("Ticker", "?"))),
        }
    user_prompt = (
        "This candidate passed the weekly Fallen Angel screen. Write the weekly digest "
        "entry for an investor email. Sections inside the JSON: 'why_moat_intact' (why the "
        "fortress still stands, 3-4 sentences), 'market_overreaction' (how exactly the "
        "market is overreacting, 2-3 sentences), 'tranche_strategy' (concrete split-entry "
        f"plan, first tranche {config.FIRST_TRANCHE_MIN}-{config.FIRST_TRANCHE_MAX}% of the "
        "full position), 'invalidation_criteria' (array of 3+ specific falsifiers).\n"
        f"DATA:\n{json.dumps({k: pick_row.get(k, '') for k in COLUMNS}, indent=2)}"
    )
    weekly_schema = (
        'Respond with ONLY JSON: {"why_moat_intact": "...", "market_overreaction": "...", '
        '"tranche_strategy": "...", "invalidation_criteria": ["..."]}'
    )
    llm = call_llm_json(SYSTEM_PROMPT + "\n\n" + weekly_schema, user_prompt) or {}
    return {
        "why_moat_intact": llm.get("why_moat_intact") or pick_row.get("Deep-Dive", ""),
        "market_overreaction": llm.get("market_overreaction")
        or pick_row.get("Core Headwinds / Catalyst", ""),
        "tranche_strategy": llm.get("tranche_strategy")
        or pick_row.get("Tranche Plan", "") or _fallback_tranche_plan(),
        "invalidation_criteria": llm.get("invalidation_criteria")
        or [c for c in str(pick_row.get("Invalidation Criteria", "")).split(" | ") if c]
        or _fallback_invalidation(FinancialSnapshot(ticker=pick_row.get("Ticker", "?"))),
    }


def generate_mini_lesson(use_llm: bool = True) -> dict:
    """Rotating Buffett-style lesson; the LLM expands the stored brief."""
    week_index = datetime.now(timezone.utc).isocalendar()[1]
    topic = config.MINI_LESSON_TOPICS[week_index % len(config.MINI_LESSON_TOPICS)]
    if not use_llm or not config.llm_ready():
        return {"title": topic["title"], "body": topic["brief"]}
    user_prompt = (
        f"Write this week's mini-lesson for a quality-value investing email.\n"
        f"Title: {topic['title']}\nSeed material: {topic['brief']}\n"
        "Expand to 150-220 words in a direct, practical Buffett-letter tone. "
        "End with one actionable takeaway sentence. Plain text only, no markdown."
    )
    if config.llm_ready():
        provider = {
            "anthropic": _call_anthropic,
            "openai": _call_openai,
            "gemini": _call_gemini,
        }[config.LLM_PROVIDER]
        try:
            text = provider(SYSTEM_PROMPT, user_prompt).strip()
            if len(text) > 200:
                return {"title": topic["title"], "body": text}
        except Exception as exc:  # noqa: BLE001
            print(f"[analyzer] mini-lesson LLM failed: {exc}")
    return {"title": topic["title"], "body": topic["brief"]}
