"""
Fallen Angel inbox archiver.

Pulls the daily "[Fallen Angel with Jan]" emails (Gemini automation, self-sent
to the user's Gmail) over IMAP and archives each one into the knowledge base:

    watchlist/stock_knowledge/fallen_angel/<TICKER>/<TICKER>_fallen_angel_<YYYY>.md

One dated section per email, appended chronologically (append-only). Every
section carries a machine-readable FA tag so the weekly rollup can grep
price/FV/MoS history without an LLM:

    <!-- FA: ticker=NKE date=2026-09-20 price=37.05 fv=94.0 mos=60.6 pe=17.3 div=4.4 msgid=... -->

New tickers are also added to index.md (via universe.add_row) with
Status="Fallen Angel" so the daily price pipeline picks them up; promotion to
own/ or watchlist/ stays a user/ZCode-session decision (see _GUIDELINE.md §9).

Auth: Gmail IMAP with a 16-char App Password (https://myaccount.google.com/apppasswords,
needs 2FA). Read GMAIL_USER / GMAIL_APP_PASSWORD from .env (falling back to
SMTP_USER / SMTP_PASSWORD). The mailbox is never modified (BODY.PEEK fetch);
re-runs are idempotent via the msgid in the FA tag.

Usage:
    python fallen_angel_inbox.py                  # fetch last 3 days, archive new ones
    python fallen_angel_inbox.py --since-days 7   # wider catch-up window
    python fallen_angel_inbox.py --dry-run        # show what would happen
    python fallen_angel_inbox.py --eml path.eml   # parse a local export (no IMAP)
"""
from __future__ import annotations

import argparse
import hashlib
import imaplib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

import config
import universe

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
SUBJECT_PREFIX = "[Fallen Angel with Jan]"
BUCKET = "fallen_angel"  # folder under stock_knowledge/ + index Status


# ---------------------------------------------------------------------------
# Credentials (.env next to the repo root; dotenv when available, else manual)
# ---------------------------------------------------------------------------
def load_credentials() -> tuple[str, str]:
    env_file = config.REPO_ROOT / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file)
    except ImportError:
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    user = os.getenv("GMAIL_USER") or os.getenv("SMTP_USER", "")
    password = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
    # Google shows app passwords as 4 groups of 4 ("xxxx xxxx xxxx xxxx");
    # tolerate pasting them with the spaces included.
    return user, password.replace(" ", "")


# ---------------------------------------------------------------------------
# HTML -> plain text (stdlib only; Jan's template is consistent, so a small
# converter beats a markdown library dependency)
# ---------------------------------------------------------------------------
class _HTMLText(HTMLParser):
    _SKIP = {"script", "style", "head"}
    _BLOCK = {"p", "div", "tr", "table", "ul", "ol", "blockquote", "section",
              "header", "footer", "article"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def _newline(self) -> None:
        self.parts.append("\n")

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "br":
            self._newline()
        elif tag == "li":
            self._newline()
            self.parts.append("- ")
        elif tag in ("td", "th"):
            self.parts.append(" | ")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._newline()
            self.parts.append("#" * min(int(tag[1]) + 1, 6) + " ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK or tag in ("li", "tr") or tag.startswith("h"):
            self._newline()

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t]+", " ", ln).strip(" |") for ln in raw.splitlines()]
        out: list[str] = []
        for ln in lines:
            if ln or (out and out[-1]):  # collapse blank runs to one
                out.append(ln)
        return "\n".join(out).strip()


def html_to_text(html_body: str) -> str:
    parser = _HTMLText()
    parser.feed(html_body)
    return parser.text()


# ---------------------------------------------------------------------------
# Email parsing
# ---------------------------------------------------------------------------
@dataclass
class ParsedEmail:
    subject: str
    msgid: str
    received: datetime
    body_text: str
    ticker: str = ""
    company: str = ""
    exchange: str = ""
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def local_date(self) -> str:
        return self.received.astimezone().strftime("%Y-%m-%d")


def _decode_subject(msg: Message) -> str:
    try:
        return str(make_header(decode_header(msg.get("Subject", ""))))
    except Exception:
        return msg.get("Subject", "")


def _extract_body(msg: Message) -> str:
    """Prefer the HTML part (Jan's plain-text part is an abbreviated teaser)."""
    html_part = plain_part = None
    for part in msg.walk():
        if part.get_content_maintype() != "text":
            continue
        charset = part.get_content_charset() or "utf-8"
        payload = part.get_payload(decode=True) or b""
        text = payload.decode(charset, errors="replace")
        if part.get_content_type() == "text/html":
            html_part = html_part or text
        elif part.get_content_type() == "text/plain":
            plain_part = plain_part or text
    if html_part:
        return html_to_text(html_part)
    return plain_part or ""


_TICKER_RE = re.compile(r"บทวิเคราะห์\s+([A-Z][A-Z0-9.]{0,9})\s*\(([^)]+)\)")
_EXCHANGE_RE = re.compile(r"\b(NYSE|NASDAQ|AMEX|OTC|LSE|SET)\s*:\s*([A-Z][A-Z0-9.]{0,9})\b")
_EXCHANGE_LABEL = {
    "NYSE": "NYSE (US)", "NASDAQ": "NASDAQ (US)", "AMEX": "AMEX (US)",
    "OTC": "OTC (US ADR)", "LSE": "LSE (UK)", "SET": "SET (Thailand)",
}

# Jan is an LLM: the daily template drifts (label spellings, table shapes).
# Metrics are therefore parsed from the "ส่วนที่ 1" block (falls back to the
# whole body), on whitespace-normalized text, matching several known label
# spellings and taking the FIRST number after the label.
_NUM = r"([\d,]+(?:\.\d+)?)"
_METRIC_RES = {
    "price": re.compile(
        r"(?:ราคาตลาด(?:ปัจจุบัน|ล่าสุด)|ราคาปัจจุบัน)\s*:?\s*\|?\s*~?\$?" + _NUM),
    "fv": re.compile(r"Fair Value[^%]{0,30}?~?\$?" + _NUM),
    "mos": re.compile(
        r"(?:Margin of Safety|ส่วนลด)(?:\s*\([^)]{0,30}\))?\s*:?\s*\|?\s*~?"
        + _NUM + r"\s*%"),
    "pe": re.compile(r"P/E[^%]{0,40}?" + _NUM + r"\s*x"),
    "div": re.compile(r"(?:Dividend Yield|อัตราปันผล)[^%]{0,40}?~?" + _NUM + r"\s*%"),
}
_SECTION1_RE = re.compile(r"ส่วนที่\s*1(.*?)ส่วนที่\s*2", re.S)


def extract_metrics(body: str, subject: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    section = _SECTION1_RE.search(body)
    text = re.sub(r"\s+", " ", section.group(1) if section else body)
    for key, rx in _METRIC_RES.items():
        m = rx.search(text)
        if m:
            try:
                metrics[key] = float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    if "mos" not in metrics:  # subject often carries "ส่วนลด 60%"
        hit = re.search(r"ส่วนลด\s*~?([\d,]+(?:\.\d+)?)\s*%", subject)
        if hit:
            metrics["mos"] = float(hit.group(1).replace(",", ""))
    return metrics


def parse_message(raw: bytes) -> ParsedEmail:
    msg = message_from_bytes(raw)
    subject = _decode_subject(msg)
    msgid = (msg.get("Message-Id") or msg.get("Message-ID") or "").strip().strip("<>")
    if not msgid:  # deterministic fallback so re-runs still dedupe
        msgid = "sha1-" + hashlib.sha1((subject + (msg.get("Date") or "")).encode()).hexdigest()[:16]
    try:
        received = parsedate_to_datetime(msg.get("Date"))
    except (TypeError, ValueError):
        received = datetime.now().astimezone()

    parsed = ParsedEmail(subject=subject, msgid=msgid, received=received,
                         body_text=_extract_body(msg))

    m = _TICKER_RE.search(subject)
    if m:
        parsed.ticker, parsed.company = m.group(1), m.group(2).strip()
    x = _EXCHANGE_RE.search(parsed.body_text) or _EXCHANGE_RE.search(subject)
    if x:
        parsed.exchange = _EXCHANGE_LABEL.get(x.group(1), x.group(1))
        parsed.ticker = parsed.ticker or x.group(2)

    parsed.metrics = extract_metrics(parsed.body_text, subject)
    return parsed


# ---------------------------------------------------------------------------
# Archiving
# ---------------------------------------------------------------------------
def _entry_markdown(parsed: ParsedEmail) -> str:
    title = parsed.subject
    if title.startswith(SUBJECT_PREFIX):
        title = title[len(SUBJECT_PREFIX):].strip()
    tag_bits = [f"ticker={parsed.ticker or 'UNKNOWN'}", f"date={parsed.local_date}"]
    for key in ("price", "fv", "mos", "pe", "div"):
        if key in parsed.metrics:
            tag_bits.append(f"{key}={parsed.metrics[key]:g}")
    tag_bits.append(f"msgid={parsed.msgid}")
    received_local = parsed.received.astimezone().strftime("%Y-%m-%d %H:%M")
    return (
        f"## {parsed.local_date} — {title}\n\n"
        f"<!-- FA: {' '.join(tag_bits)} -->\n\n"
        f"Source: email \"{SUBJECT_PREFIX}\" (Gemini automation) · received {received_local}\n\n"
        f"{parsed.body_text}\n"
    )


def _target_file(ticker: str, year: int) -> Path:
    return (config.STOCK_KNOWLEDGE_DIR / BUCKET / ticker /
            f"{ticker}_fallen_angel_{year}.md")


def _new_file_header(ticker: str, year: int) -> str:
    return (
        f"# {ticker} — Fallen Angel (Jan) Archive {year}\n\n"
        f"> จดหมายรายวัน \"{SUBJECT_PREFIX}\" ของ {ticker} — append-only, chronological.\n"
        f"> `<!-- FA: ... -->` tags are machine-readable (weekly rollup greps these).\n"
        f"> Archive keeps Jan's original Thai text; distill to English when promoting\n"
        f"> this ticker to own/ or watchlist/ (see _GUIDELINE.md §9).\n"
    )


def archive(parsed: ParsedEmail, dry_run: bool = False) -> str:
    """File one parsed email. Returns a human-readable outcome line."""
    if not parsed.ticker:
        inbox = config.STOCK_KNOWLEDGE_DIR / BUCKET / "_inbox" / f"{parsed.local_date}.md"
        if not dry_run:
            inbox.parent.mkdir(parents=True, exist_ok=True)
            with inbox.open("a", encoding="utf-8") as fh:
                fh.write("\n\n" + _entry_markdown(parsed))
        return f"[inbox] no ticker found -> filed under _inbox/{inbox.name} (dry_run={dry_run})"

    ticker = parsed.ticker.upper()
    year = parsed.received.astimezone().year
    target = _target_file(ticker, year)
    dedupe_key = f"msgid={parsed.msgid}"
    if target.exists() and dedupe_key in target.read_text(encoding="utf-8"):
        return f"[inbox] {ticker} {parsed.local_date}: already archived — skipped"

    entry = _entry_markdown(parsed)
    if dry_run:
        preview = "\n".join(entry.splitlines()[:8])
        return (f"[inbox] DRY-RUN would append to {target.relative_to(config.REPO_ROOT)}"
                f"\n--- entry preview ---\n{preview}\n---")

    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(_new_file_header(ticker, year), encoding="utf-8")
    with target.open("a", encoding="utf-8") as fh:
        fh.write("\n\n" + entry)

    added = universe.add_row({
        "Ticker": ticker,
        "Company": parsed.company or "NEEDS VERIFICATION",
        "Market": parsed.exchange or "Unknown",
        "Status": universe.STATUS_FALLEN_ANGEL,
        "Research Priority": "Low",
        "Opportunity Status": "TBD",
        "Last Review": parsed.local_date,
    })
    note = " + added to index.md" if added else ""
    return f"[inbox] archived {ticker} {parsed.local_date} -> {target.relative_to(config.REPO_ROOT)}{note}"


# ---------------------------------------------------------------------------
# IMAP fetch
# ---------------------------------------------------------------------------
def fetch_emails(since_days: int) -> list[bytes]:
    user, password = load_credentials()
    if not user or not password:
        raise SystemExit(
            "[inbox] missing Gmail credentials. Add to .env:\n"
            "  GMAIL_USER=you@gmail.com\n"
            "  GMAIL_APP_PASSWORD=<16-char app password from "
            "https://myaccount.google.com/apppasswords> (needs 2FA)"
        )
    if len(password) != 16:
        raise SystemExit(
            f"[inbox] GMAIL_APP_PASSWORD is {len(password)} chars — Gmail App "
            "Passwords are exactly 16 (shown as xxxx xxxx xxxx xxxx). The current "
            "value looks like a normal account password, which Gmail rejects over "
            "IMAP. Create an app password at https://myaccount.google.com/apppasswords "
            "and paste the 16-char code into .env."
        )
    since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
    with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
        imap.login(user, password)
        imap.select("INBOX", readonly=True)
        criteria = f'FROM "{user}" SUBJECT "{SUBJECT_PREFIX}" SINCE {since}'
        status, data = imap.search(None, criteria)
        if status != "OK":
            raise SystemExit(f"[inbox] IMAP search failed: {status}")
        ids = data[0].split()
        raws: list[bytes] = []
        for num in ids:
            status, fetched = imap.fetch(num, "(BODY.PEEK[])")
            if status == "OK" and fetched and isinstance(fetched[0], tuple):
                raws.append(fetched[0][1])
        print(f"[inbox] {len(ids)} matching message(s) since {since}, fetched {len(raws)}")
        return raws


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since-days", type=int, default=3,
                        help="IMAP lookback window in days (default 3); dedupe makes re-runs safe")
    parser.add_argument("--dry-run", action="store_true", help="parse and report, write nothing")
    parser.add_argument("--eml", action="append", default=[],
                        help="parse a local .eml export instead of IMAP (repeatable)")
    args = parser.parse_args()

    raws = [Path(p).read_bytes() for p in args.eml] if args.eml else fetch_emails(args.since_days)
    if not raws:
        print("[inbox] nothing to do")
        return
    for raw in raws:
        print(archive(parse_message(raw), dry_run=args.dry_run))


if __name__ == "__main__":
    main()
