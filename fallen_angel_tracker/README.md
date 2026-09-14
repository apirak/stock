# 🦅 Fallen Angel / Quality Value Investing Tracker

ระบบ Automation ล่าหุ้น **Wide Moat ที่ราคาปรับลดต่ำกว่ามูลค่าจริง** (Fallen Angels) ตามแนวคิด Buffett-style Quality Value — รันบนเครื่อง local ทั้งหมด

> **เอกสารสองชุดมีคนละหน้าที่:** ไฟล์นี้อธิบาย *โครงสร้างโค้ดและวิธีเรียกใช้แต่ละฟังก์ชัน* (สำหรับคนที่จะมาแก้/ใช้ต่อ) | [SETUP_GUIDE.md](SETUP_GUIDE.md) อธิบาย *การติดตั้งและตั้งค่า* (service, .env, email) | [AUTOMATION_PROMPTS.md](AUTOMATION_PROMPTS.md) เก็บ prompt สำหรับ ZCode Automations

---

## 1. สถาปัตยกรรม: 3 Step คุยกันผ่านไฟล์ JSON

```
┌──────────────────────────┐    ┌──────────────────────┐    ┌──────────────────────────┐
│ 1. data_fetcher.py       │    │ 2. ZCode harness     │    │ 3. main.py finalize      │
│    + analyzer.py         │    │  (automation session)│    │    + storage.py          │
│  ดึงข้อมูล (ฟรี)          │───▶│  Moat Impairment     │───▶│  merge analysis → CSV    │
│  คำนวณ metrics + rules   │    │  Test ด้วย model ของ  │    │  regenerate report       │
│  → data/pending/*.json   │    │  ZCode → data/analysis/│   │  (+ email ถ้าตั้ง SMTP)  │
└──────────────────────────┘    └──────────────────────┘    └──────────────────────────┘
```

**เหตุผลที่แบ่งแบบนี้:** ตัวเลขต้อง deterministic (Python คำนวณจากงบจริง ห้ามให้ LLM แต่ง) ส่วนการตัดสินเชิงคุณภาพ (ข่าวร้ายชั่วคราว vs โครงสร้างพัง) ต้องใช้ "สมอง" — ใช้ ZCode harness แทนการจ่ายค่า LLM API ถ้าไม่มี ZCode ก็ใช้ `--use-api-llm` จ่าย API รวมทุก step ในคำสั่งเดียวได้

**ตารางรันอัตโนมัติ** (ZCode Automations): daily อังคาร–เสาร์ 07:00 น. / weekly วันจันทร์ 07:00 น. — ดู prompt ที่ [AUTOMATION_PROMPTS.md](AUTOMATION_PROMPTS.md)

---

## 2. โครงสร้างโปรเจกต์

```
fallen_angel_tracker/
├── config.py               # ค่าตั้งทั้งหมด: env vars, thresholds, path, lesson topics
├── data_fetcher.py         # ดึงข้อมูลตลาดจาก yfinance → FinancialSnapshot
├── analyzer.py             # rule-based screen + LLM plumbing + schema คอลัมน์ CSV
├── storage.py              # CSV log + Markdown reports (อ่าน/เขียน/merge)
├── mailer.py               # HTML email template + Gmail SMTP
├── discord_notifier.py     # โพสต์ weekly digest เข้า Discord ผ่าน webhook
├── main.py                 # entrypoint: โหมด daily / weekly / finalize
├── AUTOMATION_PROMPTS.md   # prompt สำหรับสร้าง ZCode Automations
├── SETUP_GUIDE.md          # คู่มือติดตั้ง
└── data/ + reports/        # runtime artifacts (ดูรายละเอียดใน SETUP_GUIDE §3)
```

**ทิศทางการ import (ห้ามย้อนกลับ จะวนกัน):** `config` ← `data_fetcher` ← `analyzer` ← `storage` ← `main` / `mailer` (schema `COLUMNS` อยู่ที่ `analyzer.py` จุดเดียว)

---

## 3. CLI — เรียกใช้ผ่าน terminal

| คำสั่ง | ทำอะไร |
|---|---|
| `python main.py --mode daily` | เก็บข้อมูล + rule-based verdict → append CSV → รายงาน MD → เขียน pending file รอ ZCode |
| `python main.py --mode weekly` | อ่าน CSV ย้อนหลัง → คำนวณ tracking returns → คัด candidates → pending file + MD (fallback text) |
| `python main.py --mode finalize` | merge `data/analysis/daily-<date>.json` ลง CSV + regenerate รายงานวัน |
| `python main.py --mode finalize --weekly` | merge narratives + lesson → MD + ส่งอีเมล (ถ้าตั้ง SMTP) |
| `--tickers UNH,TGT` | ระบุหุ้น (daily) — ไม่งั้นใช้ `data/daily_input.txt` หรือ `WATCHLIST` |
| `--dry-run` | แสดงอย่างเดียว ไม่เขียนไฟล์/ไม่ส่งเมล (weekly จะเซฟ HTML preview ที่ `output/`) |
| `--use-api-llm` | รวมขั้นวิเคราะห์เป็น LLM API ในคำสั่งเดียว (ต้องตั้ง `LLM_PROVIDER` + key) |
| `--date YYYY-MM-DD` | finalize ย้อนวันที่ |

ทุกคำสั่งคืน exit code: 0 = สำเร็จ, 1 = มีปัญหา (ดู stdout)

---

## 4. ฟังก์ชันในแต่ละโมดูล — ใครทำอะไร เรียกยังไง

### `config.py` — ศูนย์รวมค่าตั้ง (ไม่มี logic)

- **Constants:** ดูตาราง thresholds ใน SETUP_GUIDE §6 — แก้ที่นี่ที่เดียวทั้งระบบ
- **Paths:** `CSV_LOG_PATH`, `PENDING_DIR`, `ANALYSIS_DIR`, `DAILY_REPORT_DIR`, `WEEKLY_REPORT_DIR`
- `WATCHLIST` — universe เริ่มต้น (หุ้น wide-moat คัดเอง เพราะ Morningstar feed เสียเงิน)
- `FAIR_VALUE_OVERRIDES` — parse จาก env `FAIR_VALUE_OVERRIDES="UNH=520,TGT=180"`
- `MINI_LESSON_TOPICS` — หัวข้อบทเรียน 12 อัน หมุนตาม ISO week (seed material ให้ ZCode ขยาย)
- `llm_ready()` / `smtp_ready()` — เช็คว่า provider/key หรือ SMTP ถูกตั้งครบหรือยัง

### `data_fetcher.py` — ดึงข้อมูล (ไม่วิเคราะห์)

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `fetch_snapshot(ticker, fair_value_override=None, include_news=True) -> FinancialSnapshot` | ดึงทุกอย่างของ 1 ตัว: ราคา, fair value (proxy 3 ชั้น), margin 4 ปี, ROIC, WACC, Net Debt/EBITDA, Interest Coverage, FCF Yield, ผลตอบแทน 1M/3M/6M, ข่าว 6 หัวข้อ — field ไหนดึงไม่ได้ = `None` + ใส่เหตุผลใน `warnings` ไม่เด้ง error |
| `fetch_price_stats(ticker) -> dict` | เวอร์ชันเบา สำหรับ weekly tracking: แค่ราคา + ผลตอบแทน 1M/3M/6M |
| `FinancialSnapshot` (dataclass) | ตัวหิ้วข้อมูลระหว่างโมดูล — `.discount` เป็น property คำนวณ (FV−P)/FV, `.to_prompt_dict()` แปลงเป็น dict พร้อมหน่วย % สำหรับให้ LLM |
| `chart_urls(ticker) -> dict` / `chart_links_md(ticker) -> str` | ลิงก์ดูกราฟ (TradingView / Yahoo Finance / StockAnalysis) — สร้างจาก ticker ณ ตอน render จึงไม่เก็บใน CSV |
| `FinancialSnapshot.fair_value_source` | `"manual_override"` > `"analyst_target_mean"` > `"earnings_based_estimate"` — ใช้ตัดสินใจว่าน่าเชื่อแค่ไหน |

> สูตรที่ฝังอยู่: ROIC = EBIT×(1−tax) ÷ (Debt+Equity−Cash) | WACC ≈ CAPM (rf + β×ERP) ผสม cost of debt after-tax | FCF = OCF − CapEx | Interest Coverage = EBIT ÷ Interest Expense

### `analyzer.py` — rule-based screen + LLM plumbing + schema

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `COLUMNS` | **schema คอลัมน์ CSV** จุดเดียว — `storage`/`mailer` ดึงจากที่นี่ |
| `VERDICT_PASS / VERDICT_WATCH / VERDICT_FAIL` | ค่า verdict 3 ค่า (data contract ห้ามแก้สะเปะ) |
| `heuristic_verdict(snap) -> (verdict, reasons)` | ตัดสินจากตัวเลขล้วน: hard-fail (coverage < 2x, leverage > 5x, FCF ติดลบหนัก) → `Fail`; ไม่มี flag + discount ≥ 15% → `Pass`; ที่เหลือ `Watch` |
| `balance_sheet_flags(snap) -> list[str]` | เช็ค 4 เงื่อนไขสเปค: leverage > 3x, coverage < 5x, FCF ≤ 0 หรือ yield < 3%, ROIC < WACC |
| `margin_trend(snap) -> str` | `"stable"/"eroding"/"improving"/"unknown"` จาก gross margin history |
| `strategic_action(verdict, snap) -> str` | Fail→`Avoid`, Watch→`Wait`, Pass→ดู discount ≥ 15% → `Accumulate 1st Tranche` |
| `action_from_row(verdict, row) -> str` | เวอร์ชันของข้างบนที่อ่านจากแถว CSV — ใช้ตอน finalize ที่ verdict ใหม่มาจาก ZCode |
| `analyze_ticker(snap, use_llm=True) -> dict` | สร้างแถว CSV เต็ม 1 แถว — `use_llm=False` (default ของ daily) ไม่ยิง API แต่ใส่ placeholder narrative |
| `pending_entry(snap, row) -> dict` | payload ที่เขียนลง pending file: metrics + rule verdict/flags + คำสั่งงานให้ ZCode |
| `select_top_picks(recent_rows, limit=2) -> list[dict]` | คัดหุ้นสัปดาห์นี้: กรอง balance sheet ต้องผ่าน (coverage ≥ 5x, leverage ≤ 3x) แล้วจัดอันดับด้วย discount + FCF yield + ROIC — verdict Pass ได้ tier บวกบน Watch |
| `generate_pick_narrative(row, use_llm=True)` | weekly deep-dive ต่อ 1 ตัว (API mode เท่านั้น — โหมด hybrid ให้ ZCode เขียนแล้ว finalize merge) |
| `generate_mini_lesson(use_llm=True) -> {"title","body"}` | หมุนหัวข้อตาม ISO week — `use_llm=False` คืน seed brief เพื่อให้ ZCode ขยาย |
| `call_llm_json(system, user) -> dict | None` | ยิง REST ตรงถึง Anthropic/OpenAI/Gemini ตาม `LLM_PROVIDER` + ดึง JSON จากคำตอบ (fail = None ไม่ raise) |

### `storage.py` — ข้อมูลอยู่ที่นี่ (CSV = source of truth, MD = ให้อ่าน)

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `append_daily_rows(rows) -> str` | append แถวใหม่ลง CSV (สร้าง header ครั้งแรก) |
| `read_log_rows() -> list[dict]` | อ่าน CSV ทั้งไฟล์เป็น list ของ dict |
| `rows_since(rows, days)` / `rows_for_date(date)` | กรองช่วงวัน (weekly ใช้ 8 วัน) / เฉพาะวันเดียว |
| `update_rows_for_date(date, updates) -> int` | **merge ของ finalize**: รับ `{ticker: {column: value}}` แล้วแก้แถววันนั้น — เขียนไฟล์ใหม่แบบ atomic (`.tmp` + replace) |
| `first_recommendation_by_ticker(rows)` | แถวแรกที่ Action ≠ Avoid ต่อ ticker = จุด anchor การแทร็คผลตอบแทน |
| `dedupe_latest_by_ticker(rows)` | แถวล่าสุดต่อ ticker — ใช้เช็ค verdict เดิมว่าเสื่อมหรือไม่ |
| `to_float(value)` | parse ตัวเลขจาก CSV (ทน `%`, ค่าว่าง) |
| `write_daily_report(rows) -> Path` | เขียน `reports/daily/<date>.md` (ภาษาอังกฤษ) |
| `write_weekly_report(data) -> Path` | เขียน `reports/weekly/<Www>.md` (**ภาษาไทย** — 3 ส่วนเหมือน email) |

### `mailer.py` — email รายสัปดาห์ (HTML inline CSS + Gmail SMTP)

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `build_weekly_email(data) -> (subject, html_body)` | ประกอบ email 3 ส่วน (ภาษาไทย): Fallen Angels ประจำสัปดาห์ / ติดตามพอร์ต / บทเรียน Buffett — `data` มาจาก `_build_digest` ใน main |
| `send_email(subject, html_body) -> bool` | ส่งผ่าน SMTP (port 465 = SSL, อื่น = STARTTLS); ถ้าไม่ได้ตั้ง SMTP → print แจ้ง + return False (ไม่ raise) |

### `discord_notifier.py` — โพสต์ weekly digest เข้า Discord

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `send_weekly_digest(data) -> bool` | โพสต์ digest เป็น **3 ข้อความแยกกัน** อ่านง่าย: ① ส่วนนำ (headline + ตาราง tracking code block) ② หุ้นแนะนำ (embed ต่อ 1 ตัว สีตาม verdict: เขียว/เหลือง/แดง) ③ บทเรียน Buffett — ตัดข้อความให้พอดี limit ของ Discord; ไม่ตั้ง `DISCORD_WEBHOOK_URL` = skip, fail = return False ไม่ raise |
| `_build_messages(data)` / `_payload(...)` | ประกอบ payload ทั้ง 3 ข้อความ (รองรับ override ชื่อผู้โพสต์ผ่าน `DISCORD_USERNAME`) |

### `main.py` — ตัวเชื่อมทุกอย่าง (ไม่มี business logic เอง)

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `run_daily(args)` | ลูป tickers → `fetch_snapshot` → `analyze_ticker` → append CSV + MD → เขียน pending file |
| `run_weekly(args)` | อ่าน log → `select_top_picks` + `build_tracking` → เขียน weekly pending + MD fallback (โหมด `--use-api-llm` จะ render+ส่งเมลเลย) |
| `run_finalize(args)` | แยก daily/weekly → merge analysis JSON ลง CSV (validate verdict, clamp position cap, recompute action) → regenerate report → (weekly) ส่งอีเมล |
| `build_tracking(all_rows)` | ต่อ ticker: หา anchor (คำแนะนำแรก) → ดึงราคาปัจจุบัน → return ตั้งแต่แนะนำ + 1M/3M/6M + flag ความเสื่อม |
| `_build_digest(payload, analysis)` | ประกอบ digest: narrative จาก ZCode ถ้ามี ไม่งั้น fallback จากข้อความใน log |
| `_deterioration_flag(latest) -> str` | สัญญาณเตือนภาษาไทย: verdict FAIL / leverage เกิน / coverage ต่ำกว่าเกณฑ์ / Watch |

---

## 5. Data Contracts (สัญญาไฟล์ระหว่าง Python ↔ ZCode)

แก้ schema ต้องแก้ทั้ง **โค้ด** (`main.py` ตอน merge) และ **prompt** ([AUTOMATION_PROMPTS.md](AUTOMATION_PROMPTS.md)) พร้อมกัน

**`data/pending/daily-<date>.json`** (Python → ZCode)
```json
{"date": "YYYY-MM-DD",
 "tickers": [{"ticker": "...", "company": "...", "price": ..., "fair_value": ...,
   "discount_pct": ..., "gross_margin_pct": ..., "operating_margin_pct": ...,
   "gross_margin_history_pct": [...], "roic_pct": ..., "wacc_pct": ...,
   "net_debt_to_ebitda": ..., "interest_coverage": ..., "fcf_yield_pct": ...,
   "recent_news_headlines": [...], "data_warnings": [...],
   "rule_based_verdict": "...", "rule_based_action": "...", "rule_based_flags": [...],
   "task": "คำสั่งให้ ZCode ทำ Moat Impairment Test"}]}
```

**`data/analysis/daily-<date>.json`** (ZCode → finalize) — field ไหนยื่นมา finalize จะ merge สิ่งนั้น ขาดไป = คงค่า rule-based เดิม
```json
{"date": "YYYY-MM-DD",
 "tickers": [{"ticker": "...",
   "verdict": "Pass - Temporary | Watch | Fail - Value Trap",
   "headwind_category": "Transitory / Surface-level | Structural Damage | Mixed",
   "moat_sources": ["Intangible Assets", "Switching Costs", "Network Effect", "Cost Advantage", "Efficient Scale"],
   "core_headwinds": "...", "deep_dive": "...", "tranche_plan": "...",
   "invalidation_criteria": ["3+ ข้อ"], "suggested_position_cap_pct": 5-8}]}
```

**`data/pending/weekly-<Www>.json`** → `{"week", "date_str", "picks": [แถว CSV], "tracking": [...], "lesson": {seed}, "notes"}` และ **`data/analysis/weekly-<Www>.json`** → `{"week", "picks": [{ticker, why_moat_intact, market_overreaction, tranche_strategy, invalidation_criteria}], "lesson": {title, body}}` — **เนื้อความเป็นภาษาไทย** (enum เช่น verdict เป็นอังกฤษ)

**`data/daily_log.csv`** — 23 คอลัมน์ ตาม `analyzer.COLUMNS`: วันที่/ticker/บริษัท, ราคา/FV/ส่วนลด, margins, ROIC/WACC, leverage/coverage/FCF yield, **Verdict**, Headwinds/Catalyst, **Strategic Action** แล้วต่อด้วย 8 คอลัมน์วิเคราะห์เพิ่ม (Headwind Category, Moat Sources, Deep-Dive, Tranche Plan, Invalidation, Position Cap, WACC, Data Warnings)

---

## 6. แก้ไข/ขยายระบบ ทำที่ไหน

| อยาก... | แก้ที่ |
|---|---|
| เพิ่ม/เปลี่ยนหุ้น | `WATCHLIST` ใน `.env` หรือ `data/daily_input.txt` (รายวัน) หรือ `--tickers` |
| ปรับเกณฑ์ framework | constants บนสุดของ `config.py` |
| ใส่ Fair Value แม่น ๆ | `FAIR_VALUE_OVERRIDES` (จาก Morningstar) |
| เปลี่ยน LLM provider/รุ่น | `LLM_PROVIDER`, `LLM_MODEL`, key ใน `.env` (โค้ด REST อยู่ `analyzer._call_*`) |
| เพิ่มคอลัมน์ CSV | `COLUMNS` ใน `analyzer.py` + จุดที่สร้าง dict ใน `analyze_ticker` |
| เปลี่ยนเกณฑ์คัด top picks weekly | `analyzer.select_top_picks` (tier ตาม verdict + คะแนน balance sheet) |
| เพิ่ม/เปลี่ยนแหล่งลิงก์กราฟ | `chart_urls()` ใน `data_fetcher.py` (ผลลัพธ์ไหลทันทีทุกช่องทาง: MD, email, Discord) |
| เพิ่มบทเรียน mini-lesson | list `MINI_LESSON_TOPICS` ใน `config.py` (หมุนอัตโนมัติตามสัปดาห์) |
| แก้แผนหน้าตา email | `mailer.py` (CSS อยู่เป็น constants บนหัวไฟล์) |
| เปลี่ยนภาษารายงาน | รายงานวัน = `storage.write_daily_report` (EN) / รายสัปดาห์ = `write_weekly_report` + labels ใน `mailer.py` (TH) + prompt ใน `AUTOMATION_PROMPTS.md` |

**ทดสอบย่อยได้แบบไม่ผูกกับ pipeline:**
```python
from data_fetcher import fetch_snapshot
from analyzer import heuristic_verdict, balance_sheet_flags
snap = fetch_snapshot("UNH")
verdict, reasons = heuristic_verdict(snap)
print(snap.discount, verdict, balance_sheet_flags(snap))
```

## 7. Tests & TDD

โปรเจกต์มี pytest suite ครอบคลุมทุกโมดูล (รันได้ offline, <1 วินาที):

```bash
.venv/bin/python -m pytest
```

แผนทดสอบ, fixtures กลาง, ข้อตกลง และ workflow สำหรับ TDD อยู่ที่
[`tests/README.md`](tests/README.md) — เวลาเพิ่มฟีเจอร์ใหม่ ให้เริ่มจาก
เขียน test ที่ fail ในไฟล์ตามชั้นของโค้ดก่อน แล้วค่อยเขียน implementation

---

*Disclaimer: เครื่องมือเชิงการศึกษา ไม่ใช่คำแนะนำการลงทุน — ตัวเลขมาจาก feed ฟรี (yfinance) Fair Value เป็นค่าประมาณเสมอ*
