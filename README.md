# 🌷 Falling Angle Watchlist System

ระบบรวมข้อมูลหุ้น + ผู้ช่วยวิเคราะห์ Value Investing สาย **Falling Angle** (ล่าหุ้น wide-moat
ที่ราคาลงต่ำกว่ามูลค่าจริงแบบชั่วคราว) พร้อมรายงานรายวัน/รายสัปดาห์บน Discord โดย
**Feb 🌷** — เพื่อนสาวนักลงทุนผู้รายงานตรงไปตรงมา ไม่ขายฝัน ไม่มั่งมีคำแนะนำ

## แผนที่ระบบ

| ทาง | คืออะไร | ใครเขียน |
|---|---|---|
| `watchlist/stock_knowledge/index.md` | **Universe** — ตารางหุ้นทั้งหมด (Status: Owned/Watch) — single source of truth | ผู้ใช้ผ่าน ZCode + bots อัปเดต Last Review |
| `watchlist/stock_knowledge/_GUIDELINE.md` | 📐 **สัญญา format** ของไฟล์หุ้นทุกตัว — bot/คน ต้องอ่านก่อนสร้าง/แก้ไฟล์ | คน + sessions |
| `watchlist/stock_knowledge/own/<TICKER>/` | research ต่อหุ้นที่ถือ (`_overall`, `_current_status`, `_news_YYYY`) | bots (daily/weekly/session) |
| `watchlist/stock_knowledge/watchlist/<TICKER>/` | research ต่อหุ้นที่ดูไว้เฉย ๆ | bots |
| `watchlist/stock_knowledge/ledger.md` | **ประวัติซื้อขาย append-only** — พอร์ต derive จากไฟล์นี้ | เฉพาะเมื่อผู้ใช้บอกเอง |
| `watchlist/_daily/` | brief รายวัน | Daily bot |
| `weekly/` | คำแนะนำรายสัปดาห์ (แนว Falling Angle) | Weekly bot |
| `knowledge/` | "หนังสือ" หลักการลงทุน — [`falling_angle.md`](knowledge/falling_angle.md) คือแกนที่ทุก bot ใช้ | คน + sessions |
| `src/` | **โค้ด + tests ทั้งหมด** — วิธีเรียกใช้แต่ละฟังก์ชันอยู่ที่ [`src/README.md`](src/README.md) | — |
| `plan/` | spec ต้นทาง (stock.md = VI system spec, token-efficient plan = กลยุทธ์ข้อมูลฟรี) | — |
| `charactor/` | ตัวละครทั้งหมด (ยังใช้งานทุกตัว) — **Feb** 🌷 ผู้รายงาน Watch list ของระบบนี้ · Jan (ตัวก่อนหน้า + รูป falling-angel 3 สถานะ) · Belldandy / Urd / Skuld (เทพธิดา Oh My Goddess) | ผู้ใช้ |

## Bot ประจำวัน / ประจำสัปดาห์ (ZCode Automations)

| Automation | เวลา | ทำอะไร | ส่งไหน |
|---|---|---|---|
| **Daily Stock** | อังคาร–เสาร์ 07:00 (ครอบคลุม US close) | ดึงราคา/งบ/ข่าว → Moat Impairment Test → อัปเดต research ต่อหุ้น → brief รายวัน | Discord **Daily** (Feb 🌷) |
| **Weekly Stock** | ทุกวันจันทร์ 09:00 | ติดตามผลแนะนำเก่า → คัดหุ้นผ่านเกณฑ์ Falling Angle → แผน 3 ไม้ + บทเรียน | Discord **Weekly** (Feb 🌷, 3 ข้อความ) |

Webhook ทั้งสองอยู่ใน `.env` (gitignored)

## วิธีใช้ร่วมกับ ZCode (ผู้ใช้)

- **"ผมซื้อ NVDA 2 หุ้นที่ $220"** → session append `ledger.md` + ย้าย folder/สถานะใน index.md
  (bot ใช้ `src/ledger.py` + `src/universe.py`)
- **เพิ่มหุ้นใหม่ใน watchlist** → session เพิ่มแถวใน index.md + สร้าง folder research
- รัน pipeline เอง: `cd src && .venv/bin/python main.py --mode daily` (ดู CLI ทั้งหมดใน src/README.md)

## หลักการเหล็ก (สรุปจาก knowledge/falling_angle.md)

1. ราคาลง ≠ ถูก — ต้องเทียบราคากับมูลค่าที่แท้จริงเสมอ (MoS)
2. แยกให้ออก: แผลชั่วคราว (Fallen Angel) vs ธุรกิจพังถาวร (Value Trap)
3. คุณภาพมาก่อนถูก: moat ระบุแหล่งได้ + ROIC > WACC + งบดับรอดพายุ
4. เข้าซื้อ 3 ไม้ + เขียน invalidation criteria ก่อนไม้แรก
5. ระบบนี้ช่วยวิเคราะห์ — การตัดสินใจซื้อขายเป็นของเจ้าของพอร์ตเสมอ

---

*เครื่องมือเชิงการศึกษา ไม่ใช่คำแนะนำการลงทุน — ข้อมูลมาจาก feed ฟรี (yfinance) Fair Value เป็นค่าประมาณ*
