"""discord_notifier.py — payload shaping + webhook delivery (requests faked).

Covers the Feb persona formatting: weekly 3-message split and the pure
build_daily_message (interesting embeds / quiet one-liners / 🧡 overpriced line).
"""
from __future__ import annotations

import pytest

import config
import discord_notifier


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

def test_trunc_short_text_unchanged():
    assert discord_notifier._trunc("hello", 10) == "hello"


def test_trunc_long_text_gets_ellipsis_within_limit():
    out = discord_notifier._trunc("x" * 50, 10)
    assert len(out) == 10
    assert out.endswith("…")


def test_trunc_handles_none_and_whitespace():
    assert discord_notifier._trunc(None, 10) == ""
    assert discord_notifier._trunc("  hi  ", 10) == "hi"


def test_verdict_color_mapping():
    assert discord_notifier._verdict_color("Pass - Temporary") == 0x2ECC71
    assert discord_notifier._verdict_color("Fail - Value Trap") == 0xE74C3C
    assert discord_notifier._verdict_color("Watch") == 0xF1C40F
    assert discord_notifier._verdict_color("") == 0xF1C40F           # safe default


def test_tracking_block_empty_state():
    assert "ยังไม่มี position" in discord_notifier._tracking_block([])


def test_tracking_block_formats_rows(make_tracking):
    block = discord_notifier._tracking_block([make_tracking("TEST")])
    lines = block.splitlines()
    assert lines[0].startswith("TICKER")
    assert any(line.startswith("TEST") for line in lines[1:])
    assert "+10.0%" in lines[1]
    assert "n/a" in lines[1]               # return_3m is None


def test_payload_omits_empty_sections_and_caps_embeds(monkeypatch):
    monkeypatch.setattr(config, "DISCORD_USERNAME", "")
    assert discord_notifier._payload() == {}
    assert discord_notifier._payload("content") == {"content": "content"}

    payload = discord_notifier._payload("content", [{"i": n} for n in range(12)])
    assert len(payload["embeds"]) == 10
    assert "username" not in payload

    monkeypatch.setattr(config, "DISCORD_USERNAME", "Feb 🌷")
    payload = discord_notifier._payload("content", [])
    assert payload["username"] == "Feb 🌷"
    assert "embeds" not in payload


# ---------------------------------------------------------------------------
# build_daily_message — Feb persona rules
# ---------------------------------------------------------------------------

def test_daily_message_interesting_gets_embeds(make_row):
    rows = [make_row(), make_row({"ticker": "AAPL"}, **{"Moat Impairment Verdict": "Watch"})]
    content, embeds = discord_notifier.build_daily_message(rows)

    assert "จาก Watch list" in content
    assert "น่าสนใจ 1 ตัว" in content
    assert discord_notifier.DISCLAIMER in content
    assert len(embeds) == 1                          # only the Pass row
    assert "TEST" in embeds[0]["title"]
    assert embeds[0]["color"] == 0x2ECC71


def test_daily_message_overpriced_line(make_row):
    cheap = make_row({"ticker": "CHEAP", "price": 60.0})            # 40% discount — interesting
    rich = make_row({"ticker": "RICH", "price": 120.0})             # -20% "discount" = expensive
    rows = [cheap, rich]
    content, embeds = discord_notifier.build_daily_message(rows)
    assert "แพงกว่ามูลค่า" in content
    assert "RICH" in content
    assert len(embeds) == 1 and "CHEAP" in embeds[0]["title"]


def test_daily_message_nothing_interesting_make_no_ideas(make_row):
    rows = [make_row(**{"Moat Impairment Verdict": "Watch"})]
    content, embeds = discord_notifier.build_daily_message(rows)
    assert "ไม่มีอะไรน่าสนใจ" in content
    assert embeds == []
    assert discord_notifier.DISCLAIMER in content


# ---------------------------------------------------------------------------
# _build_messages — the pure 3-message split
# ---------------------------------------------------------------------------

def test_build_messages_splits_lead_picks_and_lesson(make_digest):
    messages = discord_notifier._build_messages(make_digest(tracking=[], notes=["n1"]))
    assert len(messages) == 3

    lead, picks_msg, lesson_msg = messages
    assert "จาก Watch list — Falling Angle Weekly 2026-09-14" in lead["content"]
    assert "TEST: Pass - Temporary" in lead["content"]
    assert "```" in lead["content"]
    assert "⚠ n1" in lead["content"]
    assert discord_notifier.DISCLAIMER in lead["content"]
    assert "embeds" not in lead

    assert "หุ้นน่าสนใจประจำสัปดาห์" in picks_msg["content"]
    assert len(picks_msg["embeds"]) == 1
    embed = picks_msg["embeds"][0]
    assert "#1 Test Corp (TEST)" in embed["title"]
    assert embed["color"] == 0x2ECC71
    assert "criterion one" in embed["fields"][-1]["value"]

    assert lesson_msg["content"].startswith("📚")
    assert lesson_msg["embeds"][0]["title"].startswith("📚 Lesson Title")


def test_build_messages_without_picks_posts_notice(make_digest):
    messages = discord_notifier._build_messages(make_digest(pick_rows=[]))
    picks_msg = messages[1]
    lead = messages[0]
    assert "ไม่มีตัวที่ผ่านเกณฑ์ Falling Angle" in lead["content"]
    assert "ไม่มีหุ้นผ่านเกณฑ์ Falling Angle" in picks_msg["content"]
    assert "embeds" not in picks_msg


# ---------------------------------------------------------------------------
# send_weekly_digest
# ---------------------------------------------------------------------------

@pytest.fixture
def webhook(monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL", "https://discord.invalid/webhook/1")
    posted = {"payloads": []}

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json=None, timeout=None):
        posted["url"] = url
        posted["payloads"].append(json)
        return FakeResponse()

    monkeypatch.setattr(discord_notifier.requests, "post", fake_post)
    return posted


def test_send_weekly_digest_not_configured_is_noop():
    assert discord_notifier.send_weekly_digest({"picks": []}) is False


def test_send_weekly_digest_posts_three_messages(make_digest, webhook):
    assert discord_notifier.send_weekly_digest(make_digest(tracking=[])) is True
    assert webhook["url"] == "https://discord.invalid/webhook/1"
    assert len(webhook["payloads"]) == 3


def test_send_weekly_digest_fails_if_any_message_fails(make_digest, monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL", "https://discord.invalid/webhook/1")
    calls = {"n": 0}

    def flaky_post(url, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 2:                     # second message fails
            raise ConnectionError("rate limited")

        class Ok:
            def raise_for_status(self):
                pass

        return Ok()

    monkeypatch.setattr(discord_notifier.requests, "post", flaky_post)
    assert discord_notifier.send_weekly_digest(make_digest()) is False
    assert calls["n"] == 2                      # stops at the failing message


def test_send_weekly_digest_swallows_network_errors(make_digest, monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URL", "https://discord.invalid/webhook/1")

    def boom(*a, **k):
        raise ConnectionError("offline")

    monkeypatch.setattr(discord_notifier.requests, "post", boom)
    assert discord_notifier.send_weekly_digest(make_digest()) is False


def test_send_daily_summary_posts_feb_message(make_row, webhook):
    rows = [make_row()]
    assert discord_notifier.send_daily_summary(rows) is True
    payload = webhook["payloads"][0]
    assert "จาก Watch list" in payload["content"]
    assert len(payload["embeds"]) == 1


def test_send_daily_summary_not_configured_is_noop(make_row):
    assert discord_notifier.send_daily_summary([make_row()]) is False
