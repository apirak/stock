# 🤖 Automation Prompts — Fallen Angel Tracker

ไฟล์นี้เก็บ **prompt ฉบับเต็ม** สำหรับสร้าง ZCode Automations (scheduler ของระบบ)
เมื่อต้องสร้างใหม่หรือย้ายเครื่อง ให้ copy ข้อความใน code block ไปวางเป็น prompt ของ automation
พร้อมตั้ง cron ตามที่ระบุหัวไว้

> ระบบจำกัดให้สร้าง automation ได้ 1 ตัวต่อ session — เปิดแชทใหม่เพื่อสร้างตัวถัดไป

---

## 1. Daily tracker — `0 7 * * 2-6` (อังคาร–เสาร์ 07:00 น.)

ชื่อที่แนะนำ: `Fallen Angel daily tracker — อังคาร–เสาร์ 07:00`

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

STEP 4 — MERGE:
Run: cd fallen_angel_tracker && .venv/bin/python main.py --mode finalize
This merges your analysis into the CSV and regenerates reports/daily/<date>.md. Verify it exits 0.

STEP 5 — Reply with a short summary: one line per ticker (ticker, final verdict, strategic action) plus any data warnings worth flagging.
```

---

## 2. Weekly digest — `0 7 * * 1` (ทุกวันจันทร์ 07:00 น.)

ชื่อที่แนะนำ: `Fallen Angel weekly digest — ทุกวันจันทร์ 07:00`

**ข้อแตกต่างจาก daily: ทุก narrative และ mini-lesson ต้องเขียนเป็นภาษาไทย**
(ค่าใน schema ที่เป็น enum — verdict, headwind_category, ticker — ยังเป็นภาษาอังกฤษตามเดิมเพราะเป็น data contract)

```text
Execute the Fallen Angel weekly digest pipeline in this workspace (project folder: fallen_angel_tracker/). You are both the runner and the analyst. Do NOT call any paid LLM API — the narratives in step 2 are written by you directly.

STEP 1 — DATA BUILD (Python, free APIs):
Run: cd fallen_angel_tracker && .venv/bin/python main.py --mode weekly
If .venv is missing, bootstrap it first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
This reads data/daily_log.csv history, computes 1M/3M/6M returns vs recommendation prices, selects rule-based top-pick candidates, writes reports/weekly/<YYYY-Www>.md and a pending file data/pending/weekly-<YYYY-Www>.json. Note the <YYYY-Www> week label it prints.

STEP 2 — WRITE NARRATIVES IN THAI (คุณคือนักวิเคราะห์ — เขียนเป็นภาษาไทยทั้งหมด):
Read the pending file. Using ONLY the logged data (ห้ามแต่งตัวเลข):
a) สำหรับแต่ละตัวใน "picks" เขียน (ภาษาไทย):
   - why_moat_intact: 3-4 ประโยค ว่าทำไมป้อมปราการยังอยู่ — ระบุ moat source ชัดเจน (Switching Costs, Network Effect, Cost Advantage, Intangible Assets)
   - market_overreaction: 2-3 ประโยค ตลาดกำลัง overreact ตรงไหน; ถ้า verdict เป็น "Watch" ให้ระบุว่าต้องยืนยันอะไรก่อนถึงจะเข้าซื้อ
   - tranche_strategy: แผนแบ่งไม้ 3 ไม้ ไม้แรก 25-30% ของ position เป้าหมาย พร้อมเงื่อนไขไม้ต่อไป
   - invalidation_criteria: อย่างน้อย 3 ข้อ เป็นสัญญาณที่สังเกตได้จริงและเจาะจง
b) ขยาย "lesson" (title + brief) เป็นบทเรียนการลงทุนสไตล์ Buffett ความยาว 150-220 คำ ภาษาไทย โทนตรง อ่านง่าย ใช้กรณีศึกษาจริง ปิดท้ายด้วยข้อสรุปที่นำไปใช้ได้ทันที 1 ประโยค (แปล title เป็นไทยได้ โดยคงความหมาย)

STEP 3 — WRITE ANALYSIS FILE:
Write data/analysis/weekly-<same YYYY-Www>.json with exactly this schema (ค่า enum เป็นอังกฤษ เนื้อความเป็นไทย):
{"week": "<YYYY-Www>", "picks": [{"ticker": "…", "why_moat_intact": "…", "market_overreaction": "…", "tranche_strategy": "…", "invalidation_criteria": ["…"]}], "lesson": {"title": "…", "body": "…"}}

STEP 4 — MERGE + DELIVER:
Run: cd fallen_angel_tracker && .venv/bin/python main.py --mode finalize --weekly
This regenerates reports/weekly/<YYYY-Www>.md with your narratives, and delivers the digest to every configured channel (HTML email via SMTP, Discord via webhook). Verify it exits 0.

STEP 5 — Reply with a short summary in Thai: top picks + verdicts, จุดเด่นของตารางติดตาม (ผลตอบแทนดีสุด/แย่สุด, สัญญาณเตือน), และชื่อบทเรียนประจำสัปดาห์.
```
