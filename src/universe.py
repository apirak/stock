"""
Universe access: parse and update watchlist/stock_knowledge/index.md.

index.md is the single source of truth for what the bots track. Its table has
the columns:

    | Ticker | Company | Market | Status | Research Priority | Opportunity Status | Last Review |

Status is `Owned` or `Watch` (the two statuses the user maintains); the folder
placement mirrors it: stock_knowledge/own/<TICKER>/ vs stock_knowledge/watchlist/<TICKER>/.

All functions take an explicit `path` (default config.INDEX_PATH) so tests can
run against temp files without touching the real knowledge base.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import config

COLUMNS = ["Ticker", "Company", "Market", "Status", "Research Priority",
           "Opportunity Status", "Last Review"]
STATUS_OWNED = "Owned"
STATUS_WATCH = "Watch"
_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*"
                     r"([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$")


def parse_index(text: str) -> list[dict]:
    """Parse index.md text into row dicts. Pure — no file access.

    Returns one dict per table row (keys = COLUMNS). Non-table lines,
    header separators, and malformed rows are skipped silently.
    """
    rows: list[dict] = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.groups()]
        if cells[0] in ("Ticker", "---", "") or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append(dict(zip(COLUMNS, cells)))
    return rows


def read_index(path: Path | None = None) -> list[dict]:
    """Read the current index table as row dicts."""
    path = path or config.INDEX_PATH
    if not path.exists():
        return []
    return parse_index(path.read_text(encoding="utf-8"))


def _is_manual_only(row: dict) -> bool:
    market = str(row.get("Market", ""))
    return any(marker.lower() in market.lower()
               for marker in config.MANUAL_ONLY_MARKET_MARKERS)


def tickers(rows: list[dict] | None = None, status: str | None = None,
            automated_only: bool = False) -> list[str]:
    """Ticker symbols from index rows, index order preserved.

    status: filter by exact Status ("Owned"/"Watch"); None = both.
    automated_only: drop manual-research-only tickers (Thai SET / unverified DRs)
    so the price-fetch pipeline never wastes calls on them.
    """
    out: list[str] = []
    for row in rows if rows is not None else read_index():
        if status and str(row.get("Status", "")) != status:
            continue
        if automated_only and _is_manual_only(row):
            continue
        ticker = str(row.get("Ticker", "")).strip().upper()
        if ticker and ticker not in out:
            out.append(ticker)
    return out


def update_row(ticker: str, fields: dict[str, str],
               path: Path | None = None) -> bool:
    """Update cells of one ticker's table row (e.g. Last Review, Status,
    Opportunity Status). Rewrites the file atomically. Returns True if changed.

    Only values for known COLUMNS are accepted; unknown keys raise ValueError
    so bots cannot silently corrupt the schema.
    """
    path = path or config.INDEX_PATH
    unknown = set(fields) - set(COLUMNS)
    if unknown:
        raise ValueError(f"unknown index columns: {sorted(unknown)}")
    ticker = ticker.upper()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    changed = False
    for i, line in enumerate(lines):
        rows = parse_index(line)
        if not rows:
            continue
        if rows[0]["Ticker"].upper() != ticker:
            continue
        new_cells = {**rows[0], **{k: str(v) for k, v in fields.items()}}
        lines[i] = "| " + " | ".join(new_cells[c] for c in COLUMNS) + " |"
        changed = True
        break
    if changed:
        _atomic_write(path, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))
    return changed


# Folder names under stock_knowledge/ per status (index.md table uses
# "Owned"/"Watch"; the folders follow the user's tree: own/ and watchlist/)
FOLDER_BY_STATUS = {STATUS_OWNED: "own", STATUS_WATCH: "watchlist"}


def move_ticker_folder(ticker: str, new_status: str,
                       base: Path | None = None) -> Path | None:
    """Move a ticker's research folder to match a status change
    (stock_knowledge/own/ <-> stock_knowledge/watchlist/).

    Returns the destination path, or None when the ticker has no folder yet
    (nothing to move — creation is the session's job). Existing destination
    is never overwritten.
    """
    base = base or config.STOCK_KNOWLEDGE_DIR
    ticker = ticker.upper()
    if new_status not in FOLDER_BY_STATUS:
        raise ValueError(f"new_status must be one of {sorted(FOLDER_BY_STATUS)}")
    for folder in FOLDER_BY_STATUS.values():
        src = base / folder / ticker
        if src.is_dir():
            break
    else:
        return None
    dst_parent = base / FOLDER_BY_STATUS[new_status]
    dst = dst_parent / ticker
    if dst.exists():
        raise FileExistsError(f"destination already exists: {dst}")
    dst_parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return dst


def touch_last_review(ticker: str, path: Path | None = None) -> bool:
    """Set Last Review to today (UTC) for one ticker. Convenience wrapper."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return update_row(ticker, {"Last Review": today}, path=path)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
