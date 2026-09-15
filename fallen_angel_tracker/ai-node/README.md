# 📝 AI Analysis — Decision Note & Automation Prompts

โฟลเดอร์นี้คือ **แหล่งอ้างอิงของ "สมอง" ของระบบ** — ทั้งบันทึกการตัดสินใจและ prompt ที่ใช้กับ ZCode Automations

---

## 1. Decision Note: ทำไมโค้ดนี้ไม่มีส่วนเรียก LLM API

**วันที่ตัดสินใจ:** 2026-09-15

**การตัดสินใจ:** ใช้ **ZCode harness เป็นนักวิเคราะห์** เพียงช่องทางเดียว และ **ลบโค้ดที่เรียก LLM API (Anthropic/OpenAI/Gemini) ออกจากโปรเจกต์ทั้งหมด** เพื่อให้คนมาแก้โค้ดในอนาคตไม่สับสนว่าระบบวิเคราะห์ด้วยอะไร

**สิ่งที่ถูกลบไป (เคยมีในเวอร์ชันก่อนหน้า):**

| ที่เดิม | ของที่ลบ |
|---|---|
| `analyzer.py` | `SYSTEM_PROMPT`, `call_llm_json()`, `_call_anthropic/_call_openai/_call_gemini`, `_extract_json/_post`, `generate_pick_narrative()`, พารามิเตอร์ `use_llm` ของ `analyze_ticker()` |
| `config.py` | `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT`, `LLM_MAX_TOKENS`, `llm_ready()` |
| `main.py` | flag `--use-api-llm` และ branch ที่วิเคราะห์ผ่าน API inline |
| `.env.example` | หัวข้อตั้งค่า LLM keys |

เนื่องจากโปรเจกต์นี้ยังไม่เคยถูก commit (มีแค่ initial commit ของ vault), โค้ดเวอร์ชันเก่าไม่อยู่ใน git history — ถ้าอนาคตต้องการเอาคืน ให้เขียนใหม่ตามแนวทางด้านล่าง

**สิ่งที่ยังอยู่และต้องเข้าใจให้ต่างกัน:**

| ชั้น | คืออะไร | อยู่ที่ไหน |
|---|---|---|
| **Rule-based screen** | ตัวเลขล้วน คำนวณ deterministic จากงบการเงิน (leverage/coverage/ROIC-vs-WACC/FCF/discount) ให้ verdict ตั้งต้น — **ไม่ใช่ LLM** และยังทำงานแม้ไม่มีใครวิเคราะห์ | `analyzer.py` (heuristic_verdict ฯลฯ) |
| **ZCode harness** | นักวิเคราะห์ตัวจริง: อ่าน `data/pending/*.json` → ตัดสิน Transitory vs Structural + เขียน narrative → ส่งมอบเป็น `data/analysis/*.json` | ZCode Automations (prompt ในโฟลเดอร์นี้) |
| **Finalize** | Python merge ผลวิเคราะห์ลง CSV + regenerate รายงาน + ส่ง Discord/email | `main.py --mode finalize` |

**ถ้าอนาคตอยากกลับไปใช้ LLM API แทน harness:** เขียน provider layer ใน `analyzer.py` (pattern เดิมคือ POST ตรงไป `api.anthropic.com` / `api.openai.com` / `generativelanguage.googleapis.com` ด้วย `requests` + ดึง JSON จากคำตอบ) แล้วให้ `analyze_ticker()` ใช้ผลลัพธ์ override ค่า placeholder — แต่ต้องคงหลักไว้ว่า **ตัวเลขยังมาจาก `data_fetcher.py` เสมอ LLM ไม่มีสิทธิ์สร้างตัวเลข**

---

## 2. File Contract ระหว่าง Python ↔ ZCode (สรุป)

- Python (STEP 1) เขียน `data/pending/daily-<date>.json` / `weekly-<YYYY-Www>.json`
- ZCode (STEP 2–3) วิเคราะห์แล้วเขียน `data/analysis/daily-<date>.json` / `weekly-<YYYY-Www>.json` ตาม schema ที่ระบุใน prompt
- Python (STEP 4) `--mode finalize` merge → CSV + reports + Discord

แก้ schema ต้องแก้พร้อมกัน 2 ที่: โค้ด (`main.py` ตอน merge) และ prompt ในโฟลเดอร์นี้

---

## 3. Prompt ของ Automations

| ไฟล์ | Automation | Cron |
|---|---|---|
| [daily-prompt.md](daily-prompt.md) | Fallen Angel daily tracker | `0 7 * * 2-6` (อังคาร–เสาร์ 07:00) — **มีอยู่แล้วในระบบ** |
| [weekly-prompt.md](weekly-prompt.md) | Fallen Angel weekly digest | `0 7 * * 1` (วันจันทร์ 07:00) — **ยังต้องสร้างในแชทใหม่** |

> ข้อจำกัดของ ZCode: สร้าง automation ได้ 1 ตัวต่อ session — การเพิ่ม/แก้ automation ให้เปิดแชทใหม่แล้ว copy prompt จากไฟล์ในโฟลเดอร์นี้
>
> ⚠️ ถ้าแก้ prompt ในไฟล์นี้ **ต้องอัปเดต automation ใน ZCode ด้วย** (และกลับกัน) — ไฟล์เหล่านี้คือ reference ที่ต้องตรงกับของจริงเสมอ
