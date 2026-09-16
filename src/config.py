"""
Central configuration for the Falling Angle watchlist system.

All secrets and environment-specific settings come from environment variables.
A local `.env` file is loaded automatically (python-dotenv). Storage is 100%
local (CSV + Markdown) — no external database needed.

Repo layout this module points into (repo root = parent of src/):
  watchlist/stock_knowledge/   per-ticker research + index.md + ledger.md
  watchlist/_daily/            daily brief markdown
  weekly/                      weekly digest markdown
  knowledge/                   methodology book (falling_angle.md ...)
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; CI supplies real env vars
    pass

BASE_DIR = Path(__file__).resolve().parent          # .../stock/src
REPO_ROOT = BASE_DIR.parent                          # .../stock

# --- Knowledge base (the watchlist the user maintains via ZCode sessions) ----
STOCK_KNOWLEDGE_DIR = REPO_ROOT / "watchlist" / "stock_knowledge"
INDEX_PATH = STOCK_KNOWLEDGE_DIR / "index.md"        # universe: the source of truth
LEDGER_PATH = STOCK_KNOWLEDGE_DIR / "ledger.md"      # append-only transactions
GUIDELINE_PATH = STOCK_KNOWLEDGE_DIR / "_GUIDELINE.md"  # per-ticker format contract
PERSONA_PATH = REPO_ROOT / "charactor" / "feb" / "persona.md"
FALLING_ANGLE_DOC = REPO_ROOT / "knowledge" / "falling_angle.md"

# --- Pipeline runtime artifacts (live under src/, gitignored) ----------------
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CSV_LOG_PATH = DATA_DIR / "daily_log.csv"            # the tracking database
DAILY_INPUT_FILE = DATA_DIR / "daily_input.txt"      # optional manual ticker list

# File contract between the Python data step and the ZCode analysis step:
PENDING_DIR = DATA_DIR / "pending"     # written by --mode daily/weekly
ANALYSIS_DIR = DATA_DIR / "analysis"   # written by the ZCode session, merged by --mode finalize

# --- Report destinations (inside the knowledge base, committed) --------------
DAILY_REPORT_DIR = REPO_ROOT / "watchlist" / "_daily"
WEEKLY_REPORT_DIR = REPO_ROOT / "weekly"

# ---------------------------------------------------------------------------
# Email (Gmail SMTP with App Password) & Discord webhook
# ---------------------------------------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # 16-char Gmail App Password
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
EMAIL_TO = [a.strip() for a in os.getenv("EMAIL_TO", "").split(",") if a.strip()]

# Discord server webhooks (Server Settings → Integrations → Webhooks).
# Treated as secrets: anyone holding a URL can post to the channel.
# Messages display the webhook's own name/avatar unless overridden here.
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")                # daily summary channel
DISCORD_WEBHOOK_URL_WEEKLY = os.getenv("DISCORD_WEBHOOK_URL_WEEKLY", "")  # weekly digest channel
# Feb persona: webhook display name (persona file: charactor/feb/persona.md)
DISCORD_USERNAME = os.getenv("DISCORD_USERNAME", "Feb 🌷")

# ---------------------------------------------------------------------------
# Stock universe: resolved from watchlist/stock_knowledge/index.md by
# universe.tickers() (Status Owned + Watch). A WATCHLIST env var, the optional
# daily_input.txt, or --tickers still override it — in that order.
# ---------------------------------------------------------------------------
WATCHLIST = [
    t.strip().upper()
    for t in os.getenv("WATCHLIST", "").split(",")
    if t.strip()
]

# Tickers whose Market column contains any of these substrings are excluded
# from the automated daily fetch (Thai DRs / unverified instruments — manual
# research only, per plan/stock_token_efficient_update_plan.md).
MANUAL_ONLY_MARKET_MARKERS = ["SET", "Thailand"]

# Manual Morningstar-style fair values, e.g. "NVDA=220,MSFT=530".
# Anything listed here overrides the analyst-target/earnings-based estimate.
def _parse_overrides(raw: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for pair in raw.split(","):
        if "=" in pair:
            tk, _, val = pair.partition("=")
            try:
                out[tk.strip().upper()] = float(val)
            except ValueError:
                continue
    return out

FAIR_VALUE_OVERRIDES: dict[str, float] = _parse_overrides(
    os.getenv("FAIR_VALUE_OVERRIDES", "")
)

# ---------------------------------------------------------------------------
# Analytical framework thresholds (see knowledge/falling_angle.md — the two
# must stay in sync; this file is the machine-readable copy)
# ---------------------------------------------------------------------------
MAX_NET_DEBT_EBITDA = 3.0        # flag above this
MIN_INTEREST_COVERAGE = 5.0      # must stay above this
MIN_DISCOUNT_FOR_BUY = 0.15      # >=15% below fair value to be interesting
STRONG_DISCOUNT = 0.30           # >=30% = deep value zone
MIN_FCF_YIELD = 0.03             # healthy real cash flow
POSITION_CAP_MIN = 5.0           # % of portfolio
POSITION_CAP_MAX = 8.0
FIRST_TRANCHE_MIN = 25           # % of the intended full position
FIRST_TRANCHE_MAX = 30

# Simplified WACC assumptions (adjust via env if desired)
RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", "0.042"))
EQUITY_RISK_PREMIUM = float(os.getenv("EQUITY_RISK_PREMIUM", "0.05"))
FALLBACK_TAX_RATE = float(os.getenv("FALLBACK_TAX_RATE", "0.23"))
FALLBACK_COST_OF_DEBT = float(os.getenv("FALLBACK_COST_OF_DEBT", "0.045"))
FALLBACK_JUSTIFIED_PE = float(os.getenv("FALLBACK_JUSTIFIED_PE", "16.0"))

# ---------------------------------------------------------------------------
# Storage / logging
# ---------------------------------------------------------------------------
LOOKBACK_DAYS_FOR_WEEKLY = 8     # weekly digest window

# ---------------------------------------------------------------------------
# Rotating Buffett-style mini-lesson curriculum for the weekly digest.
# The ZCode harness expands the selected brief; without it the brief itself is sent.
# ---------------------------------------------------------------------------
MINI_LESSON_TOPICS: list[dict[str, str]] = [
    {
        "title": "The AmEx Salad Oil Crisis (1963)",
        "brief": (
            "In 1963 Allied Crude Vegetable Oil collapsed and American Express's "
            "subsidiary certified fraudulent warehouse receipts. The stock fell ~50%, "
            "but Buffett walked the restaurants and saw people still using charge cards. "
            "The moat (brand + network of merchants/cardholders) was intact; the damage "
            "was a one-time solvency scare, not a broken franchise. He bought ~40% of "
            "the company. Lesson: separate 'the company owes money' from 'the company "
            "lost its customers'."
        ),
    },
    {
        "title": "Chipotle's E. Coli Outbreak (2015)",
        "brief": (
            "Food-safety scandal cut traffic and the stock roughly halved. Yet the "
            "underlying economics — high unit-level margins, no debt, customers who "
            "came back within months, industry-leading same-store recovery — were intact. "
            "A classic 'surface-level wound, healthy organs' fallen angel. Lesson: "
            "ask whether the crisis permanently removed the reason customers chose "
            "the business in the first place."
        ),
    },
    {
        "title": "Meta in 2022 — Capex Panic and the -75% Drawdown",
        "brief": (
            "Meta fell from ~$380 to ~$90 on Reality Labs spending and an Apple ATT "
            "headwind. Bears called it structural (TikTok, privacy); it turned out the "
            "ad network's network effects and targeting data were intact, and cost "
            "discipline ('year of efficiency') released enormous margin. Lesson: even "
            "genuine structural questions can be over-discounted when the core cash "
            "engine still compounds; size tranches, don't catch with one hand."
        ),
    },
    {
        "title": "Five Questions to Separate a Value Trap from an Opportunity",
        "brief": (
            "1) Is revenue loss from customers leaving permanently or pausing? "
            "2) Is gross margin stable (pricing power) or collapsing (competition)? "
            "3) Is ROIC still above WACC through the downturn? 4) Can the balance "
            "sheet survive 2+ years of pain (Net Debt/EBITDA, interest coverage)? "
            "5) Is management responding like owners (cut fat) or like caretakers "
            "(chasing fads)? Two or more 'no' answers = value trap until proven else."
        ),
    },
    {
        "title": "Assessing Switching Costs in an Inflationary World",
        "brief": (
            "Switching costs are the quiet moat: ERP systems, enterprise contracts, "
            "data lock-in, professional retraining. In inflation, they convert into "
            "pricing power because customers grumble but stay. Test: estimate the "
            "total cost (money, time, risk, retraining) for a customer to leave. If "
            "it exceeds one year of your price increase, you own pricing power."
        ),
    },
    {
        "title": "Pricing Power: The Only Inflation Hedge That Matters",
        "brief": (
            "Buffett: 'The single most important decision in evaluating a business is "
            "pricing power.' Evidence to look for: gross margin stability across input "
            "cost shocks, historical price increases above inflation without volume "
            "loss, and unit economics that improve as prices rise. A moat that cannot "
            "pass cost increases to customers is a moat in name only."
        ),
    },
    {
        "title": "The Psychology of Buying When Others Panic",
        "brief": (
            "Falling knives feel unsafe because your brain equates price movement with "
            "information. Counter it mechanically: write the thesis and invalidation "
            "criteria BEFORE buying, pre-commit tranche sizes (25-30% first), and "
            "re-read the balance sheet when scared. You are not paid for comfort; you "
            "are paid for being right when it is uncomfortable."
        ),
    },
    {
        "title": "Why ROIC > WACC Is the Engine of Compounding",
        "brief": (
            "A business that earns 15% on incremental capital and reinvests half of it "
            "compounds intrinsic value ~7.5% a year before growth from pricing. If "
            "ROIC sits below WACC, 'growth' destroys value and cheap-looking multiples "
            "are traps. Always pair the ROIC history with where the moat comes from — "
            "the source explains whether high ROIC is durable."
        ),
    },
    {
        "title": "Balance Sheets Beat Earnings in a Crisis",
        "brief": (
            "Earnings tell you how the business performs in good weather; Net "
            "Debt/EBITDA and interest coverage tell you whether it survives the storm. "
            "Leverage below 3x EBITDA and coverage above 5x buy management the time "
            "to fix transitory problems. Highly levered 'cheap' stocks die before the "
            "market re-rates them — that is how value traps are manufactured."
        ),
    },
    {
        "title": "Coca-Cola 1988: Paying Up vs. Bottom-Fishing",
        "brief": (
            "Buffett bought Coca-Cola at ~15x earnings — no discount at all — because "
            "the moat and reinvestment runway were supreme. Fallen-angel investing is "
            "one edge, not the only edge. Lesson: discount to fair value is the entry "
            "technique, but the durability of the moat is the thesis; never let a "
            "big discount talk you into a weak franchise."
        ),
    },
    {
        "title": "Airlines, Retail and Other Structural Graveyards",
        "brief": (
            "Some industries commoditize permanently: undifferentiated product, "
            "unionized cost bases, capacity that re-enters on every upcycle. A falling "
            "price in a structurally bad industry is the market being right. Checklist "
            "for structural damage: technology substitution (Kodak), lost pricing "
            "power (airlines), permanent customer defection (Blackberry). If you see "
            "these, the discount is the compensation, not the opportunity."
        ),
    },
    {
        "title": "Write the Obituary Before the Wedding: Invalidation Discipline",
        "brief": (
            "Before the first tranche, write exactly what evidence would prove you "
            "wrong — margin declines for 2 straight quarters, a top customer publicly "
            "churning, coverage falling below 3x — and what you will do (cut, no "
            "averaging down past the plan). Pre-commitment converts a loss into "
            "process; improvisation converts a thesis into hope."
        ),
    },
]


def smtp_ready() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD and EMAIL_TO)


def discord_ready() -> bool:
    return bool(DISCORD_WEBHOOK_URL)


def discord_weekly_ready() -> bool:
    """Weekly channel; falls back to the daily webhook when no separate URL."""
    return bool(DISCORD_WEBHOOK_URL_WEEKLY or DISCORD_WEBHOOK_URL)
