"""
Shared fixtures for the Fallen Angel Tracker test suite.

Ground rules (enforced here so every test stays offline and hermetic):
  - `_safe_env` (autouse) blanks every secret/network knob on the `config`
    module, so a local `.env` with real SMTP/Discord/LLM credentials can never
    leak into a test run.
  - `tmp_config` redirects every storage path (CSV, reports, pending, analysis)
    into the pytest tmp dir, so tests never touch the real data/ or reports/.
  - Factory fixtures (`make_snapshot`, `make_row`, `make_tracking`,
    `make_digest`) build valid domain objects with a *clean balance sheet and
    a 20% discount* by default; each test overrides only the fields it cares
    about.
"""
from __future__ import annotations

import pytest

import analyzer
import config


@pytest.fixture(autouse=True)
def _safe_env(monkeypatch):
    """No LLM, no SMTP, no Discord — regardless of the developer's local .env."""
    monkeypatch.setattr(config, "LLM_PROVIDER", "none")
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "LLM_MODEL"):
        monkeypatch.setattr(config, key, "")
    monkeypatch.setattr(config, "SMTP_USER", "")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "")
    monkeypatch.setattr(config, "EMAIL_FROM", "")
    monkeypatch.setattr(config, "EMAIL_TO", [])
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL", "")
    monkeypatch.setattr(config, "DISCORD_USERNAME", "")


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Point every storage location at a fresh temp directory."""
    data = tmp_path / "data"
    reports = tmp_path / "reports"
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)   # keep .relative_to() prints working
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "REPORTS_DIR", reports)
    monkeypatch.setattr(config, "DAILY_REPORT_DIR", reports / "daily")
    monkeypatch.setattr(config, "WEEKLY_REPORT_DIR", reports / "weekly")
    monkeypatch.setattr(config, "CSV_LOG_PATH", data / "daily_log.csv")
    monkeypatch.setattr(config, "DAILY_INPUT_FILE", data / "daily_input.txt")
    monkeypatch.setattr(config, "PENDING_DIR", data / "pending")
    monkeypatch.setattr(config, "ANALYSIS_DIR", data / "analysis")
    return config


@pytest.fixture
def make_snapshot():
    """FinancialSnapshot factory: clean balance sheet, 20% discount to fair value."""
    from data_fetcher import FinancialSnapshot

    def _make(**overrides):
        defaults = dict(
            ticker="TEST",
            company="Test Corp",
            price=80.0,
            fair_value=100.0,            # -> discount 0.20 (above MIN 0.15)
            fair_value_source="manual_override",
            market_cap=50_000.0,
            beta=1.1,
            gross_margin=0.60,
            operating_margin=0.20,
            gross_margin_history=[0.60, 0.59, 0.61],      # newest first
            operating_margin_history=[0.20, 0.19, 0.21],
            roic=0.15,
            wacc=0.08,                   # ROIC > WACC
            net_debt_ebitda=1.5,         # < 3.0
            interest_coverage=12.0,      # > 5.0
            interest_expense_negligible=False,
            fcf=5_000.0,
            fcf_yield=0.10,              # > 0.03
            return_1m=-0.05,
            return_3m=-0.12,
            return_6m=-0.20,
            news_headlines=[],
            warnings=[],
            as_of="2026-09-14",
        )
        return FinancialSnapshot(**{**defaults, **overrides})

    return _make


@pytest.fixture
def make_row(make_snapshot):
    """Full Daily_Log row (all COLUMNS keys) built by the real analyze_ticker,
    then overridden per test — e.g. make_row(**{'Moat Impairment Verdict': 'Watch'})."""

    def _make(snapshot_overrides: dict | None = None, **field_overrides):
        snap = make_snapshot(**(snapshot_overrides or {}))
        row = analyzer.analyze_ticker(snap, use_llm=False)
        row.update(field_overrides)
        return row

    return _make


@pytest.fixture
def make_tracking():
    """One weekly tracking-table row with sensible defaults."""

    def _make(ticker="TEST", **overrides):
        row = {
            "ticker": ticker,
            "company": f"{ticker} Corp",
            "rec_date": "2026-09-07",
            "rec_price": 80.0,
            "price": 88.0,
            "return_pct": 10.0,
            "return_1m": 5.0,
            "return_3m": None,
            "return_6m": -2.0,
            "latest_verdict": "Pass - Temporary",
            "flag": "",
        }
        row.update(overrides)
        return row

    return _make


@pytest.fixture
def make_digest(make_row):
    """Weekly digest payload shaped exactly like the one run_weekly/_build_digest produce."""

    def _make(pick_rows=None, tracking=None, notes=None, lesson=None):
        rows = pick_rows if pick_rows is not None else [make_row()]
        picks = [
            {
                "row": row,
                "narrative": {
                    "why_moat_intact": f"moat story for {row['Ticker']}",
                    "market_overreaction": f"panic over {row['Ticker']}",
                    "tranche_strategy": "25-30% first tranche, rest later",
                    "invalidation_criteria": ["criterion one", "criterion two", "criterion three"],
                },
            }
            for row in rows
        ]
        return {
            "week": "2026-W37",
            "date_str": "2026-09-14",
            "picks": picks,
            "tracking": tracking if tracking is not None else [],
            "lesson": lesson or {"title": "Lesson Title", "body": "Lesson body text."},
            "notes": notes if notes is not None else [],
        }

    return _make
