"""
Discord webhook delivery.

Two channels (both optional):
  - DISCORD_WEBHOOK_URL          → daily summary, one message after finalize
  - DISCORD_WEBHOOK_URL_WEEKLY   → weekly digest, posted as THREE separate
    messages: ① lead + tracking table ② pick embeds ③ mini-lesson
    (falls back to DISCORD_WEBHOOK_URL when unset)

Discord caps: content ≤ 2000 chars, embed description ≤ 4096, field value ≤ 1024,
10 embeds per message. All text is truncated to fit — full reports always live in
reports/. Never raises; each send returns False on failure.
"""
from __future__ import annotations

import requests

import config
from data_fetcher import chart_links_md, chart_urls

_COLOR = {"Pass": 0x2ECC71, "Watch": 0xF1C40F, "Fail": 0xE74C3C}  # green/yellow/red

_MAX_CONTENT = 1900
_MAX_EMBED_DESC = 3900
_MAX_FIELD_VALUE = 1000


def _trunc(text, limit: int) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _verdict_color(verdict: str) -> int:
    for prefix, color in _COLOR.items():
        if str(verdict).startswith(prefix):
            return color
    return _COLOR["Watch"]


def _tracking_block(tracking: list[dict]) -> str:
    """Monospaced compact table (English headers keep code-block alignment)."""
    if not tracking:
        return "ยังไม่มี position ให้ติดตาม"
    lines = ["TICKER  RET     1M      3M      6M      DISC(7D)      DRIFT  VERDICT"]
    for t in tracking:
        ret = "n/a" if t["return_pct"] is None else f"{t['return_pct']:+.1f}%"

        def fmt(x):
            return "n/a" if x is None else f"{x:+.1f}%"

        disc_now = t.get("discount_now") or "n/a"
        disc_delta = t.get("discount_delta") or ""
        disc = f"{disc_now}({disc_delta})" if disc_delta else disc_now
        drift = {"🔼 Upgrade": "↑", "🔽 Downgrade": "↓"}.get(t.get("drift", ""), "·")
        lines.append(
            f"{t['ticker']:<7}{ret:<8}{fmt(t['return_1m']):<8}{fmt(t['return_3m']):<8}"
            f"{fmt(t['return_6m']):<8}{disc:<14}{drift:<7}{_trunc(t['latest_verdict'], 22)}"
        )
    return "\n".join(lines)


def _pick_embed(pick: dict, rank: int) -> dict:
    row, n = pick["row"], pick["narrative"]
    description = (
        f"🏰 **ทำไมป้อมปราการยังแข็งแกร่ง**\n{_trunc(n['why_moat_intact'], 800)}\n\n"
        f"📉 **ตลาดกำลัง Overreact อย่างไร**\n{_trunc(n['market_overreaction'], 500)}\n\n"
        f"🎯 **แผนแบ่งไม้เข้าซื้อ**\n{_trunc(n['tranche_strategy'], 600)}"
    )
    fields = [
        {"name": "Verdict", "value": _trunc(row.get("Moat Impairment Verdict", ""), 100), "inline": True},
        {"name": "แผน", "value": _trunc(row.get("Strategic Action", ""), 100), "inline": True},
        {"name": "เพดานพอร์ต", "value": f"{_trunc(row.get('Suggested Position Cap (%)', ''), 20)}%", "inline": True},
        {"name": "ราคา vs FV", "value": (
            f"${_trunc(row.get('Market Price ($)'), 30)} vs "
            f"${_trunc(row.get('Fair Value ($)'), 30)} "
            f"(ส่วนลด {_trunc(row.get('Discount (%)'), 20)}%)"
        ), "inline": False},
        {"name": "📈 ดูกราฟ", "value": _trunc(chart_links_md(row.get("Ticker", "")), _MAX_FIELD_VALUE), "inline": False},
        {"name": "🚪 จุดยอมแพ้ (Invalidation)", "value": _trunc(
            "\n".join(f"• {c}" for c in n["invalidation_criteria"][:4]), _MAX_FIELD_VALUE
        ), "inline": False},
    ]
    return {
        "title": f"#{rank} {_trunc(row.get('Company Name'), 100)} ({row.get('Ticker')})",
        "description": _trunc(description, _MAX_EMBED_DESC),
        "color": _verdict_color(row.get("Moat Impairment Verdict", "")),
        "fields": fields,
    }


def _lesson_embed(lesson: dict) -> dict:
    return {
        "title": f"📚 {_trunc(lesson['title'], 240)}",
        "description": _trunc(lesson["body"], _MAX_EMBED_DESC),
        "color": 0xC9A227,
    }


def _payload(content: str = "", embeds: list[dict] | None = None) -> dict:
    """Webhook POST body. No username override by default — messages show the
    webhook's own name/avatar as configured in Discord. Optional override via
    DISCORD_USERNAME in .env."""
    payload: dict = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds[:10]
    if config.DISCORD_USERNAME:
        payload["username"] = config.DISCORD_USERNAME
    return payload


def _build_messages(data: dict) -> list[dict]:
    """Assemble the digest as 3 separate Discord messages (lead / picks / lesson)."""
    picks = data.get("picks", [])

    # Message 1 — lead + tracking table
    lead = [f"🦅 **Fallen Angel Weekly Digest — {data['date_str']}**"]
    if picks:
        picks_line = " | ".join(
            f"{p['row']['Ticker']}: {p['row']['Moat Impairment Verdict']}" for p in picks
        )
        lead.append(f"⭐ Top Picks: {_trunc(picks_line, 200)}")
    lead.append("📊 **ติดตามพอร์ต & Watchlist**")
    lead.append(f"```{_tracking_block(data.get('tracking', []))}```")
    for note in data.get("notes", []):
        lead.append(f"⚠ {_trunc(note, 200)}")

    # Message 2 — recommended stocks
    if picks:
        picks_msg = _payload(
            "🎯 **หุ้นแนะนำประจำสัปดาห์ (Fallen Angels)**",
            [_pick_embed(pick, i + 1) for i, pick in enumerate(picks)],
        )
    else:
        picks_msg = _payload(
            "🎯 สัปดาห์นี้ไม่มีหุ้นผ่าน Moat Impairment screen — การรอคอยก็เป็น position หนึ่ง"
        )

    # Message 3 — mini-lesson
    lesson_msg = _payload(
        "📚 **บทเรียนการลงทุนสไตล์ Buffett**",
        [_lesson_embed(data["lesson"])],
    )

    return [_payload(_trunc("\n".join(lead), _MAX_CONTENT)), picks_msg, lesson_msg]


def send_weekly_digest(data: dict) -> bool:
    """Post the weekly digest to the weekly Discord channel as 3 messages.
    True only if every message succeeds."""
    url = config.DISCORD_WEBHOOK_URL_WEEKLY or config.DISCORD_WEBHOOK_URL
    if not url:
        print("[discord] no weekly webhook configured; Discord delivery skipped")
        return False
    messages = _build_messages(data)
    for i, payload in enumerate(messages, start=1):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - notification must never kill the pipeline
            print(f"[discord] ERROR on message {i}/{len(messages)}: {exc}")
            return False
    print(f"[discord] weekly digest posted as {len(messages)} message(s)")
    return True


# ---------------------------------------------------------------------------
# Daily summary (single message, posted by --mode finalize after the merge)
# ---------------------------------------------------------------------------

def _verdict_emoji(verdict: str) -> str:
    if str(verdict).startswith("Pass"):
        return "✅"
    if str(verdict).startswith("Fail"):
        return "🚫"
    return "⏳"


def send_daily_summary(rows: list[dict]) -> bool:
    """Post today's per-ticker verdicts as one compact message to the daily
    channel. Called by --mode finalize (daily) once final verdicts are merged."""
    if not config.discord_ready():
        print("[discord] DISCORD_WEBHOOK_URL not configured; daily summary skipped")
        return False
    if not rows:
        return False
    date = str(rows[0].get("Date", ""))[:10]
    lines = [f"🦅 **Fallen Angel Daily — {date}**"]
    for row in rows:
        ticker = row.get("Ticker", "")
        discount = row.get("Discount (%)")
        discount_txt = f"ส่วนลด {discount}%" if str(discount).strip() else "ส่วนลด n/a"
        lines.append(
            f"{_verdict_emoji(row.get('Moat Impairment Verdict', ''))} **{ticker}** — "
            f"{row.get('Moat Impairment Verdict', 'n/a')} → {row.get('Strategic Action', 'n/a')} "
            f"| {discount_txt} | [📊 chart]({chart_urls(ticker)['TradingView']})"
        )
    content = _trunc("\n".join(lines), _MAX_CONTENT)
    try:
        resp = requests.post(config.DISCORD_WEBHOOK_URL, json=_payload(content), timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"[discord] ERROR posting daily summary: {exc}")
        return False
    print(f"[discord] daily summary posted ({len(rows)} ticker(s))")
    return True
