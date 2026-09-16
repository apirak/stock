"""ledger.py — append-only transactions and derived positions (tmp files only)."""
from __future__ import annotations

import pytest

import ledger


# ---------------------------------------------------------------------------
# append_transaction
# ---------------------------------------------------------------------------

def test_append_creates_file_with_template_header(tmp_path):
    path = tmp_path / "ledger.md"
    ledger.append_transaction("2026-09-16", "BUY", "NVDA", shares=2, price=220,
                              reason="test", path=path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Portfolio Ledger")
    assert "## 2026-09-16 — BUY NVDA" in text
    assert "Shares: 2" in text
    assert "Price: 220 USD" in text


def test_append_missing_details_recorded_as_unknown(tmp_path):
    path = ledger.append_transaction("2026-09-16", "BUY", "nvda", path=tmp_path / "l.md")
    text = path.read_text(encoding="utf-8")
    assert "Shares: unknown" in text
    assert "Price: unknown USD" in text
    assert "Fees: unknown" in text


def test_append_appends_without_touching_history(tmp_path):
    path = tmp_path / "ledger.md"
    ledger.append_transaction("2026-09-01", "BUY", "NVDA", shares=1, price=200, path=path)
    before = path.read_text(encoding="utf-8")
    ledger.append_transaction("2026-09-16", "SELL", "NVDA", shares=1, price=240, path=path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith(before)
    assert "## 2026-09-16 — SELL NVDA" in text


def test_append_rejects_unknown_transaction_type(tmp_path):
    with pytest.raises(ValueError):
        ledger.append_transaction("2026-09-16", "YOLO", "NVDA", path=tmp_path / "l.md")


def test_append_rejects_malformed_date(tmp_path):
    with pytest.raises(ValueError):
        ledger.append_transaction("16-09-2026", "BUY", "NVDA", path=tmp_path / "l.md")


# ---------------------------------------------------------------------------
# parse_transactions
# ---------------------------------------------------------------------------

LEDGER_TEXT = """\
# Portfolio Ledger

## 2026-08-29 — BUY NVDA
Shares: 2
Price: 220 USD
Fees: unknown
Reason: Temporary valuation dislocation
Notes: user supplied transaction

## 2026-09-01 — DIVIDEND KKP
Shares: unknown
Price: 0.4 THB
Fees: unknown
Reason: dividend
Notes: auto

not-a-field-line
"""


def test_parse_transactions_reads_entries():
    txs = ledger.parse_transactions(LEDGER_TEXT)
    assert len(txs) == 2
    assert txs[0] == {
        "date": "2026-08-29", "type": "BUY", "ticker": "NVDA",
        "shares": 2.0, "price": 220.0, "currency": "USD", "fees": None,
        "reason": "Temporary valuation dislocation", "notes": "user supplied transaction",
    }
    assert txs[1]["type"] == "DIVIDEND"
    assert txs[1]["shares"] is None and txs[1]["currency"] == "THB"


def test_parse_transactions_is_case_insensitive_on_type():
    txs = ledger.parse_transactions("## 2026-09-01 — buy NVDA\nShares: 1\n")
    assert txs[0]["type"] == "BUY"


# ---------------------------------------------------------------------------
# net_positions
# ---------------------------------------------------------------------------

def test_net_positions_moving_average_cost():
    txs = [
        {"date": "2026-08-01", "type": "BUY", "ticker": "NVDA", "shares": 2.0, "price": 100.0},
        {"date": "2026-08-15", "type": "BUY", "ticker": "NVDA", "shares": 1.0, "price": 130.0},
    ]
    pos = ledger.net_positions(txs)
    assert pos["NVDA"]["shares"] == 3.0
    assert pos["NVDA"]["avg_cost"] == pytest.approx(110.0)
    assert pos["NVDA"]["last_date"] == "2026-08-15"


def test_net_positions_sell_reduces_at_book_value():
    txs = [
        {"date": "2026-08-01", "type": "BUY", "ticker": "NVDA", "shares": 2.0, "price": 100.0},
        {"date": "2026-09-01", "type": "SELL", "ticker": "NVDA", "shares": 1.0, "price": 150.0},
    ]
    pos = ledger.net_positions(txs)
    assert pos["NVDA"]["shares"] == 1.0
    assert pos["NVDA"]["avg_cost"] == pytest.approx(100.0)


def test_net_positions_full_exit_drops_the_ticker():
    txs = [
        {"date": "2026-08-01", "type": "BUY", "ticker": "NVDA", "shares": 2.0, "price": 100.0},
        {"date": "2026-09-01", "type": "SELL", "ticker": "NVDA", "shares": 2.0, "price": 90.0},
    ]
    assert ledger.net_positions(txs) == {}


def test_net_positions_ignores_income_events_and_unknown_shares():
    txs = [
        {"date": "2026-08-01", "type": "DIVIDEND", "ticker": "NVDA", "shares": None, "price": 0.4},
        {"date": "2026-08-02", "type": "BUY", "ticker": "KKP", "shares": None, "price": None},
        {"date": "2026-08-03", "type": "BUY", "ticker": "MSFT", "shares": 3.0, "price": 400.0},
    ]
    pos = ledger.net_positions(txs)
    assert set(pos) == {"MSFT"}


def test_net_positions_roundtrip_from_file(tmp_path):
    path = tmp_path / "ledger.md"
    ledger.append_transaction("2026-08-01", "BUY", "NVDA", shares=2, price=100, path=path)
    pos = ledger.net_positions(ledger.read_transactions(path))
    assert pos["NVDA"]["shares"] == 2.0
