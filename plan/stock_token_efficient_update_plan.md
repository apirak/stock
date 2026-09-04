# แผน: ระบบอัปเดตหุ้นแบบประหยัด Token (2 งานแยกกัน)

สร้างเมื่อ: 2026-09-03
อ้างอิง spec: obsedian/plan/stock.md, obsedian/plan/price_vs_intrinsic_value_rule.md
ฐานข้อมูล: obsedian/knowledge/stock/

---

## ข้อเท็จจริงที่เทสแล้ว (2026-09-03) — ตัวกำหนดแผน

| แหล่ง | ยิงครั้งเดียวได้หลายตัว? | Free tier | ใช้ทำอะไร |
|---|---|---|---|
| Yahoo `/v8/finance/spark?symbols=A,B,C` | ✅ ได้ทั้ง 20 ตัวใน 1 call (รวม .BK ไทย) | ✅ ไม่ต้องมี key | **ราคารายวัน — เครื่องยนต์หลัก** |
| FMP `/stable/quote?symbol=A,B,C` | ❌ batch ถูกบล็อก (Premium) | ✅ เฉพาะทีละตัว | ราคา cross-check เฉพาะตอน research |
| FMP `/stable/profile, key-metrics, ratios, price-target-consensus, discounted-cash-flow, income/balance/cash-flow` | ❌ ทีละตัวเท่านั้น | ✅ ~250 calls/วัน | **งานพื้นฐาน (งานที่ 1)** |
| FMP `/stable/news*` | ❌ ถูกบล็อกทั้ง endpoint | ❌ | ใช้ไม่ได้ — ใช้ Google News RSS / web_search แทน |
| Google News RSS (`news.google.com/rss/search?q=TICKER`) | ทีละตัว แต่ parse ด้วย script ได้ | ✅ ไม่ต้องมี key | **ข่าวรายวัน — กรองด้วย script ก่อน ไม่ผ่าน LLM** |
| Yahoo `/v7/finance/quote` | ❌ Unauthorized | ❌ | ไม่ใช้ |
| SEC EDGAR | ทีละตัว | ✅ | primary source ตอน research เชิงลึก |

**บทเรียนจากรอบแรก (2026-08-29):** subagent 7 ตัววิ่งพร้อมกัน ตัวละ 8-12 tool calls โดนโควต้าโมเดลรายสัปดาห์ตัดกลางคัน → งานค้าง 19 ตัว แผนนี้ออกแบบมาเพื่อไม่ให้เกิดซ้ำ

---

## หลักการประหยัด Token 3 ข้อ

1. **Script เก็บข้อมูล, LLM คิดเท่านั้น** — ทุกการดึงข้อมูล (ราคา/งบ/ข่าว) ทำด้วย script curl+python ล้วน 0 token; LLM ได้รับเฉพาะ JSON สรุปกะทัดรัด (~2-4 KB/ตัว) ไม่ต้องวน loop เรียก tool เอง
2. **LLM ตื่นเฉพาะเมื่อมีเหตุ** — วันปกติ script คำนวณ MoS + กรองข่าวเอง; agent ถูกปลุกเฉพาะเมื่อ trigger ยิง (cron `monitor` gate)
3. **ทำตาม Revaluation Discipline** — ราคาเปลี่ยน = อัปเดต MoS ด้วย script ไม่ revalue; revalue เฉพาะเมื่อสมมติฐานเปลี่ยนจริง (งบ/ guidance/ moat)

---

## งานที่ 1: Update พื้นฐานให้ครบทุกตัว (one-time, 19 ตัวคงค้าง)

### สถาปัตยกรรม: 2 ชั้น (script pre-fetch → subagent เขียนไฟล์)

**ชั้น A — Script pre-fetch (0 token):**
สคริปต์เดียว `prefetch_ticker.py TICKER` ยิง FMP 6-9 ครั้ง + Yahoo 1 ครั้ง แล้วบีบเป็น `TICKER_facts.json` (~2-4 KB):

| Endpoint | หุ้นที่ถือ (7 ตัว) | Watchlist (12 ตัว) |
|---|---|---|
| profile, quote | ✅ | ✅ |
| key-metrics, ratios | ✅ | ✅ |
| income + balance + cash-flow (4 ปี) | ✅ | ❌ (ใช้ key-metrics แทน) |
| price-target-consensus, DCF | ✅ | ✅ |
| Yahoo spark (cross-check ราคา) | ✅ | ✅ (ยิงรวม batch เดียว) |

- งบ FMP: หุ้นที่ถือ 9 calls × 7 = 63; watchlist 5 calls × 12 = 60 → รวม **~123 calls** (งบ 250/วัน เหลือเฟือ)
- หมายเหตุ: KKP, XIAOMI80 เป็นหุ้นไทย — FMP ไม่มี ใช้ Yahoo + web_search แทน; SPCX คือหุ้นไทยเพิ่ง IPO (ยืนยันจาก user แล้ว) — Yahoo ยังไม่มี symbol, research ผ่าน web_search
- **พบเพิ่ม (2026-09-03): FMP free tier ครอบคลุมเฉพาะหุ้น large-cap บางตัว** — GDS, IREN, MU, BEKE, NTES ได้แค่ profile ที่เหลือ HTTP 402 → 5 ตัวนี้ research ด้วย Yahoo + web_search เป็นหลัก

**ชั้น B — Subagent เขียน research (token น้อยกว่ารอบแรก ~3-5 เท่า):**
- รับ facts.json เข้าไปตรงๆ + อนุญาต web_search เพิ่มได้แค่ 1-2 ครั้ง (ข่าว/thesis) → เขียน 3 ไฟล์ตาม spec
- **ทีละ 2-3 ตัวต่อวัน** (ไม่พร้อมกัน 7 ตัวเหมือนรอบแรก) เพื่อไม่ให้โควต้ารายสัปดาห์หมด
- ลำดับ: หุ้นที่ถือ 7 ตัว (MSFT GOOGL NFLX GDS IREN TSLA AMD) → watchlist 12 ตัว
- Watchlist ใช้เวอร์ชัน "lite": 3 ไฟล์เหมือนกันแต่กะทัดรัดกว่า (valuation อิง multiples + analyst targets เป็นหลัก ไม่ทำ DCF เองเต็มรูปแบบ)

### ขั้นตอนปฏิบัติ

1. เขียน `prefetch_ticker.py` (รองรับทั้ง US/ไทย, จัดการ error, เขียน JSON ลง `_facts/`)
2. รัน pre-fetch ทั้ง 19 ตัว (script ล้วน, ทำได้ทีเดียว)
3. ยืนยันตัวตน SPCX กับ user ก่อน research ตัวนั้น
4. วันละ 2-3 subagent → ครบ 19 ตัวภายใน ~7-9 วัน
5. ตัวสุดท้ายของแต่ละชุด: อัปเดต watch_list.md (Opportunity Status จาก TBD → ค่าจริง)

### งบประมาณโดยประมาณ
- Token: ~1 subagent เบาๆ ต่อตัว (facts เข้าตรง, ไม่วน tool) แทน ~10 tool-call loops
- FMP: ~123 calls รวม (จ่ายครั้งเดียวตอน pre-fetch)
- เวลา: 7-9 วัน (จำกัดที่โควต้าโมเดล ไม่ใช่ API)

---

## งานที่ 2: Update รายวัน (recurring, 3 ระดับ)

### ระดับ 0 — Script รายวัน (0 token, ทุกวัน)

cron script (`daily_scan.py`) ทำงาน 1 รอบ/วัน เวลา **19:00 น. (+07)**:
- เหตุผลเวลา: US ปิดตลาด 03:00-04:00 +07, SET ปิด 16:30 +07 → 19:00 ได้ข้อมูลปิดครบทั้งสองตลาดในรอบเดียว
- ทำอะไรบ้าง:
  1. Yahoo spark 1 call → ราคาปิดทั้ง 20 ตัว
  2. อ่าน Bear/Base/Bull จาก `TICKER_current_status.md` ทุกตัว (grep field ที่กำหนด format ไว้) → คำนวณ MoS ปัจจุบันเชิงกลไก
  3. ดึง Google News RSS ต่อตัว (20 calls, ไม่มี key) → กรองด้วย keyword heuristic (earnings/guidance/downgrade/lawsuit/...) เก็บเฉพาะ headline+link ที่เข้าข่าย
  4. เขียน `_daily/YYYY-MM-DD_scan.md` (ตารางราคา+MoS+ข่าวที่เข้าข่าย) และ `trigger file`
- **Trigger ที่ปลุก agent (ระดับ 1):**
  - ราคาเปลี่ยว ≥ ±5% ในวันเดียว
  - MoS ข้ามเกณฑ์ (เข้าโซน ≥20% หรือหลุดจากที่เคยมี)
  - มีข่าวเข้าข่าย material จาก heuristic
  - งบประจำไตรมาสออก (รายการวัน earnings เก็บในไฟล์ calendar)

### ระดับ 1 — Agent สรุปรายวัน (token น้อย, เฉพาะวันที่มี trigger)

- cron ใช้ `monitor` = script ข้างบน → agent ตื่นเฉพาะเมื่อ trigger file เปลี่ยน
- agent อ่านเฉพาะ: scan file วันนี้ + current_status ของตัวที่ trigger (ไม่อ่านทั้งฐาน)
- ตัดสินตาม spec: noise หรือ fundamental / Temporary Mispricing หรือ Value Trap Risk
- อัปเดตเฉพาะไฟล์ที่เกี่ยว + เขียน `_daily/YYYY-MM-DD.md` + ส่ง Discord #stock (webhook มีอยู่แล้ว)
- วันที่ trigger เป็นแค่ราคาขยับเล็กน้อย: อาจตอบสั้น "No compelling opportunity today."

### ระดับ 2 — Deep dive (เฉพาะ major event)

- เงื่อนไขตาม spec: earnings surprise, guidance cut, >10% move พร้อมข่าว, fraud, CEO ลาออก ฯลฯ
- dispatch subagent 1 ตัวต่อหุ้น 1 ตัวที่เกิดเหตุ (เหมือน flow งานที่ 1 แต่อัปเดตไฟล์เดิม)
- วันไม่มีเหตุ = 0 token ส่วนนี้

### งบประมาณรายวันโดยประมาณ
- วันปกติ (ไม่มี trigger): **0 token** — ได้ scan file ดูเอง + (ทางเลือก) ส่ง Discord อัตโนมัติด้วย script template ภาษาไทย
- วันมี trigger ทั่วไป: 1 agent run เบาๆ
- วัน major event: 1 subagent ต่อตัวที่เกิดเหตุ
- FMP: 0-2 calls/วัน (ใช้เฉพาะตอน deep dive) → งบ 250/วันเหลือเผื่อ revalue รายไตรมาส

### Revalue เชิงโครงสร้าง (ไม่ใช่รายวัน)
- รายไตรมาส: หลังงบ Q ออก → pre-fetch ใหม่เฉพาะตัวนั้น + subagent revalue (ตาม Revaluation Discipline)
- รายสัปดาห์ (เสาร์): script เช็กว่าราคาห่างจาก Base FV > ±15% ตัวไหน → flag ให้ agent พิจารณา revalue เฉพาะตัว

---

## ขั้นตอนรวมที่จะทำ (หลัง user อนุมัติแผน)

- [ ] Phase 0: เขียน `prefetch_ticker.py` + `daily_scan.py` (ทดสอบกับ NVDA ก่อน 1 ตัว)
- [ ] Phase 1: pre-fetch 19 ตัว + ยืนยัน SPCX
- [ ] Phase 2: research หุ้นที่ถือ 7 ตัว (วันละ 2-3 ตัว)
- [ ] Phase 3: research watchlist 12 ตัว แบบ lite
- [ ] Phase 4: ตั้ง cron ระดับ 0 (ทุกวัน 19:00) + cron ระดับ 1 (monitor-gated)
- [ ] Phase 5: user ส่งข้อมูล transaction → เติม ledger.md + assets.md (ทำเมื่อไหร่ก็ได้)

## ข้อตัดสินใจจาก user (2026-09-03) — ยืนยันแล้ว

1. **SPCX** = หุ้นไทยเพิ่ง IPO เข้าตลาด — เก็บไว้ในฐานข้อมูลเพื่อสะสมข้อมูลย้อนดูภายหลัง research แบบ best-effort (ข้อมูลจะบาง ยอมรับได้)
2. **Token budget: ≤ 1 ล้าน token/วัน** → pace มาตรฐาน 3 ตัว/วัน (subagent ตัวละไม่เกิน ~300K) ครบ 19 ตัวใน ~7 วัน
3. **Google News RSS**: ถ้าเรียกไม่ได้วันไหน ข้ามชั้นข่าวไปเลย ไม่ต้อง fallback ไป web_search (ประหยัด token) — ใช้ trigger จากราคาอย่างเดียววันนั้น
4. **หุ้นไทย (KKP, XIAOMI80, SPCX)**: เอาเท่าที่ได้จาก Yahoo + web_search — ไม่บังคับครบทุก section
5. **Watchlist แบบ lite**: เห็นด้วย — ถ้าตัวไหนขึ้น Attractive ค่อยอัปเกรดเป็น full research

## ความเสี่ยงที่เหลือ

1. **โควต้าโมเดลรายสัปดาห์** ยังเป็นข้อจำกัดหลัก (1M/วัน × 7 วัน อาจเกิน weekly cap ถ้า cap ต่ำกว่า 7M) → ถ้าโดนตัดกลางคันอีก ให้พักแล้วทำต่อวันถัดไป งานออกแบบให้ resume ได้ (ตัวไหนมีไฟล์ครบ 3 ไฟล์แล้วข้าม)
2. **หุ้นไทย** ข้อมูลจะบางกว่าหุ้น US — ยอมรับตามข้อ 4
3. วันที่ RSS พัง รายงานจะขาดมุมข่าว — ระบุใน scan file วันนั้นว่า "news layer unavailable"

## Convention เพิ่มเติม (สำหรับ subagent ทุกตัว)

ทุกไฟล์ `TICKER_current_status.md` ต้องมีบรรทัด machine-readable ใต้หัวข้อ Valuation เสมอ:

`<!-- FV: bear=<low>-<high> base=<low>-<high> bull=<low>-<high> price=<ราคาอ้างอิง> asof=<YYYY-MM-DD> -->`

เพื่อให้ `daily_scan.py` คำนวณ MoS ได้โดยไม่ต้องใช้ LLM parse (มี regex fallback สำหรับไฟล์เก่า)
