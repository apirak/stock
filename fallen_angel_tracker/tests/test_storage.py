"""storage.py — CSV log roundtrips and Markdown report rendering.

All file paths point at pytest tmp dirs via the `tmp_config` fixture.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import analyzer
import storage


# ---------------------------------------------------------------------------
# CSV backend
# ---------------------------------------------------------------------------

def test_read_csv_missing_file_returns_empty(tmp_config):
    assert storage.read_csv() == []


def test_append_and_read_roundtrip_preserves_columns(tmp_config, make_row):
    row = make_row()
    storage.append_csv([row])
    rows = storage.read_csv()
    assert len(rows) == 1
    assert set(rows[0]) == set(analyzer.COLUMNS)
    assert rows[0]["Ticker"] == "TEST"
    assert rows[0]["Moat Impairment Verdict"] == "Pass - Temporary"


def test_append_csv_writes_header_once_and_ignores_extra_keys(tmp_config, make_row):
    row = make_row(**{"junk_column": "ignored"})
    storage.append_csv([row])
    storage.append_csv([make_row({"ticker": "TGT"})])
    lines = tmp_config.CSV_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3                      # header + 2 data rows
    assert lines[0].startswith("Date,Ticker,Company Name")
    assert "junk_column" not in lines[1]


def test_append_daily_rows_empty_is_noop(tmp_config):
    assert storage.append_daily_rows([]) == "nothing to log"
    assert not tmp_config.CSV_LOG_PATH.exists()


def test_append_daily_rows_reports_count_and_relative_path(tmp_config, make_row):
    msg = storage.append_daily_rows([make_row(), make_row({"ticker": "TGT"})])
    assert "logged 2 row(s)" in msg
    assert "data/daily_log.csv" in msg


def test_to_float_variants():
    assert storage.to_float("45.2") == 45.2
    assert storage.to_float("12%") == 12.0
    assert storage.to_float(" 88.0 ") == 88.0
    assert storage.to_float("") is None
    assert storage.to_float(None) is None
    assert storage.to_float("None") is None
    assert storage.to_float("abc") is None
    assert storage.to_float(7) == 7.0


# ---------------------------------------------------------------------------
# log access API
# ---------------------------------------------------------------------------

def test_rows_since_filters_old_and_malformed_dates(make_row):
    today = datetime.now(timezone.utc).date()
    recent = make_row(**{"Date": (today - timedelta(days=1)).isoformat()})
    boundary = make_row(**{"Date": (today - timedelta(days=8)).isoformat()})
    old = make_row(**{"Date": (today - timedelta(days=30)).isoformat()})
    broken = make_row(**{"Date": "not-a-date"})

    out = storage.rows_since([recent, boundary, old, broken], days=8)
    assert recent in out and boundary in out          # cutoff day itself included
    assert old not in out and broken not in out


def test_dedupe_latest_by_ticker_keeps_last_and_uppercases(make_row):
    first = make_row(**{"Market Price ($)": 10.0})
    second = make_row({"ticker": "test"}, **{"Market Price ($)": 20.0})
    latest = storage.dedupe_latest_by_ticker([first, second])
    assert list(latest) == ["TEST"]
    assert latest["TEST"]["Market Price ($)"] == 20.0


def test_rows_for_date_filters_by_date_prefix(tmp_config, make_row):
    row_a = make_row(**{"Date": "2026-09-14"})
    row_b = make_row(**{"Date": "2026-09-01"})
    storage.append_csv([row_a, row_b])
    out = storage.rows_for_date("2026-09-14")
    assert [r["Ticker"] for r in out] == ["TEST"]
    assert all(r["Date"].startswith("2026-09-14") for r in out)


def test_update_rows_for_date_merges_only_matching_rows(tmp_config, make_row):
    d1, d2 = "2026-09-14", "2026-09-13"
    target = make_row(**{"Date": d1})                       # TEST on d1
    other_date = make_row(**{"Date": d2})                   # TEST on d2
    other_ticker = make_row({"ticker": "TGT"}, **{"Date": d1})
    storage.append_csv([target, other_date, other_ticker])

    changed = storage.update_rows_for_date(
        d1, {"TEST": {"Moat Impairment Verdict": "Watch",
                      "Deep-Dive": "updated dive"}})
    assert changed == 1

    by_key = {(r["Date"], r["Ticker"]): r for r in storage.read_csv()}
    assert by_key[(d1, "TEST")]["Moat Impairment Verdict"] == "Watch"
    assert by_key[(d1, "TEST")]["Deep-Dive"] == "updated dive"
    assert by_key[(d2, "TEST")]["Deep-Dive"] != "updated dive"
    assert by_key[(d1, "TGT")]["Moat Impairment Verdict"] == "Pass - Temporary"


def test_update_rows_for_date_unknown_ticker_changes_nothing(tmp_config, make_row):
    storage.append_csv([make_row()])
    before = tmp_config.CSV_LOG_PATH.read_text(encoding="utf-8")
    assert storage.update_rows_for_date("2026-09-14", {"NOPE": {"Deep-Dive": "x"}}) == 0
    assert tmp_config.CSV_LOG_PATH.read_text(encoding="utf-8") == before


def test_first_recommendation_by_ticker_skips_avoid_and_keeps_first(make_row):
    avoid = make_row({"ticker": "AAA"}, **{"Strategic Action": "Avoid"})
    wait = make_row({"ticker": "BBB"}, **{"Strategic Action": "Wait for Next Earnings"})
    accumulate = make_row({"ticker": "AAA"}, **{"Strategic Action": "Accumulate 1st Tranche"})

    firsts = storage.first_recommendation_by_ticker([avoid, wait, accumulate])
    assert set(firsts) == {"BBB", "AAA"}
    assert firsts["AAA"]["Strategic Action"] == "Accumulate 1st Tranche"
    assert firsts["BBB"]["Strategic Action"] == "Wait for Next Earnings"


# ---------------------------------------------------------------------------
# Markdown reports
# ---------------------------------------------------------------------------

def test_write_daily_report_path_and_content(tmp_config, make_row):
    path = storage.write_daily_report([make_row()])
    assert str(path).endswith("reports/daily/2026-09-14.md")
    text = path.read_text(encoding="utf-8")
    assert "# 🦅 Fallen Angel Daily Report — 2026-09-14" in text
    assert "TEST — Test Corp" in text
    assert "✅" in text                      # Pass verdict emoji
    assert "Invalidation Criteria" in text
    assert "stockanalysis.com/stocks/test/" in text


def test_write_daily_report_fail_uses_stop_emoji(tmp_config, make_row):
    row = make_row(**{"Moat Impairment Verdict": "Fail - Value Trap"})
    text = storage.write_daily_report([row]).read_text(encoding="utf-8")
    assert "🚫" in text


def test_write_weekly_report_with_picks(tmp_config, make_digest, make_row):
    digest = make_digest(tracking=[{
        "ticker": "TEST", "rec_date": "2026-09-07", "rec_price": 80.0,
        "price": 88.0, "return_pct": 10.0, "return_1m": 5.0, "return_3m": None,
        "return_6m": -2.0, "latest_verdict": "Pass - Temporary", "flag": "",
    }], notes=["ราคาล่าช้า"])
    path = storage.write_weekly_report(digest)

    assert str(path).endswith("reports/weekly/2026-W37.md")
    text = path.read_text(encoding="utf-8")
    assert "Fallen Angel Weekly Digest — 2026-09-14" in text
    assert "### #1 Test Corp (TEST)" in text
    assert "moat story for TEST" in text
    assert "- criterion one" in text
    assert "**[TEST]" in text                 # tracking table link
    assert "+10.0%" in text and "-2.0%" in text and "n/a" in text
    assert "> ⚠ ราคาล่าช้า" in text
    assert "Lesson Title" in text


def test_write_weekly_report_without_picks_shows_patience_note(tmp_config, make_digest):
    path = storage.write_weekly_report(make_digest(pick_rows=[]))
    text = path.read_text(encoding="utf-8")
    assert "สัปดาห์นี้ไม่มีหุ้นผ่าน Moat Impairment screen" in text
    assert "ยังไม่มีคำแนะนำที่บันทึกไว้" in text
