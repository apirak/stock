# 🤖 Automation Prompts — Falling Angle Tracker (reference)

ไฟล์นี้คือ **สำเนา prompt ฉบับปัจจุบัน** ของ ZCode Automations ทั้งสามตัว
ใช้เป็นต้นฉบับเมื่อต้อง (1) ย้าย automation ไป session ใหม่ (2) สร้างซ้ำหลังลบ (3) ตรวจว่าของจริงตรงกับ reference หรือไม่

> **กติกาการ sync:** ไฟล์ในโฟลเดอร์นี้ ↔ automation ใน ZCode ต้องตรงกันเสมอ
> แก้ฝั่งไหนต้องอัปเดตอีกฝั่ง (แก้ใน chat ที่เป็นเจ้าของ automation ด้วย CronUpdate หรือแจ้งผู้ใช้แก้ใน UI)

## ตาราง automations ปัจจุบัน

| ชื่อ | Cron | ทำอะไร | ไฟล์ prompt |
|---|---|---|---|
| Daily Stock | `0 7 * * 2-6` | daily pipeline (Feb) → Discord ช่อง daily | [daily-prompt.md](daily-prompt.md) |
| Weekly Stock | `0 9 * * 1` | weekly digest (Feb ไทย) → Discord ช่อง weekly 3 ข้อความ | [weekly-prompt.md](weekly-prompt.md) |
| Fallen Angle - Gmail | `0 9 * * *` | เก็บจดหมาย Jan → `fallen_angel/` + git commit | [gmail-prompt.md](gmail-prompt.md) |

## เรื่อง session ของ automation (สำคัญ)

Automation แต่ละตัว **ผูกกับ session ที่สร้างมัน** — ทุกครั้งที่ cron ยิง prompt จะถูกส่งเข้า session นั้นและรันต่อด้วยประวัติเต็มของ session นั้น

- ถ้าสร้าง automation ใน **แชทรวมที่ยาวมาก** → ทุกรอบจะจ่ายค่า context ของทั้งแชท (แพงและเสี่ยง summarization)
- ถ้าสร้างใน **แชทเฉพาะกิจที่ว่าง** (เหมือนที่ Gmail archiver ใช้) → runs จะเกิดใน session สะอาด prompt เองก็ self-contained (อ่านไฟล์/state จาก repo ทั้งหมด) จึงทำงานได้ครบโดยไม่ต้องมีประวัติแชท

**แนวปฏิบัติที่ดี:** 1 automation = 1 แชทเฉพาะกิจที่สร้างไว้เลย (และจำกัด 1 automation ต่อ session อยู่แล้ว) — ถ้าแชทเจ้าของยาวจนเริ่มอึดอัด ย้ายได้ตามขั้นตอน: เปิดแชทใหม่ → สร้าง automation ด้วย prompt จากโฟลเดอร์นี้ → ลบตัวเก่าในแชทเดิม

---

*โครงสร้างโค้ด: `src/` (pipeline) · knowledge: `watchlist/stock_knowledge/` · สัญญา format: `_GUIDELINE.md` · หลักการ: `knowledge/falling_angle.md`*
