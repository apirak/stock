# 🦅 Fallen Angel / Quality Value Investing Tracker — Setup Guide

ระบบ Automation สำหรับล่าหุ้น **Wide Moat ที่ราคาร่วงต่ำกว่ามูลค่าจริง** (Fallen Angels) ตามแนวคิด Buffett-style Quality Value — รันบนเครื่องของคุณเองทั้งหมด ไม่มี external service

**สถาปัตยกรรมแบบ Hybrid (ค่า LLM API = 0):**

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
- **ทุกวันจันทร์ 07:00 น. ไทย** → สรุป Top Fallen Angels + แทร็คผลตอบแทน + Mini-Lesson → `reports/weekly/*.md` + ส่ง email/Discord (ถ้าตั้งค่าไว้)

---

## 1. ทำไมต้องแบ่ง 3 Step?

เพราะแต่ละ step ใช้ "สมอง" ที่เหมาะสมกับงาน:

| Step | ใครทำ | ทำอะไร | ต้นทุน |
|---|---|---|---|
| 1. เก็บข้อมูล | Python (`--mode daily/weekly`) | ดึงราคา/งบการเงินจาก yfinance, คำนวณ Margin, ROIC vs WACC, Net Debt/EBITDA, Interest Coverage, FCF Yield, ผลตอบแทนย้อนหลัง, ดึงข่าว → เขียนไฟล์ `data/pending/` | ฟรี (API ข้อมูลสาธารณะ) |
| 2. วิเคราะห์ | **ZCode harness** (automation session) | Moat Impairment Test: จำแนกข่าวร้าย Transitory vs Structural, Verdict, Deep-Dive, Tranche Plan, Invalidation Criteria, Mini-Lesson → เขียนไฟล์ `data/analysis/` | ใช้โควตา ZCode ที่มีอยู่แล้ว |
| 3. สรุปผล | Python (`--mode finalize`) | Merge analysis ลง CSV, regenerate รายงาน MD, ส่ง email + Discord | ฟรี |

ทั้งสาม step ผูกกันด้วย **ไฟล์ JSON contract** (pending → analysis) ทำให้ทดสอบ/รีรัน/ตรวจสอบแยกกันได้ทีละขั้น และถ้าขั้น 2 ล้ม ข้อมูลดิบก็ยังอยู่ใน CSV พร้อม verdict จาก rule-based แล้ว

> **การตัดสินใจเชิงออกแบบ:** โปรเจกต์นี้ **ไม่มีโค้ดเรียก LLM API เลย** — การวิเคราะห์ทั้งหมดทำโดย ZCode harness (อ่าน note ฉบับเต็มได้ที่ [ai-node/README.md](ai-node/README.md))

---

## 2. ตารางเวลา: ZCode Automations

Automation คือ "ผู้ปลุก" — จะเรียก ZCode session ตามเวลา แล้ว session นั้นทำครบทั้ง 3 step เอง (รัน Python → วิเคราะห์เอง → finalize):

| Automation | Cron (เวลาท้องถิ่น) | ความหมาย |
|---|---|---|
| Fallen Angel daily tracker | `0 7 * * 2-6` | อังคาร–เสาร์ 07:00 น. (ครอบคลุม US close จันทร์–ศุกร์) |
| Fallen Angel weekly digest | `0 7 * * 1` | ทุกวันจันทร์ 07:00 น. |

**Prompt ฉบับเต็มอยู่ในโฟลเดอร์ [ai-node/](ai-node/)** — [daily-prompt.md](ai-node/daily-prompt.md) (อังกฤษ, มีอยู่แล้ว) และ [weekly-prompt.md](ai-node/weekly-prompt.md) (ไทย, ต้องสร้างในแชทใหม่) พร้อม [README บันทึกการตัดสินใจ](ai-node/README.md) ว่าทำไมระบบไม่มีโค้ดเรียก LLM API

ข้อควรรู้:

- **เครื่องต้องเปิด** ตอน automation ทำงาน — ถ้า Mac sleep รอบนั้นอาจถูกข้าม (รันมือแทนได้ ดู Section 5)
- ทดสอบโดยไม่ต้องรอ: สั่งในแชท ZCode ได้เลย เช่น *"รัน Fallen Angel daily pipeline ตาม automation prompt ตอนนี้"*

**Backup scheduler ด้วย crontab ของ macOS** (รันเฉพาะขั้นเก็บข้อมูล ถ้าอยากได้ข้อมูลสำรองแม้ ZCode ไม่ว่าง — วิเคราะห์ทีหลังได้เพราะ pending file รออยู่):

```cron
0 7 * * 2-6 cd /path/to/fallen_angel_tracker && .venv/bin/python main.py --mode daily >> data/cron.log 2>&1
0 7 * * 1 cd /path/to/fallen_angel_tracker && .venv/bin/python main.py --mode weekly >> data/cron.log 2>&1
```

---

## 3. โครงสร้างไฟล์ข้อมูล

```
fallen_angel_tracker/
├── data/
│   ├── daily_log.csv            ← ฐานข้อมูลหลัก 1 แถว/หุ้น/วัน (ห้ามลบ — สำรองเองได้)
│   ├── daily_input.txt          ← (optional) รายชื่อหุ้นประจำวัน, บรรทัดละ 1 ตัว
│   ├── pending/                 ← Python เขียนทิ้งไว้ให้ ZCode วิเคราะห์
│   │   ├── daily-2026-09-15.json
│   │   └── weekly-2026-W38.json
│   └── analysis/                ← ZCode เขียนผลวิเคราะห์ → finalize merge ลง CSV
│       ├── daily-2026-09-15.json
│       └── weekly-2026-W38.json
├── reports/
│   ├── daily/2026-09-15.md      ← รายงานวัน (finalize แล้วมี narrative เต็ม) — เปิดใน Obsidian ได้
│   └── weekly/2026-W38.md       ← สรุปรายสัปดาห์ 3 Section
└── output/                      ← preview HTML ตอน --dry-run
```

`daily_log.csv` คือ source of truth — **ห้ามลบ** ไม่งั้นระบบแทร็คผลตอบแทนย้อนหลังจะหาย ไฟล์ pending/analysis ลบทิ้งได้หลัง finalize แล้ว (เก็บไว้ก็เป็นประวัติการวิเคราะห์ได้เช่นกัน)

---

## 4. (ไม่บังคับ) ตั้งค่าช่องทางส่ง — Email / Discord

Weekly digest ส่งได้ 2 ช่องทางพร้อมกัน — ตั้งอันไหนก็ได้ หรือทั้งคู่:

### 4.1 Gmail App Password

1. เปิด **2-Step Verification** บนบัญชี Google ก่อน: [myaccount.google.com/security](https://myaccount.google.com/security)
2. ไปที่ [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) → สร้าง App Password → ได้รหัส **16 หลัก**
3. กรอกใน `.env`: `SMTP_USER`, `SMTP_PASSWORD` (รหัส 16 หลัก — **ห้าม**รหัสผ่านจริง), `EMAIL_TO` (ผู้รับ คั่น comma)

### 4.2 Discord Webhooks — แยกช่องรายวัน / รายสัปดาห์

ระบบรองรับ 2 webhook:

| ตัวแปรใน `.env` | ใช้เมื่อไหร่ | เนื้อหา |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | ทุกวันอังคาร–เสาร์ หลัง finalize | สรุปรายวัน 1 ข้อความ: แต่ละตัว + verdict → action + ลิงก์กราฟ |
| `DISCORD_WEBHOOK_URL_WEEKLY` | ทุกวันจันทร์ | digest 3 ข้อความ: ① ส่วนนำ+tracking ② หุ้นแนะนำ ③ บทเรียน (ไม่ตั้ง = ยิงเข้าช่อง daily แทน) |

สร้าง webhook: **Server Settings → Integrations → Webhooks → New Webhook** → ตั้งชื่อ + avatar + เลือกช่อง → **Copy Webhook URL** แล้วกรอกตามช่องทางใน `.env`
ข้อความที่โพสต์จะ **แสดงชื่อ/avatar ตามที่ตั้งไว้ในหน้า Webhooks** (เช่น "Z-Code Bot") — ถ้าอยากใช้ชื่ออื่นเฉพาะข้อความของระบบ ใส่ `DISCORD_USERNAME=<ชื่อ>` ใน `.env`

> ⚠️ **Webhook URL เป็น secret** — ใครมี URL ก็โพสต์เข้าช่องคุณได้ เก็บไว้แค่ใน `.env` (gitignored) ถ้าหลุดไปแก้ได้ที่หน้า Webhooks กด Delete แล้วสร้างใหม่

ไม่ตั้งช่องทางไหนเลยก็ได้ — weekly จะบันทึกลง `reports/weekly/*.md` ให้อยู่ดี และ `--dry-run` เซฟ preview HTML ที่ `output/`

---

## 5. รันด้วยมือ (ทดสอบ / ใช้งานเอง)

```bash
cd fallen_angel_tracker
python3 -m venv .venv && source .venv/bin/activate   # ครั้งแรกครั้งเดียว
pip install -r requirements.txt
cp .env.example .env                                  # แล้วกรอกค่าที่ใช้

# ---- Flow ปกติ (3 คำสั่ง, ขั้น 2 คือ ZCode) ----
python main.py --mode daily                 # 1) เก็บข้อมูล → data/pending/daily-*.json
# 2) ให้ ZCode วิเคราะห์: สั่งในแชทว่า
#    "อ่าน fallen_angel_tracker/data/pending/daily-<date>.json วิเคราะห์ Moat Impairment Test
#     แล้วเขียนผลเป็น data/analysis/daily-<date>.json ตาม schema ใน automation prompt"
python main.py --mode finalize              # 3) merge → CSV + reports/daily/*.md

python main.py --mode weekly                # 1) สร้าง pending รายสัปดาห์
# 2) ZCode เขียน data/analysis/weekly-<Www>.json (narratives + mini-lesson)
python main.py --mode finalize --weekly     # 3) merge → reports/weekly/*.md + email/Discord

# ---- คำสั่งเสริม ----
python main.py --mode daily --tickers UNH,TGT --dry-run   # ดูอย่างเดียว ไม่เขียนไฟล์
python main.py --mode finalize --weekly --dry-run         # preview อีเมลที่ output/
python main.py --mode finalize --date 2026-09-15          # finalize ย้อนวัน
```

Input รายชื่อหุ้นประจำวันมี 3 ชั้น (บนมี priority กว่า): `--tickers` → ไฟล์ `data/daily_input.txt` → `WATCHLIST` ใน `.env`

---

## 6. ปรับ Framework ตามชอบ

ค่า threshold อยู่ใน `config.py`:

| ค่า | Default | ความหมาย |
|---|---|---|
| `MAX_NET_DEBT_EBITDA` | 3.0x | Flag เตือนหนี้สุทธิเกิน 3 เท่า EBITDA |
| `MIN_INTEREST_COVERAGE` | 5.0x | Coverage ต้องไม่ต่ำกว่านี้ |
| `MIN_FCF_YIELD` | 3.0% | FCF ต้องบวก "และแข็งแกร่ง" ตามสเปค |
| `MIN_DISCOUNT_FOR_BUY` | 15% | ส่วนลดขั้นต่ำถึงจะพิจารณาเข้าไม้ |
| `POSITION_CAP_MIN/MAX` | 5–8% | เพดานขนาดพอร์ตต่อตัว |
| `FIRST_TRANCHE_MIN/MAX` | 25–30% | สัดส่วนไม้แรกของ position เป้าหมาย |

Verdict 3 ค่า: `Pass - Temporary` (ข่าวร้ายชั่วคราว → จังหวะซื้อ), `Watch` (สัญญาณปน), `Fail - Value Trap` (ความเสียหายเชิงโครงสร้าง) — rule-based ให้ verdict ตั้งต้นจากตัวเลขเสมอ แล้ว ZCode ยืนยันหรือโต้แย้งในขั้นวิเคราะห์ (finalize ใช้คำตอบของ ZCode เป็นตัวตั้ง)

Fair Value เป็น proxy 3 ชั้น: `FAIR_VALUE_OVERRIDES` (แนะนำ เช่น `UNH=520`) → Analyst Target Mean → EPS × P/E ประมาณ

---

## 7. Troubleshooting

| อาการ | สาเหตุ/วิธีแก้ |
|---|---|
| `finalize` บอก no analysis file | ยังไม่มีใครเขียน `data/analysis/daily-<date>.json` — ให้ ZCode วิเคราะห์ก่อน (prompt อยู่ที่ ai-node/) |
| `finalize` บอก skipping TGT | ไฟล์ analysis ไม่มี ticker นั้น หรือวันที่ไม่ตรงกับแถวใน CSV — เช็ค `"date"` ใน JSON กับคอลัมน์ Date (แก้ด้วย `--date`) |
| Weekly แทร็คผลตอบแทนไม่ได้ / ตารางว่าง | `daily_log.csv` ถูกลบ — ต้องมีอย่างน้อย 1 แถวที่ Action ≠ Avoid |
| Automation ไม่ยิง | เครื่อง/ZCode ปิดหรือ sleep อยู่ตอนนั้น — รันมือ `python main.py --mode daily` แทนรอบนั้นได้ |
| Gmail `535 Bad Credentials` | ใช้รหัสผ่านจริงแทน App Password หรือยังไม่เปิด 2FA |
| Fair Value / Discount ว่าง | ไม่มี override, analyst target และ EPS ก็ไม่พอ — กรอก `FAIR_VALUE_OVERRIDES` |
| yfinance ดึงข้อมูลไม่ครบบางตัว | ปกติสำหรับ ADR/REIT — ดูคอลัมน์ `Data Warnings` ใน CSV |

---

## 8. คำเตือน

ระบบนี้เป็นเครื่องมือการศึกษาและการจัดการวงจรวิจัยหุ้นอัตโนมัติ **ไม่ใช่คำแนะนำการลงทุน** Fair Value เป็นค่าประมาณจาก feed ฟรี ควรตรวจสอบงบการเงินและข่าวสารด้วยตนเองก่อนตัดสินใจทุกครั้ง — "ปากกาชนกระดาษก่อนเงินออกจากกระเป๋า" เสมอ
