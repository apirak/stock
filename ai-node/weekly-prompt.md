# Weekly Stock — evidence review and portfolio fit

- Schedule: Monday 09:00 Asia/Bangkok.
- Repository source of truth. Copy the fenced prompt into the existing ZCode automation after updating it.

```text
Run the weekly Falling Angle workflow in this workspace as Feb. Read charactor/feb/persona.md, knowledge/falling_angle.md and watchlist/stock_knowledge/_GUIDELINE.md. Analyze directly in this session; no paid LLM API.

1. BUILD THE RESEARCH QUEUE
Run cd src && .venv/bin/python main.py --mode weekly. If necessary, create .venv and install requirements.txt. Read src/data/pending/weekly-<printed week>.json. Its picks are up to two research candidates, not buy recommendations. Fail, Watch, missing/implausible financial data and unresolved warnings are excluded. An empty list is valid; do not add names to fill it.

2. REVIEW THE WEEK AND THE PORTFOLIO
Read daily briefs for this week, index.md, ledger.md and existing research for each candidate. Use payload.portfolio for recorded holdings and weights, checking ledger_last_date and missing_prices. Weights refer only to priced recorded stocks, not the entire portfolio; cash, unrecorded trades and exchange rates remain unverified. Identify missing transactions/quantities and currency mismatches. Group related exposures (AI/data centers, China, sector, country) as well as single-stock concentration. Do not infer current portfolio size from purchase costs.
Review material thesis changes and data failures among owned names even if they are not candidates. Price returns since an initial watch date are tracking data, not realized portfolio returns or proof the thesis was correct.

3. VERIFY EACH CANDIDATE
Open the latest company filing/IR earnings release and material guidance/competition/regulatory sources. Compare with the saved thesis and the strongest bearish explanation. Include URLs, publication dates and periods in Thai narratives.
- Business: identify the moat and verify why the headwind is temporary. High historical margin alone is insufficient. Annual histories are annual; compare current quarters with comparable quarters, and use consistent annual/TTM amounts for cash-flow ratios.
- Valuation: show analyst proxy separately from independent bear/base/bull values, method, assumptions and confidence. No independent value = “ยังประเมิน MoS ไม่ได้”. Resolve conflicts such as a proxy discount while price is near internal base value. Revalue only after material assumptions change.
- Portfolio: calculate existing/proposed position weights against confirmed total portfolio value including cash before expressing baht tranche sizes. Unknown total = no baht allocation. Sector diversification may still add country or common-factor concentration.
Separate facts, estimates and opinions. Explain evidence that would disprove the idea; do not assume that the market is overreacting.

4. WRITE A DECISION-READY NARRATIVE
Write src/data/analysis/weekly-<same week>.json:
{"week":"<week>","picks":[{"ticker":"...","why_moat_intact":"Thai: business verdict, sourced evidence and unknowns","market_overreaction":"Thai: bear argument; proxy gap vs independent MoS; method/date/confidence","tranche_strategy":"Thai: portfolio fit and verification tasks; conditional plan only when business, independent valuation and portfolio fit all pass","invalidation_criteria":["observable, evidence-based criteria"]}],"lesson":{"title":"Thai title","body":"Thai: short lesson tied to a verified case or this week's evidence"}}
If verification fails, state “ศึกษาเพิ่ม / ยังไม่เปิดไม้” and the exact unresolved issue. For a fully verified future plan, first tranche is 25–30% of target position; explain later tranches and the cap inclusive of existing holdings. Each numeric invalidation threshold needs a business rationale; reuse established criteria when unchanged.
With no candidates, write picks=[] and explain exclusions in the reply. Maintain research only for material verified changes, following _GUIDELINE.md. After earnings, compare revenue/guidance/FCF/debt with old assumptions and revise independent valuation only when warranted.

5. FINALIZE AND REPORT
Run cd src && .venv/bin/python main.py --mode finalize --weekly --week <same week>. Check exit status. Reply in Thai: thesis changes, research priorities, data gaps and portfolio concentration. State whether any idea passed all three checks or no purchase plan is ready. Weekly digest is a research queue; it never automatically allocates money from a proxy discount.
```
