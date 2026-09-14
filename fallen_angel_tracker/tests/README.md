# Test Suite — Fallen Angel Tracker

ชุดทดสอบนี้ทำให้โค้ดทั้ง pipeline **ทดสอบได้แบบ offline และเร็ว (<1 วินาที)**
ครอบคลุมตั้งแต่ rule engine ระดับฟังก์ชัน จนถึง contract ระหว่างไฟล์
(CSV → pending JSON → analysis JSON → merged CSV + reports)
ต่อไปเวลาทำ TDD ให้เริ่มจากเขียน test ที่แดง (fail) ในไฟล์ที่ถูกชั้น
แล้วค่อยเขียนโค้ดให้เขียว

## วิธีรัน

```bash
cd fallen_angel_tracker
.venv/bin/python -m pytest            # ทั้งชุด (config อยู่ที่ pyproject.toml)
.venv/bin/python -m pytest tests/test_analyzer.py -k verdict   # กรองตามชื่อ
.venv/bin/python -m pytest -vv        # verbose ดูรายละเอียดตอน fail
```

ติดตั้ง dev dependencies: `pip install -r requirements-dev.txt`

## ชั้นของการทดสอบ (test pyramid)

| ไฟล์ | ชั้น | อะไรถูก mock | อะไรถูกรันจริง |
|---|---|---|---|
| `test_config.py` | unit | — | readiness gates (`llm_ready`, `smtp_ready`, `discord_ready`), `_parse_overrides` |
| `test_data_fetcher.py` | unit | `yf.Ticker` → `FakeTicker` (DataFrame จำลอง) | fair-value hierarchy, ทุก ratio, การจัดการ yfinance ที่ข้อมูลหลุม |
| `test_analyzer.py` | unit | `call_llm_json` / provider callers | screening rules, verdict/action matrix, การสร้าง row, top picks |
| `test_storage.py` | I/O | ไม่มี (แต่ path ชี้ tmp dir) | CSV roundtrip, atomic update, markdown reports |
| `test_mailer.py` | I/O | `smtplib.SMTP(_SSL)` → `FakeSMTP` | HTML rendering, escaping, ทางเลือก port 465/587 |
| `test_discord_notifier.py` | I/O | `requests.post` | payload 3-message split, truncation, failure handling |
| `test_main.py` | pipeline | `fetch_snapshot` / `fetch_price_stats` (yfinance) | CLI orchestration ทั้ง 3 mode + สัญญาไฟล์ pending/analysis |

## Fixtures กลาง (`tests/conftest.py`)

- **`_safe_env` (autouse)** — ล้างค่า secret/network ทุกตัวบน module `config`
  (LLM keys, SMTP, Discord webhook) ทุก test ไม่มีทางยิงของจริง
  แม้ `.env` ในเครื่องจะใส่ key ไว้ก็ตาม
- **`tmp_config`** — redirect ไฟล์จัดเก็บทั้งหมด (CSV, reports, pending,
  analysis, `BASE_DIR`) ไป tmp dir ของ pytest
- **`make_snapshot`** — `FinancialSnapshot` ที่สมดุลแบบ clean balance sheet,
  discount 20% (เกินเกณฑ์ซื้อ 15%) — ส่ง override เฉพาะฟิลด์ที่สนใจ
- **`make_row`** — row เต็ม 23 คอลัมน์ สร้างผ่าน `analyze_ticker` จริง
- **`make_tracking` / `make_digest`** — payload รายสัปดาห์สำหรับ mailer/discord/main

ข้อตกลง: ห้าม network, ห้าม sleep, ห้ามแตะไฟล์จริง, ใช้ `monkeypatch`
กับ attribute ของ module (โค้ดอ่านค่า `config.X` ตอน runtime จึง patch ได้ตรงจุด)

## จุดที่ตั้งใจ pin ไว้ (regression guards)

- **Fair value hierarchy** — override มือ > analyst target > EPS×PE
  (test ป้องกันการสลับลำดับความสำคัญ)
- **`heuristic_verdict` hard-fail** — coverage < 2x, leverage > 5x,
  FCF ติดลบ+โครงสร้างหนี้สูง ต้องเป็น `Fail - Value Trap` เสมอ
- **Margin ขาดลง (`eroding`) ต้องบังคับ verdict ลงเป็น `Watch`** แม้ balance sheet สะอาด
- **Verdict ที่ LLM ตอบมั่ว** ต้องถูกทิ้งและ fallback เป็น rule-based
- **Cap การถือต้อง clamp ในช่วง 5–8%** ทั้งกรณี inline LLM และ finalize
- **`finalize` ต้องไม่เขียน CSV เมื่อ analysis ไม่มี ticker ที่รู้จัก**

## margin_trend semantics (เคยเป็นบั๊ก — แก้แล้ว ปักหลักด้วย test)

`gross_margin_history` เรียง **newest-first** และ `margin_trend` วัด
`delta = ใหม่ − เก่า`: กำไรขาดลงเกิน 3 จุด = `"eroding"` / ขาขึ้น = `"improving"`
(เคยมีบั๊ก label สลับข้าง ทำให้หุ้น margin ทรุดผ่าน `!= "eroding"`
ใน `heuristic_verdict` และได้ verdict Pass ผิดๆ — แก้แล้วใน `analyzer.py`)

test ที่ปักหลักพฤติกรรมนี้:

```python
tests/test_analyzer.py::test_margin_trend_falling_margins_are_eroding
tests/test_analyzer.py::test_margin_trend_rising_margins_are_improving
tests/test_analyzer.py::test_eroding_margins_block_pass_verdict   # guard ผลปลายทาง
```

## Workflow สำหรับ TDD

1. **แดง** — เขียน test ที่อธิบายพฤติกรรมที่ยังไม่มี ในไฟล์ตามชั้นของโค้ด
   (rule ใหม่ → `test_analyzer.py`, contract ไฟล์ใหม่ → `test_main.py` ฯลฯ)
   ใช้ factory fixture ที่มีอยู่ อย่าสร้าง snapshot/row เองทั้งก้อน
2. **รันให้เห็นว่า fail ด้วยเหตุผลที่ถูก** — `.venv/bin/python -m pytest -k <name>`
3. **เขียว** — เขียนโค้ดน้อยที่สุดให้ผ่าน
4. **รีแฟกเตอร์** — รันทั้งชุด ต้องยังเขียว และ suite นี้เร็วมาก
   (ปัจจุบัน <0.3s) จึงรันได้ทุกครั้งที่ save
5. ถ้าต้องแก้พฤติกรรมเดิมที่ pin ไว้ ให้แก้ test **ก่อน** แล้ว comment ใน
   commit ว่าพฤติกรรมเปลี่ยนตามที่ตั้งใจ
