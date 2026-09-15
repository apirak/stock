# Weekly Automation Prompt — Fallen Angel weekly digest

- **Cron:** `0 7 * * 1` (ทุกวันจันทร์ 07:00 น. เวลาท้องถิ่น)
- **สถานะ:** ⚠️ **ยังไม่ได้สร้าง** — เปิดแชท ZCode ใหม่ (ระบบจำกัด 1 automation ต่อ session) แล้ววาง prompt ด้านล่าง
- **ส่งข้อความไป:** Discord ช่องรายสัปดาห์ (`DISCORD_WEBHOOK_URL_WEEKLY`) — 3 ข้อความ: ① ส่วนนำ+tracking ② หุ้นแนะนำ ③ บทเรียน + email (ถ้าตั้ง SMTP)
- **ภาษาของ narrative/บทเรียน:** ไทย (ค่า enum เช่น verdict เป็นอังกฤษตาม data contract)

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
This regenerates reports/weekly/<YYYY-Www>.md with your narratives, and delivers the digest to the weekly Discord channel (DISCORD_WEBHOOK_URL_WEEKLY, posted as 3 messages: lead+tracking / picks / lesson) and HTML email via SMTP if configured. Verify it exits 0.

STEP 5 — Reply with a short summary in Thai: top picks + verdicts, จุดเด่นของตารางติดตาม (ผลตอบแทนดีสุด/แย่สุด, สัญญาณเตือน), และชื่อบทเรียนประจำสัปดาห์.
```
