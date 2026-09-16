"""
Portfolio ledger: append-only transaction history at
watchlist/stock_knowledge/ledger.md.

The ledger is written by ZCode sessions when the USER reports a transaction —
never by the daily/weekly automations. Portfolio positions are always derived
from this file, never maintained separately.

Entry format (matches the template seeded in ledger.md):

    ## 2026-09-16 — BUY NVDA
    Shares: 2
    Price: 220 USD
    Fees: unknown
    Reason: Temporary valuation dislocation
    Notes: user supplied transaction

Supported types: BUY SELL DIVIDEND SPLIT TRANSFER CASH_IN CASH_OUT
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import config

TRANSACTION_TYPES = ("BUY", "SELL", "DIVIDEND", "SPLIT", "TRANSFER", "CASH_IN", "CASH_OUT")
_ENTRY_HEADER_RE = re.compile(
    r"^##\s*(\d{4}-\d{2}-\d{2})\s*—\s*(BUY|SELL|DIVIDEND|SPLIT|TRANSFER|CASH_IN|CASH_OUT)\s+(\S+)\s*$",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(r"^([A-Za-z_]+):\s*(.*)$")


def append_transaction(date: str, tx_type: str, ticker: str, *, shares=None,
                       price=None, currency: str = "USD", fees=None,
                       reason: str = "", notes: str = "",
                       path: Path | None = None) -> Path:
    """Append one transaction entry and return the ledger path.

    Missing details must be passed as None — they are recorded as `unknown`,
    never inferred. The file is created with a header if it does not exist.
    """
    tx_type = tx_type.upper()
    if tx_type not in TRANSACTION_TYPES:
        raise ValueError(f"unknown transaction type: {tx_type} (allowed: {TRANSACTION_TYPES})")
    datetime.strptime(date, "%Y-%m-%d")  # raises on malformed date — by design

    def fmt(value) -> str:
        return "unknown" if value is None or str(value).strip() == "" else str(value)

    entry = [
        f"## {date} — {tx_type} {ticker.upper()}",
        f"Shares: {fmt(shares)}",
        f"Price: {fmt(price)} {currency}".strip(),
        f"Fees: {fmt(fees)}",
        f"Reason: {reason or 'unknown'}",
        f"Notes: {notes or 'user supplied transaction'}",
        "",
    ]
    path = path or config.LEDGER_PATH
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Portfolio Ledger — append-only transaction history\n\n"
            "<!-- Append below. Never edit or delete historical entries. -->\n\n",
            encoding="utf-8",
        )
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(entry))
    return path


def parse_transactions(text: str) -> list[dict]:
    """Parse ledger text into transaction dicts. Pure — no file access.

    Malformed entries are skipped; unknown field lines are kept under 'extra'.
    """
    out: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        header = _ENTRY_HEADER_RE.match(line.strip())
        if header:
            current = {
                "date": header.group(1),
                "type": header.group(2).upper(),
                "ticker": header.group(3).upper(),
                "shares": None,
                "price": None,
                "currency": "",
                "fees": None,
                "reason": "",
                "notes": "",
            }
            out.append(current)
            continue
        if current is None:
            continue
        field = _FIELD_RE.match(line.strip())
        if not field:
            continue
        key, value = field.group(1).lower(), field.group(2).strip()
        if value.lower() == "unknown":
            value = ""
        if key in ("shares", "fees"):
            try:
                current[key] = float(value) if value else None
            except ValueError:
                pass
        elif key == "price":
            # "Price: 220 USD" — first token is the number, the rest the currency
            token, _, rest = value.partition(" ")
            try:
                current["price"] = float(token) if token else None
            except ValueError:
                pass
            current["currency"] = rest.strip()
        elif key == "currency":
            current["currency"] = value
        elif key in ("reason", "notes"):
            current[key] = value
    return out


def read_transactions(path: Path | None = None) -> list[dict]:
    """Read all transactions from the ledger file."""
    path = path or config.LEDGER_PATH
    if not path.exists():
        return []
    return parse_transactions(path.read_text(encoding="utf-8"))


def net_positions(transactions: list[dict] | None = None) -> dict[str, dict]:
    """Derive current holdings from BUY/SELL transactions (moving-average cost).

    Returns {ticker: {"shares": float, "avg_cost": float|None, "last_date": str}}.
    Entries with unknown share counts are excluded (they cannot be quantified);
    a later SELL that takes a position negative is treated as data error and
    clamps that ticker to zero shares.
    """
    txs = transactions if transactions is not None else read_transactions()
    book: dict[str, dict] = {}
    for tx in txs:  # file order == chronological order (append-only)
        ticker = tx["ticker"]
        if ticker in ("CASH", "") or tx["type"] in ("DIVIDEND", "TRANSFER", "CASH_IN", "CASH_OUT"):
            continue
        pos = book.setdefault(ticker, {"shares": 0.0, "avg_cost": None, "last_date": tx["date"]})
        shares, price = tx["shares"], tx["price"]
        if shares is None:
            continue
        if tx["type"] == "BUY":
            total_cost = pos["shares"] * (pos["avg_cost"] or 0.0) + shares * (price or 0.0)
            pos["shares"] += shares
            pos["avg_cost"] = total_cost / pos["shares"] if pos["shares"] else None
        elif tx["type"] == "SELL":
            pos["shares"] = max(0.0, pos["shares"] - shares)
            if pos["shares"] == 0.0:
                pos["avg_cost"] = None
        elif tx["type"] == "SPLIT":
            if shares and shares > 0:
                pos["shares"] *= shares
                pos["avg_cost"] = (pos["avg_cost"] or 0.0) / shares
        pos["last_date"] = tx["date"]
    return {t: p for t, p in book.items() if p["shares"] > 0}


def today() -> str:
    """Current UTC date — the date appended to entries when the user doesn't give one."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
