"""
Local-only storage: CSV log + Markdown reports (no external database).

Layout:
  data/daily_log.csv           one row per ticker per day — the tracking database
  reports/daily/YYYY-MM-DD.md  human-readable daily analysis
  reports/weekly/YYYY-Www.md   weekly digest (same content that goes into the email)

The CSV is the single source of truth that the weekly pipeline reads back;
the Markdown reports are for reading in an editor / Obsidian.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone

import config
from analyzer import COLUMNS
from data_fetcher import chart_links_md, chart_urls


# ---------------------------------------------------------------------------
# CSV backend (the tracking database)
# ---------------------------------------------------------------------------

def append_csv(rows: list[dict]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    exists = config.CSV_LOG_PATH.exists()
    with config.CSV_LOG_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def read_csv() -> list[dict]:
    if not config.CSV_LOG_PATH.exists():
        return []
    with config.CSV_LOG_PATH.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def to_float(value) -> float | None:
    try:
        text = str(value).strip().replace("%", "")
        return float(text) if text not in ("", "None") else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Log access API (used by main.py)
# ---------------------------------------------------------------------------

def append_daily_rows(rows: list[dict]) -> str:
    if not rows:
        return "nothing to log"
    append_csv(rows)
    return f"logged {len(rows)} row(s) to {config.CSV_LOG_PATH.relative_to(config.BASE_DIR)}"


def read_log_rows() -> list[dict]:
    return read_csv()


def rows_since(rows: list[dict], days: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    out = []
    for row in rows:
        try:
            row_date = datetime.strptime(str(row.get("Date", ""))[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if row_date >= cutoff:
            out.append(row)
    return out


def dedupe_latest_by_ticker(rows: list[dict]) -> dict[str, dict]:
    """Latest row per ticker, preserving log order."""
    latest: dict[str, dict] = {}
    for row in rows:
        ticker = str(row.get("Ticker", "")).upper()
        if ticker:
            latest[ticker] = row
    return latest


def rows_for_date(date: str) -> list[dict]:
    return [row for row in read_csv() if str(row.get("Date", ""))[:10] == date]


def update_rows_for_date(date: str, updates: dict[str, dict]) -> int:
    """Merge per-ticker field updates into rows of `date`; atomic CSV rewrite."""
    rows = read_csv()
    changed = 0
    for row in rows:
        ticker = str(row.get("Ticker", "")).upper()
        if str(row.get("Date", ""))[:10] == date and ticker in updates:
            row.update(updates[ticker])
            changed += 1
    if changed:
        tmp = config.CSV_LOG_PATH.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(config.CSV_LOG_PATH)
    return changed


def first_recommendation_by_ticker(rows: list[dict]) -> dict[str, dict]:
    """First actionable row (anything not 'Avoid') per ticker — the tracking anchor."""
    firsts: dict[str, dict] = {}
    for row in rows:
        ticker = str(row.get("Ticker", "")).upper()
        action = str(row.get("Strategic Action", ""))
        if ticker and action and action != "Avoid" and ticker not in firsts:
            firsts[ticker] = row
    return firsts


# ---------------------------------------------------------------------------
# Markdown reports
# ---------------------------------------------------------------------------

def _verdict_emoji(verdict: str) -> str:
    if str(verdict).startswith("Pass"):
        return "✅"
    if str(verdict).startswith("Fail"):
        return "🚫"
    return "⏳"


def _daily_section(row: dict) -> list[str]:
    invalidation = [c for c in str(row.get("Invalidation Criteria", "")).split(" | ") if c]
    invalidation_md = "\n".join(f"  - {c}" for c in invalidation) or "  - (n/a)"
    return [
        f"## {_verdict_emoji(row.get('Moat Impairment Verdict', ''))} "
        f"{row.get('Ticker')} — {row.get('Company Name')}",
        "",
        f"**Verdict:** {row.get('Moat Impairment Verdict')} · "
        f"**Action:** {row.get('Strategic Action')} · "
        f"**Position cap:** {row.get('Suggested Position Cap (%)')}%",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Price vs Fair Value | ${row.get('Market Price ($)')} vs "
        f"${row.get('Fair Value ($)')} ({row.get('Discount (%)')}% discount) |",
        f"| Gross / Operating Margin | {row.get('Gross Margin (%)')}% / "
        f"{row.get('Operating Margin (%)')}% |",
        f"| ROIC vs WACC | {row.get('ROIC (%)')}% vs {row.get('WACC (%)')}% |",
        f"| Net Debt/EBITDA · Interest Coverage | {row.get('Net Debt / EBITDA') or 'n/a'} · "
        f"{row.get('Interest Coverage Ratio') or 'n/a'} |",
        f"| FCF Yield | {row.get('FCF Yield (%)')}% |",
        "",
        f"**📈 ดูกราฟ:** {chart_links_md(row.get('Ticker', ''))}",
        "",
        f"**Headwinds / Catalyst:** {row.get('Core Headwinds / Catalyst')}",
        "",
        f"**Deep-Dive:** {row.get('Deep-Dive')}",
        "",
        f"**Tranche Plan:** {row.get('Tranche Plan')}",
        "",
        "**Invalidation Criteria (cut if any trigger):**",
        invalidation_md,
        "",
    ]


def write_daily_report(rows: list[dict]) -> object:
    """Write reports/daily/YYYY-MM-DD.md and return the path."""
    config.DAILY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date = str(rows[0].get("Date", ""))[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = config.DAILY_REPORT_DIR / f"{date}.md"
    lines = [
        f"# 🦅 Fallen Angel Daily Report — {date}",
        "",
        f"_{len(rows)} ticker(s) analyzed · raw log: `data/daily_log.csv`_",
        "",
    ]
    for row in rows:
        lines.extend(_daily_section(row))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _fmt_pct_return(value) -> str:
    return "n/a" if value is None else f"{value:+.1f}%"


def _weekly_tracking_table(tracking: list[dict]) -> list[str]:
    if not tracking:
        return ["_ยังไม่มีคำแนะนำที่บันทึกไว้ — รัน daily pipeline ก่อน_", ""]
    lines = [
        "| Ticker | วันที่แนะนำ | ราคาตอนแนะนำ | ราคาปัจจุบัน | ผลตอบแทน | 1M | 3M | 6M | ส่วนลด (7 วัน) | Drift | Verdict ล่าสุด | สัญญาณเตือน |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t in tracking:
        tv_url = chart_urls(t["ticker"])["TradingView"]
        lines.append(
            f"| **[{t['ticker']}]({tv_url})** | {t['rec_date']} | ${t['rec_price']} | ${t['price']} "
            f"| {_fmt_pct_return(t['return_pct'])} | {_fmt_pct_return(t['return_1m'])} "
            f"| {_fmt_pct_return(t['return_3m'])} | {_fmt_pct_return(t['return_6m'])} "
            f"| {t.get('discount_trend') or '—'} | {t.get('drift') or '—'} "
            f"| {t['latest_verdict']} | {t['flag'] or '—'} |"
        )
    lines.append("")
    return lines


def write_weekly_report(data: dict) -> object:
    """Write reports/weekly/<YYYY-Www>.md from the same payload that feeds the email.

    The filename follows the payload's week (data["week"]) so finalizing an
    older week never scatters files across the wrong folders.
    """
    config.WEEKLY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    week = data.get("week") or datetime.now(timezone.utc).strftime("%G-W%V")
    path = config.WEEKLY_REPORT_DIR / f"{week}.md"

    lines = [f"# 🦅 Fallen Angel Weekly Digest — {data['date_str']}", ""]

    lines += ["## ส่วนที่ 1 — Fallen Angels ประจำสัปดาห์", ""]
    if not data["picks"]:
        lines += ["_สัปดาห์นี้ไม่มีหุ้นผ่าน Moat Impairment screen — การรอคอยก็เป็น position หนึ่ง_", ""]
    for i, pick in enumerate(data["picks"], start=1):
        row, n = pick["row"], pick["narrative"]
        lines += [
            f"### #{i} {row.get('Company Name')} ({row.get('Ticker')})",
            "",
            f"**Verdict:** {row.get('Moat Impairment Verdict')} · "
            f"**แผน:** {row.get('Strategic Action')} · "
            f"**เพดานพอร์ต:** {row.get('Suggested Position Cap (%)')}% · "
            f"**ราคา:** ${row.get('Market Price ($)')} vs FV ${row.get('Fair Value ($)')} "
            f"(ส่วนลด {row.get('Discount (%)')}%)",
            "",
            f"**📈 ดูกราฟ:** {chart_links_md(row.get('Ticker', ''))}",
            "",
            f"**🏰 ทำไมป้อมปราการยังแข็งแกร่ง:** {n['why_moat_intact']}",
            "",
            f"**📉 ตลาดกำลัง overreact อย่างไร:** {n['market_overreaction']}",
            "",
            f"**🎯 แผนแบ่งไม้เข้าซื้อ:** {n['tranche_strategy']}",
            "",
            "**🚪 จุดยอมแพ้ (Invalidation Criteria) — เจอเมื่อไหร่ต้องตัด:**",
            "\n".join(f"- {c}" for c in n["invalidation_criteria"]),
            "",
        ]

    lines += ["## ส่วนที่ 2 — ติดตามพอร์ต & Watchlist", ""]
    lines += _weekly_tracking_table(data["tracking"])
    for note in data.get("notes", []):
        lines.append(f"> ⚠ {note}")
    if data.get("notes"):
        lines.append("")

    lesson = data["lesson"]
    lines += [
        "## ส่วนที่ 3 — บทเรียนการลงทุนสไตล์ Buffett",
        "",
        f"### 📚 {lesson['title']}",
        "",
        lesson["body"],
        "",
        "---",
        "_สร้างอัตโนมัติโดย Fallen Angel Tracker — เนื้อหาเชิงการศึกษา ไม่ใช่คำแนะนำการลงทุน_",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
