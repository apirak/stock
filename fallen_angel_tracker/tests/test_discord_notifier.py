"""discord_notifier.py — payload shaping + webhook delivery (requests faked).

The current implementation posts the digest as THREE messages
(lead + tracking / picks embeds / lesson), and returns True only if every
message succeeds.
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

    monkeypatch.setattr(config, "DISCORD_USERNAME", "Angel Bot")
    payload = discord_notifier._payload("content", [])
    assert payload["username"] == "Angel Bot"
    assert "embeds" not in payload


# ---------------------------------------------------------------------------
# _build_messages — the pure 3-message split
# ---------------------------------------------------------------------------

def test_build_messages_splits_lead_picks_and_lesson(make_digest):
    messages = discord_notifier._build_messages(make_digest(tracking=[], notes=["n1"]))
    assert len(messages) == 3

    lead, picks_msg, lesson_msg = messages
    assert "Fallen Angel Weekly Digest — 2026-09-14" in lead["content"]
    assert "TEST: Pass - Temporary" in lead["content"]
    assert "```" in lead["content"]
    assert "⚠ n1" in lead["content"]
    assert "embeds" not in lead

    assert "หุ้นแนะนำประจำสัปดาห์" in picks_msg["content"]
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
    assert "สัปดาห์นี้ไม่มีหุ้นผ่าน" in picks_msg["content"]
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
