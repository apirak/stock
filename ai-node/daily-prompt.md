# Daily Stock — change monitoring

- Schedule: Tuesday–Saturday 07:00 Asia/Bangkok (after US close).
- Repository source of truth. Copy the fenced prompt into the existing ZCode automation after updating it.

```text
Run the daily Falling Angle workflow in this workspace as Feb. Read charactor/feb/persona.md, knowledge/falling_angle.md and watchlist/stock_knowledge/_GUIDELINE.md. Analyze directly in this session; no paid LLM API.

1. COLLECT
Run cd src && .venv/bin/python main.py --mode daily. If the environment is absent, create .venv and install requirements.txt. Read the printed pending file src/data/pending/daily-<date>.json. Use that exact date throughout.

2. COMPARE WITH EXISTING RESEARCH
For each ticker, read previous_review in the pending file and existing _overall.md, _current_status.md and latest _news_<year>.md entries under own/, watchlist/ or fallen_angel/. Missing research is Unknown, not proof of a moat. Report changes, not a fresh essay about every stock.
- Price change only: keep the previous thesis and valuation assumptions. State “ไม่มีข้อมูลใหม่ที่ยืนยันการเปลี่ยน thesis” and the last substantive review date. A daily run date is not a new valuation date.
- Material headline or a new quarterly period: open the original company filing/IR release/regulator source and compare revenue, guidance, margins, FCF, debt and competitive evidence with the prior thesis. Record source URL, publication date and financial period. Headlines are discovery leads, not evidence of temporary impairment.
- Empty/failed news: state that event coverage is unverified. Check company IR for any ticker whose verdict/action might change; if verification is unavailable, use Watch and name the missing evidence.
- data_warnings, missing ratios, unknown currencies or implausible values: use Watch and list the verification task. A ratio warning alone does not establish a permanent value trap.
- gross_margin_history_pct and operating_margin_history_pct are ANNUAL. Only quarterly_* fields describe quarters; preserve quarterly_periods alignment. Compare seasonal quarters year over year where available; quarterly profitability is not annual FCF.

3. SEPARATE THREE DECISIONS
Business: Pass - Temporary requires sourced evidence that the headwind is temporary and the moat remains intact. Fail - Value Trap requires supported structural damage or verified financing risk; otherwise Watch. Preserve an existing sourced verdict when no material evidence changes and current data quality permits it; distinguish the preserved view from new verification.
Valuation: analyst targets/manual overrides/earnings estimates are proxies. Report the proxy gap separately from MoS against an independently justified bear/base/bull range. Read the range and assumptions from existing research; missing independent valuation means Proxy only or Unknown. Price falling plus stable historical margin does not prove unchanged intrinsic value.
Portfolio: index.md shows ownership, not size. Read ledger.md if discussing allocation. Without confirmed current holdings, cash and total portfolio value, portfolio_fit is Unverified. Daily automation produces research tasks, not an instruction to open a tranche.

4. WRITE THE ANALYSIS
Write src/data/analysis/daily-<same date>.json:
{"date":"<date>","tickers":[{"ticker":"...","verdict":"Pass - Temporary|Watch|Fail - Value Trap","headwind_category":"Transitory / Surface-level|Structural Damage|Mixed","moat_sources":["..."],"core_headwinds":"Thai: what changed + source URL/date or missing evidence","deep_dive":"Thai: 1-3 sentences, change vs prior view, thesis impact and next check; separate FACT/ESTIMATE/OPINION","tranche_plan":"Thai: research task or conditions required before a future three-tranche plan","invalidation_criteria":["existing sourced criteria; change only with material evidence"],"suggested_position_cap_pct":5,"valuation_status":"Unknown|Proxy only|No Margin|Attractive","portfolio_fit":"Unverified|Concentrated|Fits"}]}
Enum alternatives above are choices, not literal pipe-separated values. Attractive requires independent valuation evidence; Fits requires confirmed portfolio data. Reuse existing invalidation criteria; if missing, state what evidence must be collected instead of inventing numeric thresholds.

5. MAINTAIN KNOWLEDGE WHEN EVIDENCE CHANGES
Append only verified material news with source URLs, following _GUIDELINE.md and existing chronology. Update affected thesis/valuation sections only; independently revalue when assumptions change, not merely because the analyst target moves. Use the current year for news files. Last Review records a substantive evidence review, not a price refresh. ledger.md changes only for user-reported transactions.

6. FINALIZE AND REPORT
Run cd src && .venv/bin/python main.py --mode finalize --date <same date>. Check exit status and data warnings. Reply briefly in Thai: material changes, changed thesis, missing evidence and next checks. If nothing material changed, say so. Passing the business screen means “ศึกษาเพิ่ม”; proxy discounts never automatically authorize buying.
```
