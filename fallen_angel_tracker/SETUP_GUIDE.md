# 🦅 Fallen Angel / Quality Value Investing Tracker — Setup Guide

ระบบ Automation สำหรับล่าหุ้น **Wide Moat ที่ราคาร่วงต่ำกว่ามูลค่าจริง** (Fallen Angels) ตามแนวคิด Buffett-style Quality Value

**สถาปัตยกรรมแบบ Hybrid (ประหยัดสุด — ค่า LLM API = 0):**

```
┌─────────────────────┐      ┌──────────────────────┐      ┌─────────────────────┐
│ 1. Python เก็บข้อมูล │      │ 2. ZCode harness     │      │ 3. Python จัด format │
│  yfinance API (ฟรี) │ ───▶ │  อ่าน pending file   │ ───▶ │  merge ลง CSV       │
│  + rule-based screen│      │  วิเคราะห์ Moat Test  │      │  + รายงาน MD/Email  │
│  → data/pending/*.json     │  ด้วย model ของ ZCode │      │  → reports/*.md     │
└─────────────────────┘      │  → data/analysis/*.json     └─────────────────────┘
                             └──────────────────────┘
```

- **ทุกวันทำการ (อังคาร–เสาร์ 07:00 น. ไทย)** → เก็บข้อมูล → ZCode วิเคราะห์ → `data/daily_log.csv` + `reports/daily/*.md`
- **ทุกวันจันทร์ 07:00 น. ไทย** → สรุป Top Fallen Angels + แทร็คผลตอบแทน + Mini-Lesson → `reports/weekly/*.md` + อีเมล (ถ้าตั้ง SMTP)

---

## 1. ทำไมต้องแบ่ง 3 Step?

เพราะแต่ละ step ใช้ "สมอง" ที่เหมาะสมกับงาน:

| Step | ใครทำ | ทำอะไร | ต้นทุน |
|---|---|---|---|
| 1. เก็บข้อมูล | Python (`--mode daily/weekly`) | ดึงราคา/งบการเงินจาก yfinance, คำนวณ Margin, ROIC vs WACC, Net Debt/EBITDA, Interest Coverage, FCF Yield, ผลตอบแทนย้อนหลัง, ดึงข่าว → เขียนไฟล์ `data/pending/` | ฟรี (API ข้อมูลสาธารณะ) |
| 2. วิเคราะห์ | **ZCode harness** (automation session) | Moat Impairment Test: จำแนกข่าวร้าย Transitory vs Structural, Verdict, Deep-Dive, Tranche Plan, Invalidation Criteria, Mini-Lesson → เขียนไฟล์ `data/analysis/` | ใช้โควตา ZCode ที่มีอยู่แล้ว |
| 3. สรุปผล | Python (`--mode finalize`) | Merge analysis ลง CSV, regenerate รายงาน MD, render + ส่งอีเมล | ฟรี |

ทั้งสาม step ผูกกันด้วย **ไฟล์ JSON contract** (pending → analysis) ทำให้ทดสอบ/รีรัน/ตรวจสอบแยกกันได้ทีละขั้น และถ้าขั้น 2 ล้ม ข้อมูลดิบก็ยังอยู่ใน CSV พร้อม verdict จาก rule-based แล้ว

> **ทางเลือกเดิมยังใช้ได้:** `--use-api-llm` จะรวมขั้น 1–3 ในคำสั่งเดียวโดยเรียก LLM API เอง (Anthropic/OpenAI/Gemini ผ่าน `LLM_PROVIDER` + key) — เหมาะกับการรันบน GitHub Actions ที่ไม่มี ZCode แต่มีค่า API

---

## 2. ตารางเวลา: ZCode Automations (ตั้งไว้แล้วในระบบนี้)

ระบบนี้ถูกออกแบบมาให้ **ZCode Automation เป็น scheduler หลัก** — automation จะปลุก ZCode session ตามเวลา แล้ว session นั้นทำทั้ง 3 step เอง (รัน Python + วิเคราะห์เอง + finalize):

| Automation | Cron (เวลาท้องถิ่น) | ความหมาย |
|---|---|---|
| Fallen Angel daily tracker | `0 7 * * 2-6` | อังคาร–เสาร์ 07:00 น. (ครอบคลุม US close จันทร์–ศุกร์) |
| Fallen Angel weekly digest | `0 7 * * 1` | ทุกวันจันทร์ 07:00 น. |

จัดการได้ที่คำสั่ง automations ของ ZCode (ดูรายการ/แก้เวลา/ลบ) ข้อควรรู้:

- **เครื่องต้องเปิด** ตอนที่ automation ทำงาน — ถ้า Mac  sleep อยู่รอบนั้นอาจถูกข้าม (รันมือเอา: `python main.py --mode daily`)
- ทดลองรันทั้ง flow ด้วยมือได้ ตาม Section 5

---

## 3. โครงสร้างไฟล์ข้อมูล

```
fallen_angel_tracker/
├── data/
│   ├── daily_log.csv            ← ฐานข้อมูลหลัก 1 แถว/หุ้น/วัน (ห้ามลบ)
│   ├── daily_input.txt          ← (optional) รายชื่อหุ้นประจำวัน, บรรทัดละ 1 ตัว
│   ├── pending/                 ← Python เขียนทิ้งไว้ให้ ZCode วิเคราะห์
│   │   ├── daily-2026-09-15.json
│   │   └── weekly-2026-W38.json
│   └── analysis/                ← ZCode เขียนผลวิเคราะห์ (JSON schema ตาม automation prompt)
│       ├── daily-2026-09-15.json
│       └── weekly-2026-W38.json
├── reports/
│   ├── daily/2026-09-15.md      ← รายงานวัน (finalize แล้วมี narrative เต็ม)
│   └── weekly/2026-W38.md       ← สรุปรายสัปดาห์ 3 Section
└── output/                      ← preview HTML ตอน --dry-run
```

`daily_log.csv` คือ source of truth — **ห้ามลบ** ไม่งั้นระบบแทร็คผลตอบแทนย้อนหลังจะหาย ไฟล์ pending/analysis ลบทิ้งได้หลัง finalize แล้ว (เก็บไว้ก็เป็นประวัติการวิเคราะห์ได้เช่นกัน)

---

## 4. (ไม่บังคับ) ตั้งค่า Gmail App Password — ถ้าอยากได้อีเมลสรุปรายสัปดาห์

1. เปิด **2-Step Verification** บนบัญชี Google ก่อน: [myaccount.google.com/security](https://myaccount.google.com/security)
2. ไปที่ [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) → สร้าง App Password → ได้รหัส **16 หลัก**
3. กรอกใน `.env`: `SMTP_USER`, `SMTP_PASSWORD` (รหัส 16 หลัก — **ห้าม**รหัสผ่านจริง), `EMAIL_TO` (ผู้รับ คั่น comma)

ไม่ตั้งก็ได้ — weekly จะบันทึกลง `reports/weekly/*.md` ให้อยู่ดี

---

## 5. รันด้วยมือ (ทดสอบ / ใช้งานเอง)

```bash
cd fallen_angel_tracker
python3 -m venv .venv && source .venv/bin/activate   # ครั้งแรกครั้งเดียว
pip install -r requirements.txt
cp .env.example .env                                  # แล้วกรอกค่าที่ใช้

# ---- Flow ปกติ (3 คำสั่ง, ขั้น 2 คือ ZCode) ----
python main.py --mode daily                 # 1) เก็บข้อมูล → data/pending/daily-*.json
# 2) ให้ ZCode วิเคราะห์: เปิด session แล้วสั่ง
#    "อ่าน fallen_angel_tracker/data/pending/daily-<date>.json วิเคราะห์ Moat Impairment Test
#     แล้วเขียนผลเป็น data/analysis/daily-<date>.json ตาม schema ใน automation prompt"
python main.py --mode finalize              # 3) merge → CSV + reports/daily/*.md

python main.py --mode weekly                # 1) สร้าง pending รายสัปดาห์
# 2) ZCode เขียน data/analysis/weekly-<Www>.json (narratives + mini-lesson)
python main.py --mode finalize --weekly     # 3) merge → reports/weekly/*.md + ส่งอีเมล

# ---- คำสั่งเสริม ----
python main.py --mode daily --tickers UNH,TGT --dry-run   # ดูอย่างเดียว ไม่เขียนไฟล์
python main.py --mode finalize --weekly --dry-run         # preview อีเมลที่ output/
python main.py --mode daily --use-api-llm                 # โหมดเก่า: จ่าย API วิเคราะห์ในคำสั่งเดียว
python main.py --mode finalize --date 2026-09-15          # finalize ย้อนวัน
```

Input รายชื่อหุ้นประจำวันมี 3 ชั้น (บนมี priority กว่า): `--tickers` → ไฟล์ `data/daily_input.txt` → `WATCHLIST` ใน `.env`

---

## 6. (ทางเลือก) รันบน GitHub Actions แทน ZCode

ถ้าจะให้รันแม้เครื่องปิด ให้ push ขึ้น GitHub แล้วใช้ `tracker.yml` ที่แนบมา — แต่ CI ไม่มี ZCode จึงต้องใช้โหมด `--use-api-llm` (แก้ `run:` ใน yml เป็น `python main.py --mode daily --use-api-llm`) และใส่ Secrets: `LLM_PROVIDER`, key ของ provider นั้น, `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GEMINI_API_KEY`, `SMTP_USER/SMTP_PASSWORD/EMAIL_TO`, `WATCHLIST`, `FAIR_VALUE_OVERRIDES`

Workflow จะ **commit `data/` + `reports/` กลับเข้า repo หลังรันทุกครั้ง** (repo = database) ตารางเดิม: daily `0 0 * * 2-6`, weekly `0 0 * * 1` (UTC = 07:00 ไทย) ทดสอบมือที่แท็บ **Actions → Run workflow**

---

## 7. ปรับ Framework ตามชอบ

ค่า threshold อยู่ใน `config.py`:

| ค่า | Default | ความหมาย |
|---|---|---|
| `MAX_NET_DEBT_EBITDA` | 3.0x | Flag เตือนหนี้สุทธิเกิน 3 เท่า EBITDA |
| `MIN_INTEREST_COVERAGE` | 5.0x | Coverage ต้องไม่ต่ำกว่านี้ |
| `MIN_DISCOUNT_FOR_BUY` | 15% | ส่วนลดขั้นต่ำถึงจะพิจารณาเข้าไม้ |
| `POSITION_CAP_MIN/MAX` | 5–8% | เพดานขนาดพอร์ตต่อตัว |
| `FIRST_TRANCHE_MIN/MAX` | 25–30% | สัดส่วนไม้แรกของ position เป้าหมาย |

Verdict 3 ค่า: `Pass - Temporary` (ข่าวร้ายชั่วคราว → จังหวะซื้อ), `Watch` (สัญญาณปน), `Fail - Value Trap` (ความเสียหายเชิงโครงสร้าง) — ตัว rule-based ให้ verdict ตั้งต้นก่อนเสมอ แล้ว ZCode จะยืนยันหรือโต้แย้งในขั้นวิเคราะห์ (finalize ใช้คำตอบของ ZCode เป็นตัวตั้ง)

Fair Value เป็น proxy 3 ชั้น: `FAIR_VALUE_OVERRIDES` (แนะนำ เช่น `UNH=520`) → Analyst Target Mean → EPS × P/E ประมาณ

---

## 8. Troubleshooting

| อาการ | สาเหตุ/วิธีแก้ |
|---|---|
| `finalize` บอก no analysis file | ยังไม่มีใครเขียน `data/analysis/daily-<date>.json` — ให้ ZCode วิเคราะห์ก่อน (หรือใช้ `--use-api-llm`) |
| `finalize` บอก skipping TGT | ไฟล์ analysis ไม่มี ticker นั้น หรือวันที่ไม่ตรงกับแถวใน CSV — เช็ค `"date"` ใน JSON กับคอลัมน์ Date (แก้ด้วย `--date`) |
| Weekly แทร็คผลตอบแทนไม่ได้ / ตารางว่าง | `daily_log.csv` ถูกลบ — ต้องมีอย่างน้อย 1 แถวที่ Action ≠ Avoid |
| Automation ไม่ยิง | เครื่อง/ZCode ปิดอยู่ตอนนั้น — รันมือ `python main.py --mode daily` แทนรอบนั้นได้ |
| Gmail `535 Bad Credentials` | ใช้รหัสผ่านจริงแทน App Password หรือยังไม่เปิด 2FA |
| Fair Value / Discount ว่าง | ไม่มี override, analyst target และ EPS ก็ไม่พอ — กรอก `FAIR_VALUE_OVERRIDES` |
| yfinance ดึงข้อมูลไม่ครบบางตัว | ปกติสำหรับ ADR/REIT — ดูคอลัมน์ `Data Warnings` ใน CSV |
| CI `git push` ล้มเหลว | workflow ต้องมี `permissions: contents: write` และ branch ไม่ถูก protect |
| LLM API ตอบ parse ไม่ผ่าน (โหมด --use-api-llm) | fallback เป็น rule-based อัตโนมัติ — ลองเปลี่ยน `LLM_MODEL` |

---

## 9. คำเตือน

ระบบนี้เป็นเครื่องมือการศึกษาและการจัดการวงจรวิจัยหุ้นอัตโนมัติ **ไม่ใช่คำแนะนำการลงทุน** Fair Value เป็นค่าประมาณจาก feed ฟรี ควรตรวจสอบงบการเงินและข่าวสารด้วยตนเองก่อนตัดสินใจทุกครั้ง — "ปากกาชนกระดาษก่อนเงินออกจากกระเป๋า" เสมอ
