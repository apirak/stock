# Daily Automation Prompt — Fallen Angel daily tracker

- **Cron:** `0 7 * * 2-6` (อังคาร–เสาร์ 07:00 น. เวลาท้องถิ่น — ครอบคลุม US close จันทร์–ศุกร์)
- **สถานะ:** ✅ มีอยู่แล้วใน ZCode Automations
- **ส่งข้อความไป:** Discord ช่องรายวัน (`DISCORD_WEBHOOK_URL`) — 1 ข้อความสรุปต่อวัน
- **ภาษาของ analysis:** อังกฤษ

> วิธีใช้: เปิดแชท ZCode ใหม่ → สร้าง Automation ด้วย cron ด้านบน → วาง prompt ด้านล่างเป็น prompt

```text
Execute the Fallen Angel daily tracking pipeline in this workspace (project folder: fallen_angel_tracker/). You are both the runner and the analyst. Do NOT call any paid LLM API — the analysis in step 2 is performed by you directly.

STEP 1 — DATA COLLECTION (Python, free APIs):
Run: cd fallen_angel_tracker && .venv/bin/python main.py --mode daily
If .venv is missing, bootstrap it first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
This fetches prices/financials/news via yfinance, appends rule-based rows to data/daily_log.csv, writes reports/daily/<date>.md, and writes a pending file data/pending/daily-<YYYY-MM-DD>.json. Note the <date> it prints.

STEP 2 — MOAT IMPAIRMENT ANALYSIS (you are the analyst):
Read the pending file. For EACH ticker, using ONLY the metrics, rule_based_flags and recent_news_headlines in the file (never invent numbers), apply the Buffett-style framework:
- Classify headwinds as "Transitory / Surface-level" (one-off scare, single missed quarter, temporary confidence crisis — the customer's reason for choosing the business is intact) vs "Structural Damage" (permanent technology obsolescence like Kodak/Blackberry, lost pricing power, customers churning for good, commoditization).
- Verdict rules: "Pass - Temporary" if headwinds are transitory AND moat sources remain verifiable; "Watch" if evidence is mixed or the balance sheet is stressed but survivable; "Fail - Value Trap" if structural damage, or leverage/coverage suggests the business may not survive the storm (heed rule_based_flags: interest coverage < 5x or Net Debt/EBITDA > 3x are red flags; coverage < 2x or leverage > 5x is near-fatal).
- Moat sources taxonomy: Intangible Assets, Switching Costs, Network Effect, Cost Advantage, Efficient Scale.

STEP 3 — WRITE ANALYSIS FILE:
Write data/analysis/daily-<same date>.json (create data/analysis/ if needed) with exactly this JSON schema:
{"date": "<YYYY-MM-DD>", "tickers": [{"ticker": "…", "verdict": "Pass - Temporary" | "Watch" | "Fail - Value Trap", "headwind_category": "Transitory / Surface-level" | "Structural Damage" | "Mixed", "moat_sources": ["…"], "core_headwinds": "1-2 sentences naming the headwinds + near-term catalyst", "deep_dive": "3-5 sentences: why the moat is/isn't intact and how the market is overreacting or repricing correctly", "tranche_plan": "3-tranche entry plan; first tranche deploys 25-30% of the intended full position", "invalidation_criteria": ["at least 3 specific, observable falsifiers"], "suggested_position_cap_pct": <integer 5-8>}]}

STEP 4 — MERGE + NOTIFY:
Run: cd fallen_angel_tracker && .venv/bin/python main.py --mode finalize
This merges your analysis into the CSV, regenerates reports/daily/<date>.md, and posts the daily summary (one line per ticker: verdict → action + chart link) to the daily Discord channel via DISCORD_WEBHOOK_URL. Verify it exits 0.

STEP 5 — Reply with a short summary: one line per ticker (ticker, final verdict, strategic action) plus any data warnings worth flagging.
```
