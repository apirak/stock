# 🌷 Falling Angle Watchlist System — src/

โค้ดทั้งหมดของระบบอยู่ที่นี่ (โปรเจกต์เดิม `fallen_angel_tracker/` ถูกแทนที่และลบออกแล้ว — ย้อนประวัติได้จาก git)

> **เอกสารสามชุดมีคนละหน้าที่:** ไฟล์นี้อธิบาย *โครงสร้างโค้ดและวิธีเรียกใช้แต่ละฟังก์ชัน*
> (สำหรับ bot/คนที่จะมาใช้ต่อ) | [knowledge/falling_angle.md](../knowledge/falling_angle.md)
> คือ *หลักการลงทุน* ที่ bot ต้องใช้ตัดสิน | [_GUIDELINE.md](../watchlist/stock_knowledge/_GUIDELINE.md)
> คือ *format การเก็บไฟล์หุ้น* ใน stock_knowledge/ (spec เต็มอยู่ที่ plan/stock.md)

---

## 1. สถาปัตยกรรม: 3 Step คุยกันผ่านไฟล์ JSON (ไม่มีการเรียก LLM API)

```
┌──────────────────────────┐    ┌──────────────────────┐    ┌──────────────────────────┐
│ 1. data_fetcher.py       │    │ 2. ZCode harness     │    │ 3. main.py finalize      │
│    + analyzer.py         │    │  (automation session)│    │    + storage.py          │
│  ดึงข้อมูล (ฟรี, yfinance) │───▶│  Moat Impairment     │───▶│  merge analysis → CSV    │
│  คำนวณ metrics + rules   │    │  Test ด้วย model ของ  │    │  regenerate report       │
│  → src/data/pending/*.json│   │  ZCode → src/data/   │    │  → Discord (Feb 🌷)      │
└──────────────────────────┘    │  analysis/           │    │  (+ email ถ้าตั้ง SMTP)   │
                                └──────────────────────┘    └──────────────────────────┘
```

**หลักการ:** ตัวเลขต้อง deterministic (Python คำนวณจากงบจริง ห้ามให้ LLM แต่ง) ส่วนการตัดสิน
เชิงคุณภาพ (ข่าวร้ายชั่วคราว vs โครงสร้างพัง) ใช้ "สมอง" ของ ZCode session —
โปรเจกต์นี้จงใจไม่มีโค้ดเรียก LLM API

**แหล่งข้อมูล:** universe อ่านจาก `watchlist/stock_knowledge/index.md` (single source of
truth) — ตัวไหน Market เป็น SET/ไทย (SPCX, KKP, XIAOMI80) จะถูกข้ามในการดึงราคาอัตโนมัติ
(manual research only)

**ตารางรันอัตโนมัติ** (ZCode Automations): Daily Stock อังคาร–เสาร์ 07:00 / Weekly Stock
จันทร์ 09:00 — prompt อัปเดตล่าสุดอยู่ใน automation เหล่านั้น

---

## 2. CLI — เรียกใช้ผ่าน terminal (จาก `src/`)

| คำสั่ง | ทำอะไร |
|---|---|
| `.venv/bin/python main.py --mode daily` | เก็บข้อมูลทุกตัวใน index.md + rule-based verdict → append CSV → brief ที่ `watchlist/_daily/<date>.md` → เขียน pending file รอ ZCode |
| `.venv/bin/python main.py --mode weekly` | อ่าน CSV ย้อนหลัง → คำนวณ tracking returns → คัด top picks → pending + digest fallback ที่ `weekly/<YYYY-Www>.md` |
| `.venv/bin/python main.py --mode finalize` | merge `src/data/analysis/daily-<date>.json` ลง CSV + regenerate รายงาน + **โพสต์ Discord Daily (Feb)** |
| `.venv/bin/python main.py --mode finalize --weekly` | merge narratives + lesson → digest + **โพสต์ Discord Weekly (Feb, 3 ข้อความ)** + email (ถ้าตั้ง SMTP) |
| `--tickers NVDA,TSLA` | ระบุหุ้น (daily) — ไม่งั้นใช้ `src/data/daily_input.txt` → env `WATCHLIST` → index.md |
| `--dry-run` | แสดงอย่างเดียว ไม่เขียนไฟล์/ไม่โพสต์ (weekly จะเซฟ HTML preview ที่ `src/output/`) |
| `--date YYYY-MM-DD` / `--week YYYY-Www` | finalize ย้อนวัน |

ทุกคำสั่งคืน exit code: 0 = สำเร็จ, 1 = มีปัญหา (ดู stdout)

---

## 3. ฟังก์ชันในแต่ละโมดูล — bot ตัวอื่นเรียกยังไง

> import แบบ flat จากโฟลเดอร์ src/ เช่น `sys.path.insert(0, "src")` แล้ว `import universe`

### `config.py` — ศูนย์รวมค่าตั้ง (ไม่มี logic)

- **Paths:** `INDEX_PATH`, `LEDGER_PATH`, `GUIDELINE_PATH` (format contract), `STOCK_KNOWLEDGE_DIR` (knowledge base) ·
  `DAILY_REPORT_DIR` = `watchlist/_daily/`, `WEEKLY_REPORT_DIR` = `weekly/` ·
  `CSV_LOG_PATH`, `PENDING_DIR`, `ANALYSIS_DIR` (runtime, ใต้ src/) ·
  `PERSONA_PATH` (charactor/feb/persona.md), `FALLING_ANGLE_DOC` (knowledge/falling_angle.md)
- **Watchlist:** `WATCHLIST` (จาก env; ปกติว่าง = ให้ universe อ่าน index.md),
  `MANUAL_ONLY_MARKET_MARKERS` (ตัดหุ้นไทย/DR ออกจาก fetch อัตโนมัติ)
- **Thresholds:** ตัวเลขเกณฑ์เดียวกับ knowledge/falling_angle.md — `MAX_NET_DEBT_EBITDA=3`,
  `MIN_INTEREST_COVERAGE=5`, `MIN_DISCOUNT_FOR_BUY=0.15`, `STRONG_DISCOUNT=0.30`,
  `MIN_FCF_YIELD=0.03`, position cap 5–8%, tranche แรก 25–30%
- `FAIR_VALUE_OVERRIDES` — parse จาก env `"NVDA=220,MSFT=530"` (FV จาก Morningstar ฯลฯ)
- `MINI_LESSON_TOPICS` — หัวข้อบทเรียน 12 อัน หมุนตาม ISO week
- `smtp_ready()` / `discord_ready()` / `discord_weekly_ready()` — เช็คช่องทางส่ง
- `DISCORD_USERNAME` default `"Feb 🌷"` (override ผ่าน env ได้)

### `universe.py` — อ่าน/แก้ `watchlist/stock_knowledge/index.md` (แหล่งความจริงเดียว)

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `parse_index(text) -> list[dict]` | แปลง markdown table → list ของ dict (keys = COLUMNS: Ticker, Company, Market, Status, Research Priority, Opportunity Status, Last Review) — pure |
| `read_index(path=None) -> list[dict]` | อ่าน index.md จริง → rows |
| `tickers(rows=None, status=None, automated_only=False) -> list[str]` | รายชื่อ ticker ตามลำดับในไฟล์ — `status="Owned"/"Watch"` กรอง, `automated_only=True` ตัด SPCX/KKP/XIAOMI80 (SET/ไทย) ออก |
| `update_row(ticker, fields: dict, path=None) -> bool` | แก้ cell ของแถวเดียว เช่น `{"Status": "Watch", "Last Review": "..."}` — atomic, reject column แปลก (ValueError) |
| `touch_last_review(ticker, path=None) -> bool` | เซ็ต Last Review = วันนี้ (UTC) |
| `move_ticker_folder(ticker, new_status, base=None) -> Path \| None` | ย้าย folder หุ้น `own/ ↔ watchlist/` ตอนสถานะเปลี่ยน — คืน path ปลายทาง, None ถ้าไม่มี folder, raise FileExistsError ถ้าปลายทางมีของอยู่ |

**ตัวอย่าง (session "ผู้ใช้บอกว่าซื้อ AAPL"):**
```python
import universe
universe.update_row("AAPL", {"Status": "Owned", "Last Review": "2026-09-16"})
universe.move_ticker_folder("AAPL", "Owned")        # watchlist/AAPL -> own/AAPL
```

### `ledger.py` — บันทึกซื้อขาย append-only ที่ `watchlist/stock_knowledge/ledger.md`

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `append_transaction(date, tx_type, ticker, *, shares, price, currency, fees, reason, notes, path=None) -> Path` | เพิ่ม 1 รายการ — tx_type ∈ BUY, SELL, DIVIDEND, SPLIT, TRANSFER, CASH_IN, CASH_OUT; ข้อมูลที่ไม่รู้ส่ง None (จะถูกบันทึกว่า `unknown` ไม่เดา); date format `YYYY-MM-DD` |
| `parse_transactions(text) -> list[dict]` | แปลงข้อความ ledger → transactions (pure) |
| `read_transactions(path=None) -> list[dict]` | อ่าน ledger ทั้งไฟล์ |
| `net_positions(transactions=None) -> dict[str, dict]` | **พอร์ตปัจจุบัน** จาก BUY/SELL (moving-average cost): `{ticker: {shares, avg_cost, last_date}}` — ตัดตัวที่ shares unknown / ขายหมดแล้ว |

**ตัวอย่าง (session "ผมซื้อ MSFT 2 หุ้นที่ $530"):**
```python
import ledger
ledger.append_transaction("2026-09-16", "BUY", "MSFT", shares=2, price=530,
                          reason="เหตุผลตามที่ผู้ใช้บอก")
# แล้วอัปเดต index.md ผ่าน universe (ด้านบน) — bot ห้ามแต่ง transaction เอง
```

### `data_fetcher.py` — ดึงข้อมูล (yfinance, ไม่วิเคราะห์)

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `fetch_snapshot(ticker, fair_value_override=None, include_news=True) -> FinancialSnapshot` | ทุกอย่างของ 1 ตัว: ราคา, fair value (proxy 3 ชั้น), margin 4 ปี, ROIC, WACC, Net Debt/EBITDA, Interest Coverage, FCF Yield, ผลตอบแทน 1M/3M/6M, ข่าว 6 หัวข้อ — field ไหนดึงไม่ได้ = `None` + เหตุผลใน `warnings` ไม่เด้ง error |
| `fetch_price_stats(ticker) -> dict` | เบา ๆ สำหรับ weekly tracking: ราคา + returns 1M/3M/6M |
| `chart_urls(ticker)` / `chart_links_md(ticker)` | ลิงก์กราฟ TradingView / Yahoo / StockAnalysis |
| `FinancialSnapshot` | dataclass — `.discount` = (FV−P)/FV, `.to_prompt_dict()` แปลงเป็น JSON พร้อมหน่วย % สำหรับ pending file |

FV hierarchy: `manual_override` > `analyst_target_mean` > `earnings_based_estimate` —
ทุกตัวเป็น proxy เสมอ ต้องกำกับที่มาในรายงาน

### `analyzer.py` — rule-based screen + file contract (ไม่มี LLM)

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `COLUMNS` | **schema คอลัมน์ CSV** จุดเดียว (23 คอลัมน์) — storage/mailer ดึงจากที่นี่ |
| `VERDICT_PASS / VERDICT_WATCH / VERDICT_FAIL` | ค่า verdict 3 ค่า (data contract ห้ามแก้สะเปะ) |
| `heuristic_verdict(snap) -> (verdict, reasons)` | ตัดสินจากตัวเลขล้วน: hard-fail (coverage < 2x, leverage > 5x, FCF ติดลบหนัก) → Fail; ไม่มี flag + discount ≥ 15% → Pass; ที่เหลือ Watch |
| `balance_sheet_flags(snap) -> list[str]` | เช็ค 4 เงื่อนไข: leverage > 3x, coverage < 5x, FCF ≤ 0/yield < 3%, ROIC < WACC |
| `margin_trend(snap) -> str` | `"stable"/"eroding"/"improving"/"unknown"` (margin ลง = eroding) |
| `strategic_action(verdict, snap)` / `action_from_row(verdict, row)` | Fail→Avoid, Watch→Wait, Pass + discount ≥ 15% → Accumulate 1st Tranche |
| `analyze_ticker(snap) -> dict` | แถว CSV เต็ม 1 แถวจาก rule-based ล้วน — narrative เป็น placeholder รอ merge ตอน finalize |
| `pending_entry(snap, row) -> dict` | payload ใน pending file: metrics + rule verdict + task ให้ ZCode |
| `select_top_picks(recent_rows, limit=2) -> list[dict]` | คัดหุ้นสัปดาห์นี้: งบดับต้องผ่าน (coverage ≥ 5x, leverage ≤ 3x) แล้วจัดอันดับด้วย discount + FCF yield + ROIC |
| `verdict_drift(history_rows, latest_verdict) -> str` | 🔼 Upgrade / 🔽 Downgrade เทียบ best-in-history |
| `generate_mini_lesson() -> dict` | seed บทเรียนหมุนตาม ISO week (ZCode ขยายเป็นไทย) |

### `storage.py` — CSV = source of truth, MD = ให้อ่าน

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `append_daily_rows(rows) -> str` | append ลง `src/data/daily_log.csv` |
| `read_log_rows()` / `rows_since(rows, days)` / `rows_for_date(date)` | อ่าน/กรองช่วงวัน (weekly ใช้ 8 วัน) |
| `update_rows_for_date(date, updates) -> int` | **merge ของ finalize**: `{ticker: {column: value}}` — atomic rewrite |
| `first_recommendation_by_ticker(rows)` | แถวแรกที่ Action ≠ Avoid = anchor ติดตามผล |
| `dedupe_latest_by_ticker(rows)` / `to_float(value)` | แถวล่าสุดต่อตัว / parse ตัวเลขทน `%` |
| `write_daily_report(rows) -> Path` | เขียน `watchlist/_daily/<date>.md` (EN) |
| `write_weekly_report(data) -> Path` | เขียน `weekly/<YYYY-Www>.md` (TH 3 ส่วน) |

### `discord_notifier.py` — โพสต์ Discord ในบุคลิก **Feb 🌷** (charactor/feb/persona.md)

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `build_daily_message(rows) -> (content, embeds)` | pure — กติกา Feb: ทุกข้อความขึ้นต้น "จาก Watch list"; ตัวน่าสนใจ (Pass) = embed เขียวต่อตัว (ราคา/FV/MoS/แผน/กราฟ); ที่เหลือ one-liner; แพงกว่ามูลค่ารวมบรรทัดเดียว 🧡; ไม่มีตัวน่าสนใจ = บอกตรง ๆ ห้ามมั่งมี; ปิดท้าย disclaimer |
| `send_daily_summary(rows) -> bool` | โพสต์ daily ไป `DISCORD_WEBHOOK_URL` (username "Feb 🌷") |
| `send_weekly_digest(data) -> bool` | โพสต์ weekly **3 ข้อความ**: ① lead + ตาราง tracking ② pick embeds (สีตาม verdict) ③ บทเรียน — ไป `DISCORD_WEBHOOK_URL_WEEKLY` |

### `mailer.py` — email รายสัปดาห์ (HTML inline CSS + Gmail SMTP)

- `build_weekly_email(data) -> (subject, html_body)` — ประกอบ email 3 ส่วน (ภาษาไทย)
- `send_email(subject, html_body) -> bool` — SMTP ไม่ได้ตั้ง = return False (ไม่ raise)

### `main.py` — ตัวเชื่อมทุกอย่าง (ไม่มี business logic เอง)

| ฟังก์ชัน | หน้าที่ |
|---|---|
| `run_daily(args)` | `_resolve_tickers` → fetch → analyze → append CSV + brief + pending file |
| `run_weekly(args)` | อ่าน log → select_top_picks + build_tracking → weekly pending + digest fallback |
| `run_finalize(args)` | merge analysis JSON → CSV → report → Discord (weekly: + email) |
| `build_tracking(all_rows)` | ต่อตัว: anchor → returns ตั้งแต่แนะนำ + 1M/3M/6M + verdict drift + แนวโน้มส่วนลด 7 วัน |
| `_deterioration_flag(latest)` | สัญญาณเตือนไทย: FAIL / leverage เกิน / coverage ต่ำ / Watch |

---

## 4. Data Contracts (สัญญาไฟล์ Python ↔ ZCode)

แก้ schema ต้องแก้ทั้งโค้ด (`main.py` ตอน merge) และ prompt (ZCode Automations) พร้อมกัน

**`src/data/pending/daily-<date>.json`** (Python → ZCode) — เหมือนเดิมก่อนย้าย:
metrics + `rule_based_verdict` + `rule_based_flags` + `task`

**`src/data/analysis/daily-<date>.json`** (ZCode → finalize):
```json
{"date": "YYYY-MM-DD",
 "tickers": [{"ticker": "...",
   "verdict": "Pass - Temporary | Watch | Fail - Value Trap",
   "headwind_category": "Transitory / Surface-level | Structural Damage | Mixed",
   "moat_sources": ["Intangible Assets", "Switching Costs", "Network Effect", "Cost Advantage", "Efficient Scale"],
   "core_headwinds": "...", "deep_dive": "...", "tranche_plan": "...",
   "invalidation_criteria": ["3+ ข้อ"], "suggested_position_cap_pct": 5-8}]}
```

**`src/data/pending/weekly-<Www>.json`** → `{"week", "date_str", "picks", "tracking", "lesson": seed, "notes"}`
**`src/data/analysis/weekly-<Www>.json`** → `{"week", "picks": [{ticker, why_moat_intact, market_overreaction, tranche_strategy, invalidation_criteria}], "lesson": {title, body}}` — เนื้อความไทย, enum อังกฤษ

**`src/data/daily_log.csv`** — 23 คอลัมน์ ตาม `analyzer.COLUMNS`

**index.md / ledger.md** — ดู format ใน `universe.py` / `ledger.py` และหัวไฟล์จริง

---

## 5. แก้ไข/ขยายระบบ ทำที่ไหน

| อยาก... | แก้ที่ |
|---|---|
| เพิ่ม/ลบ/เปลี่ยนสถานะหุ้น | ผ่าน ZCode session → `universe.update_row` + `move_ticker_folder` + `ledger` (ไม่แก้ env อีกต่อไป) |
| ปรับเกณฑ์ framework | constants ใน `config.py` **พร้อม** ข้อความใน `knowledge/falling_angle.md` |
| ใส่ Fair Value แม่น | env `FAIR_VALUE_OVERRIDES` ใน `.env` |
| เปลี่ยน "สมอง" ผู้วิเคราะห์ | แก้ prompt ใน ZCode Automations (อ้างอิง knowledge/falling_angle.md + plan/stock.md) |
| เพิ่มคอลัมน์ CSV | `COLUMNS` ใน `analyzer.py` + `analyze_ticker` |
| เปลี่ยนบุคลิกข้อความ Discord | `charactor/feb/persona.md` + templates ใน `discord_notifier.py` |
| เพิ่มบทเรียน mini-lesson | list `MINI_LESSON_TOPICS` ใน `config.py` |

## 6. Tests

```bash
cd src && .venv/bin/python -m pytest      # 158 tests, offline, < 1 วินาที
```

ครอบคลุมทุกโมดูลรวมถึง universe/ledger ใหม่ — กติกา TDD และ fixtures อยู่ใน
`tests/conftest.py` (ทุก test ตัดขาดจาก .env จริงและเขียนลง tmp เท่านั้น)

---

*Disclaimer: เครื่องมือเชิงการศึกษา ไม่ใช่คำแนะนำการลงทุน — Fair Value เป็นค่าประมาณเสมอ*
