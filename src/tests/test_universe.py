"""universe.py — index.md parsing, filtering, and updates (all against tmp files)."""
from __future__ import annotations

import pytest

import universe

TABLE = """\
# VI Research Watch List — Index

| Ticker | Company | Market | Status | Research Priority | Opportunity Status | Last Review |
|---|---|---|---|---|---|---|
| NVDA | NVIDIA Corp | NASDAQ (US) | Owned | High | TBD | 2026-08-29 |
| MSFT | Microsoft Corp | NASDAQ (US) | Owned | High | TBD | 2026-08-29 |
| AAPL | Apple Inc | NASDAQ (US) | Watch | Medium | TBD | 2026-08-29 |
| KKP | Kiatnakin Phatra Bank PCL | SET (Thailand) | Watch | Low | TBD | 2026-08-29 |

## Notes
- some prose that must not parse as a row
"""


@pytest.fixture
def index_file(tmp_path):
    path = tmp_path / "index.md"
    path.write_text(TABLE, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# parse_index / read_index
# ---------------------------------------------------------------------------

def test_parse_index_reads_all_rows():
    rows = universe.parse_index(TABLE)
    assert [r["Ticker"] for r in rows] == ["NVDA", "MSFT", "AAPL", "KKP"]
    assert rows[0]["Status"] == "Owned"
    assert rows[2]["Market"] == "NASDAQ (US)"


def test_parse_index_skips_header_separator_and_prose():
    rows = universe.parse_index(TABLE)
    assert all(r["Ticker"] not in ("Ticker", "---") for r in rows)
    assert all("prose" not in r["Ticker"] for r in rows)


def test_parse_index_ignores_malformed_rows():
    rows = universe.parse_index("| NVDA | missing columns |\n")
    assert rows == []


def test_read_index_missing_file_returns_empty(tmp_path):
    assert universe.read_index(tmp_path / "nope.md") == []


# ---------------------------------------------------------------------------
# tickers
# ---------------------------------------------------------------------------

def test_tickers_preserves_index_order(index_file):
    assert universe.tickers(universe.read_index(index_file)) == ["NVDA", "MSFT", "AAPL", "KKP"]


def test_tickers_filter_by_status(index_file):
    rows = universe.read_index(index_file)
    assert universe.tickers(rows, status="Owned") == ["NVDA", "MSFT"]
    assert universe.tickers(rows, status="Watch") == ["AAPL", "KKP"]


def test_tickers_automated_only_drops_thai_set(index_file):
    rows = universe.read_index(index_file)
    assert universe.tickers(rows, automated_only=True) == ["NVDA", "MSFT", "AAPL"]


# ---------------------------------------------------------------------------
# update_row / touch_last_review
# ---------------------------------------------------------------------------

def test_update_row_changes_only_target_cells(index_file):
    assert universe.update_row("aapl", {"Status": "Owned", "Last Review": "2026-09-16"},
                               path=index_file) is True
    rows = universe.read_index(index_file)
    assert rows[2]["Status"] == "Owned"
    assert rows[2]["Last Review"] == "2026-09-16"
    assert rows[0]["Status"] == "Owned"          # untouched
    assert rows[3]["Status"] == "Watch"


def test_update_row_unknown_ticker_changes_nothing(index_file):
    before = index_file.read_text(encoding="utf-8")
    assert universe.update_row("NOPE", {"Status": "Owned"}, path=index_file) is False
    assert index_file.read_text(encoding="utf-8") == before


def test_update_row_rejects_unknown_columns(index_file):
    with pytest.raises(ValueError):
        universe.update_row("NVDA", {"Not A Column": "x"}, path=index_file)


def test_touch_last_review_writes_today(index_file):
    assert universe.touch_last_review("MSFT", path=index_file) is True
    row = universe.read_index(index_file)[1]
    assert row["Last Review"] >= "2026-01-01"    # a plausible date was written


# ---------------------------------------------------------------------------
# move_ticker_folder
# ---------------------------------------------------------------------------

def test_move_ticker_folder_moves_owned_to_watchlist(tmp_path):
    (tmp_path / "own" / "NVDA").mkdir(parents=True)
    (tmp_path / "own" / "NVDA" / "NVDA_overall.md").write_text("x", encoding="utf-8")

    dst = universe.move_ticker_folder("NVDA", "Watch", base=tmp_path)

    assert dst == tmp_path / "watchlist" / "NVDA"
    assert dst.is_dir() and (dst / "NVDA_overall.md").exists()
    assert not (tmp_path / "own" / "NVDA").exists()


def test_move_ticker_folder_returns_none_without_folder(tmp_path):
    assert universe.move_ticker_folder("NOPE", "Owned", base=tmp_path) is None


def test_move_ticker_folder_refuses_to_overwrite(tmp_path):
    (tmp_path / "own" / "NVDA").mkdir(parents=True)
    (tmp_path / "watchlist" / "NVDA").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        universe.move_ticker_folder("NVDA", "Watch", base=tmp_path)
