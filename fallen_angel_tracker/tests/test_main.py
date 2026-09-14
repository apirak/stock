"""main.py — pipeline orchestration for daily / weekly / finalize.

External market data (yfinance) is monkeypatched; everything else runs for
real against tmp-dir storage, so the file contract (CSV -> pending JSON ->
analysis JSON -> merged CSV + reports) is exercised end to end.
"""
from __future__ import annotations

import argparse
import json

import pytest

import config
import data_fetcher
import main
import storage


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(mode="daily", tickers="", dry_run=False, use_api_llm=False,
                    date="", week="", weekly=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def test_resolve_tickers_arg_wins_over_everything(tmp_config):
    assert main._resolve_tickers(" unh , tgt ,") == ["UNH", "TGT"]


def test_resolve_tickers_reads_daily_input_file(tmp_config):
    tmp_config.DAILY_INPUT_FILE.parent.mkdir(parents=True)
    tmp_config.DAILY_INPUT_FILE.write_text("# comment\n\nunh\ntgt\n", encoding="utf-8")
    assert main._resolve_tickers(None) == ["UNH", "TGT"]


def test_resolve_tickers_falls_back_to_watchlist(tmp_config, monkeypatch):
    monkeypatch.setattr(config, "WATCHLIST", ["DIS", "NKE"])
    assert main._resolve_tickers("") == ["DIS", "NKE"]


def test_deterioration_flag_levels(make_row):
    assert "Value Trap" in main._deterioration_flag(
        make_row(**{"Moat Impairment Verdict": "Fail - Value Trap"}))
    assert "หนี้สุทธิ 4.0x" in main._deterioration_flag(
        make_row(**{"Net Debt / EBITDA": 4.0}))
    assert "Coverage 3.0x" in main._deterioration_flag(
        make_row(**{"Interest Coverage Ratio": 3.0}))
    assert "Watch" in main._deterioration_flag(
        make_row(**{"Moat Impairment Verdict": "Watch"}))
    assert main._deterioration_flag(make_row()) == ""


def test_write_json_creates_missing_parents(tmp_config):
    path = tmp_config.PENDING_DIR / "nested" / "file.json"
    main._write_json(path, {"a": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}


# ---------------------------------------------------------------------------
# build_tracking
# ---------------------------------------------------------------------------

def test_build_tracking_computes_returns_against_first_recommendation(
        make_row, monkeypatch):
    first = make_row(**{"Date": "2026-09-07",
                        "Strategic Action": "Wait for Next Earnings"})
    latest = make_row(**{"Date": "2026-09-14",
                         "Moat Impairment Verdict": "Watch"})
    monkeypatch.setattr(
        data_fetcher, "fetch_price_stats",
        lambda ticker: {"price": 88.0, "return_1m": 0.05,
                        "return_3m": None, "return_6m": -0.1})

    tracking, notes = main.build_tracking([first, latest])

    assert notes == []
    row = tracking[0]
    assert row["ticker"] == "TEST"
    assert row["rec_date"] == "2026-09-07"
    assert row["rec_price"] == 80.0
    assert row["price"] == 88.0
    assert row["return_pct"] == pytest.approx(10.0)
    assert row["return_1m"] == pytest.approx(5.0)
    assert row["return_3m"] is None
    assert row["latest_verdict"] == "Watch"
    assert "Watch" in row["flag"]


def test_build_tracking_notes_failed_price_fetch(make_row, monkeypatch):
    row = make_row()

    def boom(ticker):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(data_fetcher, "fetch_price_stats", boom)
    tracking, notes = main.build_tracking([row])
    assert tracking == []
    assert len(notes) == 1 and "TEST" in notes[0]


def test_build_tracking_falls_back_to_recommendation_price(make_row, monkeypatch):
    row = make_row()
    monkeypatch.setattr(
        data_fetcher, "fetch_price_stats",
        lambda ticker: {"price": None, "return_1m": None,
                        "return_3m": None, "return_6m": None})
    tracking, _ = main.build_tracking([row])
    assert tracking[0]["price"] == 80.0
    assert tracking[0]["return_pct"] == 0.0


# ---------------------------------------------------------------------------
# _build_digest
# ---------------------------------------------------------------------------

def test_build_digest_prefers_analysis_over_fallbacks(make_row):
    row = make_row()
    payload = {"week": "2026-W37", "date_str": "2026-09-14", "picks": [row],
               "tracking": [], "lesson": {"title": "t", "body": "b"},
               "notes": ["n"]}
    analysis = {
        "picks": [{"ticker": "TEST", "why_moat_intact": "AI moat text",
                   "tranche_strategy": "AI tranche",
                   "invalidation_criteria": ["i1", "i2", "i3"]}],
        "lesson": {"title": "AI Lesson", "body": "AI body"},
    }
    digest = main._build_digest(payload, analysis)

    n = digest["picks"][0]["narrative"]
    assert n["why_moat_intact"] == "AI moat text"
    assert n["tranche_strategy"] == "AI tranche"
    assert n["invalidation_criteria"] == ["i1", "i2", "i3"]
    assert n["market_overreaction"] == row["Core Headwinds / Catalyst"]  # fell back
    assert digest["lesson"] == {"title": "AI Lesson", "body": "AI body"}
    assert digest["notes"] == ["n"]


def test_build_digest_without_analysis_uses_row_text(make_row):
    row = make_row(**{"Deep-Dive": "row dive", "Tranche Plan": "row plan"})
    payload = {"week": "2026-W37", "date_str": "2026-09-14", "picks": [row],
               "tracking": [], "lesson": {"title": "t", "body": "b"}, "notes": []}
    digest = main._build_digest(payload, {})
    n = digest["picks"][0]["narrative"]
    assert n["why_moat_intact"] == "row dive"
    assert n["tranche_strategy"] == "row plan"
    assert n["invalidation_criteria"]  # split out of the row


# ---------------------------------------------------------------------------
# run_daily
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_fetch_snapshot(monkeypatch, make_snapshot):
    def _install(raise_for=()):
        def fetch(ticker, fair_value_override=None, include_news=True):
            if ticker in raise_for:
                raise RuntimeError(f"{ticker} is broken")
            return make_snapshot(ticker=ticker)

        monkeypatch.setattr(data_fetcher, "fetch_snapshot", fetch)
    return _install


def test_run_daily_dry_run_prints_without_writing(tmp_config, fake_fetch_snapshot,
                                                  capsys):
    fake_fetch_snapshot()
    rc = main.run_daily(_args(tickers="TEST", dry_run=True))
    out = capsys.readouterr().out
    assert rc == 0
    assert "TEST" in out and "dry run" in out
    assert not tmp_config.CSV_LOG_PATH.exists()
    assert not tmp_config.PENDING_DIR.exists()


def test_run_daily_one_bad_ticker_does_not_kill_the_run(tmp_config,
                                                        fake_fetch_snapshot,
                                                        capsys):
    fake_fetch_snapshot(raise_for=("BAD",))
    rc = main.run_daily(_args(tickers="BAD,GOOD"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "BAD" in out and "FAILED" in out
    assert len(storage.read_csv()) == 1          # only GOOD logged


def test_run_daily_all_tickers_failing_returns_error(tmp_config,
                                                     fake_fetch_snapshot):
    fake_fetch_snapshot(raise_for=("BAD1", "BAD2"))
    assert main.run_daily(_args(tickers="BAD1,BAD2")) == 1
    assert not tmp_config.CSV_LOG_PATH.exists()


def test_run_daily_writes_csv_report_and_pending_file(tmp_config,
                                                      fake_fetch_snapshot):
    fake_fetch_snapshot()
    rc = main.run_daily(_args(tickers="TEST"))
    assert rc == 0

    rows = storage.read_csv()
    assert len(rows) == 1 and rows[0]["Ticker"] == "TEST"

    today = main._today()
    report = tmp_config.DAILY_REPORT_DIR / f"{today}.md"
    pending = tmp_config.PENDING_DIR / f"daily-{today}.json"
    assert report.exists()
    assert pending.exists()

    payload = json.loads(pending.read_text(encoding="utf-8"))
    assert payload["date"] == today
    assert payload["tickers"][0]["ticker"] == "TEST"
    assert "Moat Impairment Test" in payload["tickers"][0]["task"]


# ---------------------------------------------------------------------------
# run_weekly
# ---------------------------------------------------------------------------

def test_run_weekly_writes_digest_report_and_pending(tmp_config, make_row,
                                                     monkeypatch):
    storage.append_csv([make_row(**{"Date": main._today()})])
    monkeypatch.setattr(
        data_fetcher, "fetch_price_stats",
        lambda ticker: {"price": 85.0, "return_1m": 0.01,
                        "return_3m": None, "return_6m": None})

    rc = main.run_weekly(_args(mode="weekly"))
    assert rc == 0

    week = main._week_label()
    report = tmp_config.WEEKLY_REPORT_DIR / f"{week}.md"
    pending = tmp_config.PENDING_DIR / f"weekly-{week}.json"
    assert report.exists()
    assert pending.exists()

    payload = json.loads(pending.read_text(encoding="utf-8"))
    assert payload["week"] == week
    assert payload["picks"][0]["Ticker"] == "TEST"
    assert payload["lesson"]["title"]            # seed lesson for the harness

    report_text = report.read_text(encoding="utf-8")
    assert "Test Corp (TEST)" in report_text     # pick rendered in the digest
    assert "**[TEST]" in report_text             # tracking table rendered


def test_run_weekly_with_no_history_still_renders(tmp_config):
    rc = main.run_weekly(_args(mode="weekly"))
    assert rc == 0
    report = tmp_config.WEEKLY_REPORT_DIR / f"{main._week_label()}.md"
    assert "สัปดาห์นี้ไม่มีหุ้นผ่าน" in report.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# finalize: daily
# ---------------------------------------------------------------------------

def _seed_analysis(tmp_config, date, ticker="TEST"):
    tmp_config.PENDING_DIR.mkdir(parents=True, exist_ok=True)
    tmp_config.ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    (tmp_config.PENDING_DIR / f"daily-{date}.json").write_text("{}", encoding="utf-8")
    analysis = {"tickers": [{
        "ticker": ticker,
        "verdict": "Watch",
        "headwind_category": "Structural Damage",
        "moat_sources": ["Network Effect"],
        "core_headwinds": "churn accelerating",
        "deep_dive": "AI deep dive",
        "tranche_plan": "AI tranche plan",
        "invalidation_criteria": ["i1", "i2", "i3"],
        "suggested_position_cap_pct": 50,
    }]}
    (tmp_config.ANALYSIS_DIR / f"daily-{date}.json").write_text(
        json.dumps(analysis), encoding="utf-8")


def test_finalize_daily_merges_analysis_into_csv_and_report(tmp_config, make_row,
                                                            capsys):
    date = main._today()
    storage.append_csv([make_row(**{"Date": date})])
    _seed_analysis(tmp_config, date)

    rc = main.run_finalize(_args(mode="finalize", date=date))
    assert rc == 0

    row = storage.rows_for_date(date)[0]
    assert row["Moat Impairment Verdict"] == "Watch"
    assert row["Strategic Action"] == "Wait for Next Earnings"
    assert row["Headwind Category"] == "Structural Damage"
    assert row["Moat Sources"] == "Network Effect"
    assert row["Deep-Dive"] == "AI deep dive"
    assert row["Invalidation Criteria"] == "i1 | i2 | i3"
    assert row["Suggested Position Cap (%)"] == "8.0"     # clamped to cap max

    report_text = (tmp_config.DAILY_REPORT_DIR / f"{date}.md").read_text(encoding="utf-8")
    assert "AI deep dive" in report_text


def test_finalize_daily_unknown_ticker_is_skipped(tmp_config, make_row, capsys):
    date = main._today()
    storage.append_csv([make_row(**{"Date": date})])
    _seed_analysis(tmp_config, date, ticker="NOPE")

    rc = main.run_finalize(_args(mode="finalize", date=date))
    out = capsys.readouterr().out
    assert rc == 1                                # nothing usable -> CSV unchanged
    assert "skipping NOPE" in out
    row = storage.rows_for_date(date)[0]
    assert row["Moat Impairment Verdict"] == "Pass - Temporary"


def test_finalize_daily_missing_pending_file_fails(tmp_config):
    assert main.run_finalize(_args(mode="finalize", date="2026-09-14")) == 1


def test_finalize_daily_missing_analysis_file_fails(tmp_config, make_row, capsys):
    date = main._today()
    storage.append_csv([make_row(**{"Date": date})])
    tmp_config.PENDING_DIR.mkdir(parents=True, exist_ok=True)
    (tmp_config.PENDING_DIR / f"daily-{date}.json").write_text("{}", encoding="utf-8")
    rc = main.run_finalize(_args(mode="finalize", date=date))
    assert rc == 1
    assert "no analysis file" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# finalize: weekly
# ---------------------------------------------------------------------------

def _seed_weekly_pending(tmp_config, make_row, week, date_str):
    tmp_config.PENDING_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"week": week, "date_str": date_str, "picks": [make_row()],
               "tracking": [], "lesson": {"title": "t", "body": "b"}, "notes": []}
    (tmp_config.PENDING_DIR / f"weekly-{week}.json").write_text(
        json.dumps(payload), encoding="utf-8")


def test_finalize_weekly_dry_run_writes_preview_only(tmp_config, make_row, capsys):
    week = main._week_label()
    _seed_weekly_pending(tmp_config, make_row, week, "2026-09-14")

    rc = main.run_finalize(_args(mode="finalize", weekly=True, week=week,
                                 dry_run=True))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Fallen Angel Weekly Digest" in out               # subject printed

    preview = tmp_config.OUTPUT_DIR / "weekly_preview_2026-09-14.html"
    assert preview.exists()
    assert "#1 Test Corp (TEST)" in preview.read_text(encoding="utf-8")


def test_finalize_weekly_without_delivery_channels_succeeds(tmp_config, make_row):
    week = main._week_label()
    _seed_weekly_pending(tmp_config, make_row, week, "2026-09-14")

    rc = main.run_finalize(_args(mode="finalize", weekly=True, week=week))
    assert rc == 0
    assert (tmp_config.WEEKLY_REPORT_DIR / f"{week}.md").exists()


def test_finalize_weekly_missing_pending_fails(tmp_config):
    assert main.run_finalize(_args(mode="finalize", weekly=True, week="2026-W37")) == 1
