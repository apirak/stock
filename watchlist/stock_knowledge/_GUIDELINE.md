# 📐 Guideline — รูปแบบการเก็บข้อมูลหุ้น (สำหรับทุก ticker)

> ไฟล์นี้คือ **สัญญา format** ของ `stock_knowledge/` — bot ทุตัว (Daily / Weekly / session)
> ต้องอ่านและทำตามไฟล์นี้ก่อนสร้างหรือแก้ไฟล์หุ้น ผู้ใช้ก็ใช้เป็น checklist ได้
> ที่มา: รวม spec จาก `plan/stock.md` + `plan/stock_token_efficient_update_plan.md` ให้ใช้ที่เดียว

---

## 1. โครงสร้าง folder ต่อหุ้น

```
stock_knowledge/
├── _GUIDELINE.md            ← ไฟล์นี้ (ห้ามสร้าง folder ชื่อขึ้นต้น _)
├── index.md                 ← universe table (single source of truth — แก้ผ่าน universe.py เท่านั้น)
├── ledger.md                ← ประวัติซื้อขาย append-only (ห้าม bot เขียนเอง)
├── own/<TICKER>/            ← สถานะ Owned
│   ├── <TICKER>_overall.md
│   ├── <TICKER>_current_status.md
│   └── <TICKER>_news_<YYYY>.md
└── watchlist/<TICKER>/      ← สถานะ Watch (โครงเหมือนกัน แต่ tier Lite)
```

**กติกาตั้งชื่อ (บังคับเป๊ะ):**
- Folder = ticker **ตัวพิมพ์ใหญ่หมด** เช่น `NVDA/` (ยกเว้นหุ้นไทย/DR ใช้ symbol ตาม SET)
- ไฟล์ = `<TICKER>_overall.md` · `<TICKER>_current_status.md` · `<TICKER>_news_<YYYY>.md`
- ข่าวแยก **1 ไฟล์ต่อปี** — ขึ้นปีใหม่เปิดไฟล์ใหม่ (`_news_2027.md`) ห้ามรวมไฟล์เดียวยาวไม่รู้จบ
- ห้ามไฟล์อื่นนอกจาก 3 ชนิดนี้ (ไม่มี scratch/note หลุดเข้ามา)

**ย้ายตำแหน่ง:** พอสถานะเปลี่ยน (ซื้อ/ขาย) ย้ายทั้ง folder ระหว่าง `own/` ↔ `watchlist/`
ด้วย `universe.move_ticker_folder()` — พร้อมอัปเดตคอลัมน์ Status ใน index.md และบันทึก ledger

---

## 2. สองระดับความลึก (tier)

| | Full (default) | Lite |
|---|---|---|
| ใช้กับ | หุ้นที่ **Owned** ทุกตัว + Watch ที่ขึ้น Opportunity Status `Attractive` ขึ้นไป | Watch ทั่วไป (เริ่มต้น) |
| `_overall.md` | ครบทุก section ตาม §3 | ครบแต่กระชับ — Business Model/Revenue Drivers รวบเป็น bullet สั้น |
| `_current_status.md` | ครบทุก section + FV tag | ครบ แต่ valuation อิง analyst consensus + multiples เท่านั้น (ไม่ทำ DCF เอง) |
| `_news_<YYYY>.md` | เหมือนกัน | เหมือนกัน |

อัปเกรด Lite → Full เมื่อตัวนั้นเข้าเกณฑ์น่าสนใจจริง (MoS ≥ 20% + moat ชัด) — อย่าอัปเกรดทุกตัว
เพราะแพง (token + API quota)

---

## 3. `<TICKER>_overall.md` — ความรู้ธุรกิจที่เปลี่ยนช้า (ห้าม rewrite ทุกวัน)

บังคับมีหัวข้อตามนี้ครบ (ชื่อ header เป๊ะ เพราะ bot ใช้ grep หาได้):

```
# <TICKER> — Overall Company Research
## Company Overview          (ชื่อบริษัท/exchange/ประเทศ/อุตสาหกรรม/market cap/FY + "Identity verified: Yes/No")
## Business Model            (ขายอะไร ใครจ่าย ทำไมลูกค้าซื้อ — อธิบายแบบคนไม่รู้จักบริษัทอ่านรู้เรื่อง)
## Revenue Drivers           (ตัวแปรที่ขับรายได้/margin/FCF)
## Industry Structure        (ขนาดตลาด การเติบโต ความ cyclicality กฎระเบียบ)
## Competitive Position      (คู่แข่ง ส่วนแบ่ง switching cost network effect)
## Moat                      (Rate: Strong/Moderate/Weak/Unclear + **ระบุแหล่ง moat ชัดเจน**)
## Management                (คุณภาพ capital allocation ความสม่ำเสมอของผู้ถือหุ้น)
## Financial Quality         (เลือก metric ที่เหมาะกับธุรกิจ: ROIC, margin trend, debt, SBC, cash conversion)
## Capital Allocation        (reinvest/M&A/buyback/dividend/issuance)
## Major Risks               (แยก business/financial/competitive/regulatory/tech)
## Long-Term Investment Thesis   (3-5 ข้อ ทำไมบริษัทนี้สมควรลงทุน)
## Thesis-Breaking Conditions    (เงื่อนไขที่สังเกตได้จริงที่ทำให้ thesis ล้ม — เขียนตอนสร้างไฟล์)
## Relevant Valuation Methods   (วิธีประเมินที่เหมาะกับธุรกิจนี้ + เหตุผล)
```

อัปเดตเฉพาะเมื่อ: โครงสร้างธุรกิจเปลี่ยน (M&A ใหญ่, segment ใหม่, คู่แข่งเปลี่ยนเกม) —
ไม่ใช่ทุกวัน ไม่ใช่เพราะราคาขยับ

---

## 4. `<TICKER>_current_status.md` — มุมมองปัจจุบัน (อัปเดตเมื่อมีข้อมูลใหม่ที่มีนัยสำคัญ)

บังคับมีหัวข้อครบ + สิ้นสุดด้วย FV tag:

```
# <TICKER> — Current Status
## Current Snapshot          (วันที่ update, ราคา, market cap, metric ล่าสุด)
## Current Business Condition: **Improving|Stable|Mixed|Deteriorating**   (+ เหตุผล)
## Current Thesis Status: **Strengthening|Intact|Slightly Weakened|At Risk|Broken**
## Recent Material Changes   (เฉพาะของที่ matter ตอนนี้ — ไม่ใส่ noise)
## Valuation
## Opportunity Status: **High Conviction|Attractive|Watch|Fairly Valued|Overvalued|Temporary Mispricing Candidate|Value Trap Risk|Thesis Broken**
## Research Priority: **High|Medium|Low**
## Key Catalysts
## Key Risks
## What Could Change My Mind
## Next Things to Monitor
```

**Opportunity Status ห้ามใช้คำว่า "BUY"** — ระบบนี้เป็นผู้ช่วยวิจัย ไม่ใช่ผู้สั่งซื้อ

### FV machine tag (บังคับ — script ใช้อ่านค่านี้คำนวณ MoS)

ใต้หัวข้อ `## Valuation` ต้องมีบรรทัดนี้เสมอ (syntax เป๊ะ):

```
<!-- FV: bear=<low>-<high> base=<low>-<high> bull=<low>-<high> price=<ราคาอ้างอิง> asof=<YYYY-MM-DD> -->
```

ตัวอย่างจริง: `<!-- FV: bear=260-320 base=380-460 bull=540-640 price=496.82 asof=2026-09-03 -->`

กติกา Valuation (ตาม `plan/price_vs_intrinsic_value_rule.md`):
- FV เป็น **ช่วง** ห้ามเขียนตัวเลขเดียวปลอมความแม่น
- ระบุที่มาทุกครั้ง: External analyst range / Base จาก method อะไร — ค่าที่ยังเป็น
  proxy ต้องกำกับคำว่า "proxy"
- **Revaluation Discipline:** ราคาขยับ = อัปเดตแค่ MoS/สถานะ; revalue FV เฉพาะเมื่อ
  สมมติฐานเปลี่ยนจริง (งบ, guidance, moat, หนี้) — อัปเดต tag ใหม่พร้อม asof วันที่ใหม่

---

## 5. `<TICKER>_news_<YYYY>.md` — ข่าว (append-only, กรองก่อนเก็บ)

**เก็บเฉพาะข่าว material** — Earnings, Guidance, Competition, Regulation, M&A,
Management, Debt/Capital Allocation, โครงสร้างอุตสาหกรรม
**ห้ามเก็บ:** clickbait, ข่าวรีไซเคิล, ความเห็นนักวิเคราะห์ที่ไม่มีข้อมูลใหม่, เรื่องราคาขยับรายวัน

Format ต่อ 1 entry (ใหม่สุดอยู่บนสุดของไฟล์):

```
## YYYY-MM-DD — <Headline สั้นกระชับ>

Source: <ชื่อแหล่ง>
URL: <ลิงก์>
Category: Earnings|Guidance|Product|Competition|Regulation|Management|M&A|Capital Allocation|Financing|Lawsuit|Macro|Industry|Other
Summary: <สรุป factual 2-4 ประโยค>
Impact: Positive|Negative|Neutral|Unclear
Time Horizon: Short|Medium|Long
Thesis Impact: Strengthens|No Material Change|Weakens|Potentially Breaks
Intrinsic Value Impact: Increase|No Material Change|Decrease|Unclear
Why It Matters: <อธิบาย 1-2 ประโยค>
```

กติกา: append ที่**ท้ายไฟล์** (เรียงเวลา) หรือด้านบนตามที่เคยทำในไฟล์นั้น —
**ขอให้ภายในไฟล์เดียวกันทำเหมือนเดิมทั้งไฟล์** · ห้ามลบ/แก้ entry เก่า · เปิดปีใหม่ = ไฟล์ใหม่

---

## 6. กติกาเนื้อหา (ใช้ร่วมทุกไฟล์)

1. **ภาษา:** เก็บงานวิจัยเป็น **อังกฤษ** (ประหยัด token, ค้นหาง่าย) — ภาษาไทยใช้กับคำอธิบาย
   ที่ส่งถึงผู้ใช้/Discord เท่านั้น (ตาม Language Rules ใน plan/stock.md)
2. **ติดป้ายแยกชนิดข้อมูล:** FACT / ASSUMPTION / ESTIMATE / OPINION — ห้ามเบลอ
   (เช่น "FY revenue +18% (FACT)" vs "Base FV $380-460 (ESTIMATE)")
3. **ห้ามเดาเลข:** ข้อมูลไม่มี = เขียน `Unknown` / `Insufficient data` — ไม่ใช่ประกอบให้ครบ
4. **วันที่ข้อมูล:** แยก publication date / event date / data period ชัดเจน
   (กันข่าวเก่าหน้าเป็นข่าวใหม่)
5. **Source hierarchy:** filings > IR > earnings release > transcript > regulator >
   สื่อการเงินชั้นดี > analyst research — เก็บลิงก์ทุกครั้งที่มี
6. **สิ่งที่ห้ามอยู่ใน folder นี้:** transaction (→ `ledger.md`), สเตตัส universe
   (→ `index.md`), รายงานรายวัน/รายสัปดาห์ (→ `watchlist/_daily/`, `weekly/`)

---

## 7. Checklist ตอนสร้างหุ้นใหม่ (bot ใช้ก่อนส่งงาน)

- [ ] เพิ่มแถวใน `index.md` (Ticker/Company/Market/Status/Priority/Opportunity=TBD/Last Review=วันนี้)
- [ ] ยืนยัน identity: ticker/exchange/ประเทศ/security type — ไม่ชัวร์ = หมายเหตุ
      "NEEDS VERIFICATION" ในคอลัมน์ Company
- [ ] สร้าง `<TICKER>_overall.md` ครบทุก section (§3)
- [ ] สร้าง `<TICKER>_current_status.md` ครบทุก section + **FV tag** (§4)
- [ ] สร้าง `<TICKER>_news_<ปีปัจจุบัน>.md` (ว่างไว้ได้ ถ้ายังไม่มีข่าว material)
- [ ] Tier: Owned = Full / Watch = Lite (§2)

## 8. Checklist ตอนอัปเดตประจำวัน (bot)

- [ ] มีข่าว material เท่านั้นถึงแตะไฟล์ (§5) — ไม่มี = ไม่แตะอะไรเลย
- [ ] ข่าวกระทบ thesis/valuation → อัปเดต `current_status.md` เฉพาะ section เกี่ยวข้อง
- [ ] ราคาเปลี่ยนอย่างเดียว → อัปเดต MoS ใน current_status + ย้าย `price=`/`asof=` ใน FV tag
      (ค่า bear/base/bull คงเดิม) — ไม่ revalue
- [ ] อัปเดตคอลัมน์ `Last Review` ใน index.md เฉพาะตัวที่แตะ
