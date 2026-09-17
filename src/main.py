"""
Entrypoint for the Falling Angle watchlist system.

Hybrid architecture (zero LLM API cost — this codebase contains no LLM calls):
  1. `--mode daily` / `--mode weekly` : Python collects market data, runs the
     deterministic screen, logs to CSV/MD and writes a PENDING file under
     src/data/pending/.
  2. A ZCode automation session reads the pending file, performs the Moat
     Impairment Test with its own model, and writes an analysis JSON under
     src/data/analysis/.
  3. `--mode finalize` merges the analysis into the CSV, regenerates the
     Markdown report and delivers to Discord (weekly: + email if configured).

Usage:
    python main.py --mode daily  [--tickers NVDA,MSFT] [--dry-run]
    python main.py --mode weekly [--dry-run]
    python main.py --mode finalize [--weekly] [--date YYYY-MM-DD] [--week YYYY-Www]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
from datetime import datetime, timedelta, timezone

import analyzer
import config
import data_fetcher
import discord_notifier
import storage
import universe
from mailer import build_weekly_email, send_email


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")



def _rel(path) -> str:
    """Pretty path for logs: relative to the repo root when possible."""
    try:
        return str(Path(path).relative_to(config.REPO_ROOT))
    except ValueError:
        return str(path)


def _week_label() -> str:
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve_tickers(args_tickers: str | None) -> list[str]:
    """Priority: --tickers > daily_input.txt > WATCHLIST env > index.md universe.

    The index.md fallback (automated_only) excludes manual-research-only
    tickers (Thai SET DRs), so the daily fetch never burns calls on them.
    """
    if args_tickers:
        return [t.strip().upper() for t in args_tickers.split(",") if t.strip()]
    if config.DAILY_INPUT_FILE.exists():
        lines = [
            line.strip().upper()
            for line in config.DAILY_INPUT_FILE.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if lines:
            return lines
    if config.WATCHLIST:
        return list(config.WATCHLIST)
    return universe.tickers(automated_only=True)


def _print_row_summary(row: dict) -> None:
    print(
        f"  {row['Ticker']:<6} price=${row['Market Price ($)'] or 'n/a':<9}"
        f" discount={row['Discount (%)'] or 'n/a'}%"
        f" | {row['Moat Impairment Verdict']:<18}"
        f" | {row['Strategic Action']}"
    )


def _write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# daily pipeline:  collect -> (harness analyzes) -> finalize
# ---------------------------------------------------------------------------

def run_daily(args: argparse.Namespace) -> int:
    today = _today()
    tickers = _resolve_tickers(args.tickers)
    print(f"[daily] analyzing {len(tickers)} ticker(s) rule-based (no LLM cost): {', '.join(tickers)}")

    rows: list[dict] = []
    pending: list[dict] = []
    failures = 0
    for ticker in tickers:
        try:
            snap = data_fetcher.fetch_snapshot(
                ticker, fair_value_override=config.FAIR_VALUE_OVERRIDES.get(ticker)
            )
            row = analyzer.analyze_ticker(snap)
            rows.append(row)
            pending.append(analyzer.pending_entry(snap, row))
            _print_row_summary(row)
        except Exception as exc:  # noqa: BLE001 - one bad ticker must not kill the run
            failures += 1
            print(f"  {ticker:<6} FAILED: {exc}")

    if not rows:
        print("[daily] no rows produced")
        return 1

    if args.dry_run:
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=analyzer.COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        print("\n--- dry run: rows that would be logged ---")
        print(buffer.getvalue())
        return 0

    print("[daily] " + storage.append_daily_rows(rows))
    report_path = storage.write_daily_report(rows)
    print(f"[daily] markdown report: {_rel(report_path)}")

    if pending:
        pending_path = config.PENDING_DIR / f"daily-{today}.json"
        _write_json(pending_path, {"date": today, "tickers": pending})
        print(
            f"[daily] pending analysis file: {_rel(pending_path)}\n"
            f"[daily] next step (ZCode harness): analyze it and write "
            f"src/data/analysis/daily-{today}.json, then run: python main.py --mode finalize"
        )
    return 1 if failures and not rows else 0


# ---------------------------------------------------------------------------
# finalize: merge the harness analysis into CSV + reports
# ---------------------------------------------------------------------------

def _finalize_daily(args: argparse.Namespace) -> int:
    date = args.date or _today()
    pending_path = config.PENDING_DIR / f"daily-{date}.json"
    analysis_path = config.ANALYSIS_DIR / f"daily-{date}.json"
    if not pending_path.exists():
        print(f"[finalize] no pending file: {_rel(pending_path)}")
        return 1
    if not analysis_path.exists():
        print(
            f"[finalize] no analysis file yet: {_rel(analysis_path)}\n"
            "[finalize] run the ZCode analysis step first, or re-run finalize afterwards."
        )
        return 1

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    rows_by_ticker = {r["Ticker"]: r for r in storage.rows_for_date(date)}

    updates: dict[str, dict] = {}
    for item in analysis.get("tickers", []):
        ticker = str(item.get("ticker", "")).upper()
        row = rows_by_ticker.get(ticker)
        if not row:
            print(f"[finalize] skipping {ticker or '?'}: no row logged on {date}")
            continue
        upd: dict[str, str] = {}
        verdict = item.get("verdict")
        if verdict in analyzer.VALID_VERDICTS:
            upd["Moat Impairment Verdict"] = verdict
            upd["Strategic Action"] = analyzer.action_from_row(verdict, row)
        if item.get("headwind_category"):
            upd["Headwind Category"] = str(item["headwind_category"])
        if item.get("moat_sources"):
            srcs = item["moat_sources"]
            upd["Moat Sources"] = ", ".join(srcs) if isinstance(srcs, list) else str(srcs)
        if item.get("core_headwinds"):
            upd["Core Headwinds / Catalyst"] = str(item["core_headwinds"])
        if item.get("deep_dive"):
            upd["Deep-Dive"] = str(item["deep_dive"])
        if item.get("tranche_plan"):
            upd["Tranche Plan"] = str(item["tranche_plan"])
        if item.get("invalidation_criteria"):
            crit = item["invalidation_criteria"]
            upd["Invalidation Criteria"] = (
                " | ".join(crit) if isinstance(crit, list) else str(crit)
            )
        try:
            cap = float(item.get("suggested_position_cap_pct"))
            upd["Suggested Position Cap (%)"] = min(
                max(cap, config.POSITION_CAP_MIN), config.POSITION_CAP_MAX
            )
        except (TypeError, ValueError):
            pass
        if upd:
            updates[ticker] = upd

    if not updates:
        print("[finalize] analysis file contained no usable entries; CSV unchanged")
        return 1

    changed = storage.update_rows_for_date(date, updates)
    rows = storage.rows_for_date(date)
    report_path = storage.write_daily_report(rows)
    print(f"[finalize] merged {changed} row(s) for {date}")
    for row in rows:
        _print_row_summary(row)
    print(f"[finalize] markdown report regenerated: {_rel(report_path)}")
    discord_failed = not discord_notifier.send_daily_summary(rows) and config.discord_ready()
    if discord_failed:
        print("[finalize] ERROR: daily Discord delivery failed")
        return 1
    return 0


# ---------------------------------------------------------------------------
# weekly pipeline:  build -> (harness narrates) -> finalize
# ---------------------------------------------------------------------------

def _deterioration_flag(latest: dict) -> str:
    """Thai alert strings — these surface only in the weekly digest."""
    verdict = str(latest.get("Moat Impairment Verdict", ""))
    if "Fail" in verdict:
        return "⚠ Verdict FAIL — เสี่ยงเป็น Value Trap"
    leverage = storage.to_float(latest.get("Net Debt / EBITDA"))
    coverage = storage.to_float(latest.get("Interest Coverage Ratio"))
    if leverage is not None and leverage > config.MAX_NET_DEBT_EBITDA:
        return f"⚠ หนี้สุทธิ {leverage:.1f}x EBITDA เกินเกณฑ์ {config.MAX_NET_DEBT_EBITDA:.0f}x"
    if coverage is not None and coverage < config.MIN_INTEREST_COVERAGE:
        return f"⚠ Coverage {coverage:.1f}x ต่ำกว่าเกณฑ์ {config.MIN_INTEREST_COVERAGE:.0f}x"
    if "Watch" in verdict:
        return "△ Watch — พื้นฐานเริ่มอ่อนแรง ติดตามต่อ"
    return ""


def build_tracking(all_rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Return (tracking_rows, notes). Anchor = first actionable row per ticker.

    Uses the accumulated daily history (rows_by_ticker) to compute verdict
    drift and the 7-day discount trend — both impossible without daily rows.
    """
    firsts = storage.first_recommendation_by_ticker(all_rows)
    rows_by_ticker: dict[str, list[dict]] = {}
    for row in all_rows:
        rows_by_ticker.setdefault(str(row.get("Ticker", "")).upper(), []).append(row)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).date()

    def row_date(row: dict):
        try:
            return datetime.strptime(str(row.get("Date", ""))[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    tracking: list[dict] = []
    notes: list[str] = []
    for ticker, first in sorted(firsts.items()):
        try:
            stats = data_fetcher.fetch_price_stats(ticker)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{ticker}: ดึงราคาไม่สำเร็จ ({exc})")
            continue
        ticker_rows = rows_by_ticker.get(ticker, [])
        latest = ticker_rows[-1] if ticker_rows else first
        history = ticker_rows[:-1]  # everything before the latest row
        drift = analyzer.verdict_drift(history, str(latest.get("Moat Impairment Verdict", "")))

        week_rows = [r for r in ticker_rows if (rd := row_date(r)) and rd >= cutoff]
        d_latest = storage.to_float(latest.get("Discount (%)"))
        d_start = storage.to_float(week_rows[0].get("Discount (%)")) if week_rows else None
        if d_latest is None:
            discount_trend, discount_now, discount_delta = "", "", ""
        elif d_start is None or abs(d_latest - d_start) < 0.05:
            discount_trend, discount_now, discount_delta = f"{d_latest:.1f}%", f"{d_latest:.1f}", ""
        else:
            discount_trend = f"{d_start:.1f}% → {d_latest:.1f}% (Δ{d_latest - d_start:+.1f})"
            discount_now, discount_delta = f"{d_latest:.1f}", f"{d_latest - d_start:+.1f}"

        rec_price = storage.to_float(first.get("Market Price ($)"))
        price = stats["price"] or rec_price
        return_pct = (price / rec_price - 1) * 100 if price and rec_price else None
        tracking.append({
            "ticker": ticker,
            "company": first.get("Company Name", ticker),
            "rec_date": str(first.get("Date", ""))[:10],
            "rec_price": rec_price if rec_price is not None else "n/a",
            "price": round(price, 2) if price else "n/a",
            "return_pct": return_pct,
            "return_1m": stats["return_1m"] * 100 if stats["return_1m"] is not None else None,
            "return_3m": stats["return_3m"] * 100 if stats["return_3m"] is not None else None,
            "return_6m": stats["return_6m"] * 100 if stats["return_6m"] is not None else None,
            "discount_trend": discount_trend,
            "discount_now": discount_now,
            "discount_delta": discount_delta,
            "drift": drift,
            "latest_verdict": latest.get("Moat Impairment Verdict", "n/a"),
            "flag": _deterioration_flag(latest),
        })
    return tracking, notes


def _coverage_notes(all_rows: list[dict], days: int = 7) -> list[str]:
    """Flag weekdays in the last `days` days with no daily rows — the weekly
    digest then knows where the accumulated history has gaps."""
    have = {str(r.get("Date", ""))[:10] for r in all_rows}
    today = datetime.now(timezone.utc).date()
    thai_days = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]
    missing = []
    for i in range(1, days + 1):
        d = today - timedelta(days=i)
        if d.weekday() < 5 and d.isoformat() not in have:
            missing.append(f"{d.isoformat()} ({thai_days[d.weekday()]})")
    if not missing:
        return []
    shown = ", ".join(missing[:5]) + (f" และอีก {len(missing) - 5} วัน" if len(missing) > 5 else "")
    return [f"ข้อมูล daily ขาดวัน: {shown} — อาจเกิดจากเครื่องปิด/automation ไม่ได้รัน "
            "หรือเป็นวันหยุดตลาดสหรัฐ"]


def _build_digest(payload: dict, analysis: dict) -> dict:
    """Assemble the weekly digest payload; harness analysis overrides fallbacks."""
    pick_analysis = {
        str(p.get("ticker", "")).upper(): p for p in analysis.get("picks", [])
    }
    picks_payload = []
    for row in payload["picks"]:
        a = pick_analysis.get(row["Ticker"], {})
        invalidation = a.get("invalidation_criteria")
        picks_payload.append({
            "row": row,
            "narrative": {
                "why_moat_intact": a.get("why_moat_intact") or row.get("Deep-Dive", ""),
                "market_overreaction": a.get("market_overreaction")
                or row.get("Core Headwinds / Catalyst", ""),
                "tranche_strategy": a.get("tranche_strategy")
                or row.get("Tranche Plan", "") or analyzer.fallback_tranche_plan(),
                "invalidation_criteria": (
                    invalidation if isinstance(invalidation, list) and invalidation
                    else [c for c in str(row.get("Invalidation Criteria", "")).split(" | ") if c]
                ),
            },
        })
    lesson = analysis.get("lesson") or payload["lesson"]
    return {
        "week": payload.get("week", ""),
        "date_str": payload["date_str"],
        "picks": picks_payload,
        "tracking": payload["tracking"],
        "lesson": lesson,
        "notes": payload.get("notes", []),
    }


def run_weekly(args: argparse.Namespace) -> int:
    today = _today()
    week = _week_label()
    print(f"[weekly] building digest for {today} ({week})")

    all_rows = storage.read_log_rows()
    print(f"[weekly] loaded {len(all_rows)} historical row(s)")

    recent = storage.rows_since(all_rows, config.LOOKBACK_DAYS_FOR_WEEKLY)
    print(f"[weekly] {len(recent)} row(s) in the last {config.LOOKBACK_DAYS_FOR_WEEKLY} days")

    picks = analyzer.select_top_picks(recent, limit=2)
    tracking, notes = ([], [])
    if all_rows:
        tracking, notes = build_tracking(all_rows)
        notes = _coverage_notes(all_rows) + notes

    payload = {
        "week": week,
        "date_str": today,
        "picks": picks,
        "tracking": tracking,
        "lesson": analyzer.generate_mini_lesson(),  # seed topic for the harness
        "notes": notes,
    }
    digest = _build_digest(payload, {})
    report_path = storage.write_weekly_report(digest)
    pending_path = config.PENDING_DIR / f"weekly-{week}.json"
    _write_json(pending_path, payload)
    for pick in picks:
        print(f"  candidate: {pick['Ticker']} ({pick['Moat Impairment Verdict']})")
    print(f"[weekly] markdown digest (fallback text): {_rel(report_path)}")
    print(
        f"[weekly] pending narrative file: {_rel(pending_path)}\n"
        f"[weekly] next step (ZCode harness): write src/data/analysis/weekly-{week}.json, "
        f"then run: python main.py --mode finalize --weekly"
    )
    return 0


def _finalize_weekly(args: argparse.Namespace) -> int:
    week = args.week or _week_label()
    pending_path = config.PENDING_DIR / f"weekly-{week}.json"
    analysis_path = config.ANALYSIS_DIR / f"weekly-{week}.json"
    if not pending_path.exists():
        print(f"[finalize] no pending file: {_rel(pending_path)} — run --mode weekly first")
        return 1
    payload = json.loads(pending_path.read_text(encoding="utf-8"))
    analysis = {}
    if analysis_path.exists():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    else:
        print(
            f"[finalize] note: no analysis file ({_rel(analysis_path)}); "
            "rendering with fallback text"
        )

    digest = _build_digest(payload, analysis)
    md_path = storage.write_weekly_report(digest)
    subject, html_body = build_weekly_email(digest)

    if args.dry_run:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = config.OUTPUT_DIR / f"weekly_preview_{digest['date_str']}.html"
        out_path.write_text(html_body, encoding="utf-8")
        print(f"[finalize] dry run: email preview written to {out_path}")
        print(f"[finalize] subject would be: {subject}")
        return 0

    print(f"[finalize] markdown digest: {_rel(md_path)}")
    email_failed = not send_email(subject, html_body) and config.smtp_ready()
    discord_failed = not discord_notifier.send_weekly_digest(digest) and config.discord_weekly_ready()
    if email_failed or discord_failed:
        print("[finalize] ERROR: a configured delivery channel failed")
        return 1
    return 0


def run_finalize(args: argparse.Namespace) -> int:
    return _finalize_weekly(args) if args.weekly else _finalize_daily(args)


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Fallen Angel / Quality Value Investing Tracker")
    parser.add_argument("--mode", choices=["daily", "weekly", "finalize"], required=True)
    parser.add_argument("--tickers", default="",
                        help="comma-separated tickers, overrides WATCHLIST (daily mode)")
    parser.add_argument("--dry-run", action="store_true",
                        help="do not write any files or send email; print instead")
    parser.add_argument("--date", default="", help="finalize daily rows of this date (YYYY-MM-DD)")
    parser.add_argument("--week", default="", help="finalize the weekly digest of this ISO week (YYYY-Www)")
    parser.add_argument("--weekly", action="store_true",
                        help="with --mode finalize: process the weekly digest instead")
    args = parser.parse_args()

    runner = {"daily": run_daily, "weekly": run_weekly, "finalize": run_finalize}[args.mode]
    raise SystemExit(runner(args))


if __name__ == "__main__":
    main()
