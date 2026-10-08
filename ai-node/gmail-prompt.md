# Fallen Angle - Gmail — prompt ฉบับปัจจุบัน (copied from live automation 2026-10-01)

- **Cron:** `0 9 * * 1` (ทุกวัน 09:00 น.)
- **แชทเจ้าของ:** session เฉพาะกิจที่สร้างไว้แยกต่างหาก (ต้นแบบที่ daily จะย้ายไปเทียบ)

```text
ตรวจและเก็บจดหมาย "[Fallen Angel with Jan]" ประจำวันเข้า archive ของ repo นี้

1. รันคำสั่ง:
   cd /Users/apirak/workspace/stock/src && .venv/bin/python fallen_angel_inbox.py --since-days 3

2. ตีความผล:
   - บรรทัด "[inbox] archived <TICKER> <date> ..." = มีจดหมายใหม่ถูกเก็บ →
     อ่าน FA tag (บรรทัด <!-- FA: ... -->) ในไฟล์
     watchlist/stock_knowledge/fallen_angel/<TICKER>/<TICKER>_fallen_angel_<YYYY>.md
     แล้วสรุปให้ผู้ใช้สั้น ๆ ต่อ ticker: ชื่อบริษัท, ราคา (price), Fair Value (fv),
     ส่วนลด (mos), P/E และลิงก์ไฟล์ archive
   - "already archived — skipped" หรือ "nothing to do" = ไม่มีของใหม่ →
     ตอบสั้นหนึ่งบรรทัดว่าไม่มีจดหมายใหม่ แล้วจบ ไม่ต้องทำอย่างอื่น
   - "[inbox] no ticker found -> filed under _inbox/..." = มีจดหมายที่หา ticker
     ไม่เจอ → แจ้งผู้ใช้ว่ามีจดหมายรอจัดการมือที่
     watchlist/stock_knowledge/fallen_angel/_inbox/ แล้วจบ (ห้ามแก้/ย้ายเอง)

3. ถ้ามีจดหมายใหม่ถูกเก็บ (กรณีแรกในข้อ 2): git add เฉพาะ
   watchlist/stock_knowledge/fallen_angel/ และ watchlist/stock_knowledge/index.md
   แล้ว commit ข้อความ "fallen-angel inbox: archive <N> new email(s) (<TICKERS>)"
   — ห้าม push

4. ข้อห้ามและการจัดการ error:
   - ห้ามอ่าน แก้ หรือแสดงเนื้อหาไฟล์ .env เด็ดขาด (มีรหัสผ่าน) — ถ้า script
     ออกข้อความ "missing Gmail credentials" หรือ "GMAIL_APP_PASSWORD is N chars"
     ให้คัดลอกข้อความนั้นแจ้งผู้ใช้ว่าต้องไปสร้าง/แก้ App Password เอง แล้วจบ
     ไม่ต้องพยายามแก้ไฟล์ .env แทน
   - ห้ามแก้ไฟล์ archive หรือแถวใน index.md ด้วยมือ — ทุกอย่างเขียนโดย script เท่านั้น
   - ถ้าเจอ IMAP/network error ให้แจ้งสั้น ๆ แล้วจบ (รอบถัดไปกวาดย้อนหลัง 3 วันให้เอง)
     retry ได้มากสุดครั้งเดียวต่อรอบ

5. ถ้าสถานการณ์ทำให้ต้องแตะไฟล์ใน watchlist/stock_knowledge/ ด้วยตัวเอง
   (นอกจาก git add ในข้อ 3) หรือเจอกรณีที่ prompt นี้ไม่ครอบคลุม:
   ให้อ่าน watchlist/stock_knowledge/_GUIDELINE.md ก่อนเสมอ โดยเฉพาะ §9
   (กติกา folder fallen_angel/) — หลักการคือ bot เพิ่มข้อมูลได้อย่างเดียว
   ห้ามแก้ของเดิม และการเปลี่ยนสถานะหุ้นเป็นสิทธิ์ของผู้ใช้
```
