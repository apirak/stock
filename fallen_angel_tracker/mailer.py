"""
Weekly digest email: HTML template + Gmail SMTP delivery.

Sections (per spec): 1) Top Fallen Angels of the Week with moat deep-dive and
tranche plan, 2) Portfolio & Watchlist tracking with returns and deterioration
flags, 3) rotating Buffett-style mini-lesson. Inline CSS only — email clients
strip <style> blocks inconsistently.
"""
from __future__ import annotations

import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def _esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _nl2br(text) -> str:
    return _esc(text).replace("\n", "<br>")


_CSS = (
    "font-family:Georgia,'Times New Roman',serif;color:#1a1a2e;"
    "line-height:1.55;max-width:720px;margin:0 auto;padding:16px;"
)
_CARD_CSS = (
    "border:1px solid #d8dee6;border-radius:10px;padding:18px 22px;margin:0 0 22px;"
    "background:#ffffff;"
)
_TITLE_CSS = "margin:0 0 10px;font-size:20px;color:#8b1e3f;"
_LABEL_CSS = (
    "display:inline-block;background:#f2e9e4;color:#8b1e3f;border-radius:4px;"
    "padding:2px 8px;font-size:12px;font-family:Arial,sans-serif;margin-right:6px;"
)
_SECTION_CSS = (
    "font-family:Arial,sans-serif;font-size:13px;font-weight:bold;"
    "letter-spacing:1px;text-transform:uppercase;color:#5c677d;"
    "border-bottom:2px solid #8b1e3f;padding-bottom:6px;margin:34px 0 16px;"
)
_TABLE_CSS = "border-collapse:collapse;width:100%;font-size:13px;font-family:Arial,sans-serif;"
_TH_CSS = (
    "background:#1d3557;color:#ffffff;padding:8px 10px;text-align:left;"
    "font-size:12px;border:1px solid #1d3557;"
)
_TD_CSS = "padding:7px 10px;border:1px solid #d8dee6;vertical-align:top;"
_LESSON_CSS = (
    "background:#fdf6ec;border-left:5px solid #c9a227;padding:18px 22px;"
    "border-radius:0 10px 10px 0;"
)
_FOOTER_CSS = (
    "font-size:11px;color:#8d99ae;font-family:Arial,sans-serif;margin-top:30px;"
    "border-top:1px solid #d8dee6;padding-top:12px;"
)


def _metrics_table(row: dict) -> str:
    cells = [
        ("Price", f"${_esc(row.get('Market Price ($)'))}"),
        ("Fair Value", f"${_esc(row.get('Fair Value ($)'))}"),
        ("Discount", f"{_esc(row.get('Discount (%)'))}%"),
        ("Gross / Op Margin", f"{_esc(row.get('Gross Margin (%)'))}% / {_esc(row.get('Operating Margin (%)'))}%"),
        ("ROIC vs WACC", f"{_esc(row.get('ROIC (%)'))}% vs {_esc(row.get('WACC (%)'))}%"),
        ("Net Debt/EBITDA", _esc(row.get("Net Debt / EBITDA")) or "n/a"),
        ("Int. Coverage", _esc(row.get("Interest Coverage Ratio")) or "n/a"),
        ("FCF Yield", f"{_esc(row.get('FCF Yield (%)'))}%"),
    ]
    cells_td = "".join(
        f'<td style="{_TD_CSS}"><b style="color:#5c677d;font-size:11px;'
        f'font-family:Arial">{label}</b><br>{value}</td>'
        for label, value in cells
    )
    return f'<table style="{_TABLE_CSS}"><tr>{cells_td}</tr></table>'


def _pick_card(pick: dict, rank: int) -> str:
    row = pick["row"]
    narrative = pick["narrative"]
    invalidation_items = "".join(
        f"<li style=\"margin:4px 0\">{_esc(item)}</li>"
        for item in narrative["invalidation_criteria"]
    )
    return f"""
    <div style="{_CARD_CSS}">
      <h3 style="{_TITLE_CSS}">#{rank} { _esc(row.get('Company Name')) } ({_esc(row.get('Ticker'))})</h3>
      <p style="margin:0 0 12px">
        <span style="{_LABEL_CSS}">{_esc(row.get('Moat Impairment Verdict'))}</span>
        <span style="{_LABEL_CSS}">{_esc(row.get('Strategic Action'))}</span>
        <span style="{_LABEL_CSS}">Cap {_esc(row.get('Suggested Position Cap (%)'))}% of portfolio</span>
      </p>
      {_metrics_table(row)}
      <p style="margin:14px 0 4px"><b style="font-family:Arial;font-size:13px">🏰 Why the moat is intact</b><br>{_nl2br(narrative['why_moat_intact'])}</p>
      <p style="margin:10px 0 4px"><b style="font-family:Arial;font-size:13px">📉 How the market is overreacting</b><br>{_nl2br(narrative['market_overreaction'])}</p>
      <p style="margin:10px 0 4px"><b style="font-family:Arial;font-size:13px">🎯 Tranche strategy (split entries)</b><br>{_nl2br(narrative['tranche_strategy'])}</p>
      <p style="margin:10px 0 4px"><b style="font-family:Arial;font-size:13px">🚪 Invalidation criteria — cut if any trigger</b></p>
      <ul style="margin:4px 0 8px;padding-left:22px;font-size:13px">{invalidation_items}</ul>
    </div>"""


def _tracking_table(tracking: list[dict]) -> str:
    if not tracking:
        return (
            "<p style=\"font-size:13px;color:#5c677d\">No actionable recommendations "
            "logged yet — the tracking table will populate after the first daily run.</p>"
        )
    header = "".join(
        f'<th style="{_TH_CSS}">{h}</th>'
        for h in ["Ticker", "Rec. Date", "Rec. Price", "Now", "Return",
                  "1M", "3M", "6M", "Latest Verdict", "Alert"]
    )
    body_rows = []
    for t in tracking:
        ret = t["return_pct"]
        ret_str = "n/a" if ret is None else f"{ret:+.1f}%"
        color = "#2a9d8f" if (ret or 0) > 0 else ("#c1121f" if (ret or 0) < 0 else "#5c677d")

        def fmt(x):
            return "n/a" if x is None else f"{x:+.1f}%"

        body_rows.append(
            f'<tr><td style="{_TD_CSS}"><b>{_esc(t["ticker"])}</b></td>'
            f'<td style="{_TD_CSS}">{_esc(t["rec_date"])}</td>'
            f'<td style="{_TD_CSS}">${_esc(t["rec_price"])}</td>'
            f'<td style="{_TD_CSS}">${_esc(t["price"])}</td>'
            f'<td style="{_TD_CSS};color:{color};font-weight:bold">{ret_str}</td>'
            f'<td style="{_TD_CSS}">{fmt(t["return_1m"])}</td>'
            f'<td style="{_TD_CSS}">{fmt(t["return_3m"])}</td>'
            f'<td style="{_TD_CSS}">{fmt(t["return_6m"])}</td>'
            f'<td style="{_TD_CSS}">{_esc(t["latest_verdict"])}</td>'
            f'<td style="{_TD_CSS};color:#c1121f">{_esc(t["flag"])}</td></tr>'
        )
    return f'<table style="{_TABLE_CSS}"><tr>{header}</tr>{"".join(body_rows)}</table>'


def build_weekly_email(data: dict) -> tuple[str, str]:
    """Return (subject, html_body)."""
    date_str = data["date_str"]
    subject = f"🦅 Fallen Angel Weekly Digest — {date_str}"

    picks_html = "".join(_pick_card(p, i + 1) for i, p in enumerate(data["picks"])) or (
        '<div style="' + _CARD_CSS + '"><p style="margin:0">No stock passed the '
        "Moat Impairment screen this week — patience is a position. The watchlist "
        "tracking below is still updated.</p></div>"
    )
    lesson = data["lesson"]
    notes_html = "".join(
        f"<p style=\"margin:2px 0;font-size:12px;color:#5c677d\">• {_esc(n)}</p>"
        for n in data.get("notes", [])
    )

    body = f"""<!DOCTYPE html>
<html><body style="margin:0;background:#f4f5f7">
<div style="{_CSS}">
  <div style="background:#1d3557;border-radius:10px;padding:22px 26px;margin-bottom:8px">
    <h1 style="color:#ffffff;margin:0;font-size:24px;font-family:Georgia,serif">
      🦅 Fallen Angel Weekly Digest</h1>
    <p style="color:#a8dadc;margin:6px 0 0;font-size:13px;font-family:Arial,sans-serif">
      Quality Value Investing Tracker &middot; { _esc(date_str) }</p>
  </div>

  <div class="section" style="{_SECTION_CSS}">Section 1 &mdash; Fallen Angels of the Week</div>
  {picks_html}

  <div class="section" style="{_SECTION_CSS}">Section 2 &mdash; Portfolio &amp; Watchlist Tracking</div>
  <div style="{_CARD_CSS}">{_tracking_table(data["tracking"])}{notes_html}</div>

  <div class="section" style="{_SECTION_CSS}">Section 3 &mdash; Buffett-style Mini-Lesson</div>
  <div style="{_LESSON_CSS}">
    <h3 style="margin:0 0 8px;color:#8b1e3f;font-size:18px">📚 {_esc(lesson["title"])}</h3>
    <p style="margin:0;font-size:14px">{_nl2br(lesson["body"])}</p>
  </div>

  <p style="{_FOOTER_CSS}">
    Generated automatically by the Fallen Angel / Quality Value Investing Tracker.
    Fair values are estimates (analyst mean target / manual override / earnings-based proxy).
    This is educational automation, not personalized investment advice — do your own work
    before acting on any pick.
  </p>
</div>
</body></html>"""
    return subject, body


def send_email(subject: str, html_body: str) -> bool:
    """Send via Gmail SMTP (SSL). Returns True on success."""
    if not config.smtp_ready():
        print("[mailer] SMTP not configured (SMTP_USER/SMTP_PASSWORD/EMAIL_TO); email skipped")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = ", ".join(config.EMAIL_TO)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if config.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())
    print(f"[mailer] sent '{subject}' to {', '.join(config.EMAIL_TO)}")
    return True
