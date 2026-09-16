"""mailer.py — HTML rendering + SMTP delivery (SMTP fully faked)."""
from __future__ import annotations

import email

import pytest

import config
import mailer


class FakeSMTP:
    """Minimal context-manager SMTP double recording the conversation."""

    last = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.started_tls = False
        self.logins = []
        self.sent = []
        FakeSMTP.last = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logins.append((user, password))

    def sendmail(self, frm, to, body):
        self.sent.append((frm, list(to), body))


@pytest.fixture
def smtp_config(monkeypatch):
    monkeypatch.setattr(config, "SMTP_USER", "me@gmail.com")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "app-pass")
    monkeypatch.setattr(config, "EMAIL_FROM", "me@gmail.com")
    monkeypatch.setattr(config, "EMAIL_TO", ["a@x.com", "b@x.com"])
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(config, "SMTP_PORT", 465)


def test_build_weekly_email_subject_and_sections(make_digest):
    subject, body = mailer.build_weekly_email(make_digest())
    assert subject == "🌷 Falling Angle Weekly Digest — 2026-09-14"
    assert "ส่วนที่ 1" in body and "ส่วนที่ 2" in body and "ส่วนที่ 3" in body
    assert "#1 Test Corp (TEST)" in body
    assert "moat story for TEST" in body
    assert "<li" in body and "criterion one" in body
    assert "Lesson Title" in body


def test_build_weekly_email_without_picks_shows_notice(make_digest):
    subject, body = mailer.build_weekly_email(make_digest(pick_rows=[]))
    assert subject == "🌷 Falling Angle Weekly Digest — 2026-09-14"
    assert "สัปดาห์นี้ไม่มีหุ้นผ่าน" in body
    assert "Test Corp" not in body          # no pick cards rendered


def test_build_weekly_email_escapes_html(make_digest, make_row):
    digest = make_digest(pick_rows=[make_row(**{"Company Name": "<b>Evil & Co</b>"})],
                         notes=["<script>alert(1)</script>"])
    _, body = mailer.build_weekly_email(digest)
    assert "<script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "&lt;b&gt;Evil &amp; Co&lt;/b&gt;" in body


def test_tracking_table_colors_returns(make_digest, make_tracking):
    up = make_tracking("UP", return_pct=3.2)
    down = make_tracking("DOWN", return_pct=-1.0)
    _, body = mailer.build_weekly_email(make_digest(pick_rows=[], tracking=[up, down]))
    assert "#2a9d8f" in body          # positive -> green
    assert "#c1121f" in body          # negative -> red
    assert "+3.2%" in body and "-1.0%" in body
    assert "n/a" in body              # None return renders as n/a


def test_send_email_skips_when_not_configured():
    # _safe_env blanks all SMTP settings
    assert mailer.send_email("subj", "<p>x</p>") is False


def test_send_email_ssl_port_465(monkeypatch, smtp_config):
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTP)
    assert mailer.send_email("subj", "<p>body</p>") is True
    sent = FakeSMTP.last
    assert sent.host == "smtp.gmail.com" and sent.port == 465
    assert sent.logins == [("me@gmail.com", "app-pass")]
    frm, to, raw = sent.sent[0]
    assert frm == "me@gmail.com"
    assert to == ["a@x.com", "b@x.com"]

    msg = email.message_from_string(raw)
    assert msg["Subject"] == "subj"
    assert msg["To"] == "a@x.com, b@x.com"
    html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
    html_payload = html_part.get_payload(decode=True).decode("utf-8")  # base64 part
    assert "<p>body</p>" in html_payload


def test_send_email_starttls_on_other_ports(monkeypatch, smtp_config):
    monkeypatch.setattr(config, "SMTP_PORT", 587)
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTP)
    assert mailer.send_email("subj", "<p>x</p>") is True
    assert FakeSMTP.last.started_tls is True
