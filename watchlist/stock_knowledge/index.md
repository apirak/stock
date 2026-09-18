# VI Research Watch List — Index

Last updated: 2026-09-16

> 📐 **ก่อนสร้าง/แก้ไฟล์หุ้น อ่าน [_GUIDELINE.md](_GUIDELINE.md) ก่อนทุกครั้ง** —
> เป็นสัญญา format ของ folder นี้ (โครงสร้างไฟล์, หัวข้อบังคับ, FV tag, กติกาข่าว)

This file is the **single source of truth** for the research universe.
Both bots (Daily / Weekly) read this table to decide what to track.
Status changes (buy/sell) are made by the user via ZCode sessions — never by the bots.

| Ticker | Company | Market | Status | Research Priority | Opportunity Status | Last Review |
|---|---|---|---|---|---|---|
| NVDA | NVIDIA Corp | NASDAQ (US) | Owned | High | TBD | 2026-09-17 |
| MSFT | Microsoft Corp | NASDAQ (US) | Owned | High | TBD | 2026-08-29 |
| GOOGL | Alphabet Inc (Class A) | NASDAQ (US) | Owned | High | TBD | 2026-08-29 |
| NFLX | Netflix Inc | NASDAQ (US) | Owned | Medium | TBD | 2026-08-29 |
| GDS | GDS Holdings (ADR) | NASDAQ (US/China) | Owned | Medium | TBD | 2026-08-29 |
| IREN | IREN Ltd | NASDAQ (US) | Owned | Medium | TBD | 2026-09-17 |
| TSLA | Tesla Inc | NASDAQ (US) | Owned | Medium | TBD | 2026-09-16 |
| AMD | Advanced Micro Devices | NASDAQ (US) | Owned | Medium | TBD | 2026-08-29 |
| AAPL | Apple Inc | NASDAQ (US) | Watch | Medium | TBD | 2026-09-16 |
| AMZN | Amazon.com Inc | NASDAQ (US) | Watch | Medium | TBD | 2026-08-29 |
| META | Meta Platforms | NASDAQ (US) | Watch | Medium | TBD | 2026-08-29 |
| SHOP | Shopify Inc | NYSE (Canada) | Watch | Low | TBD | 2026-09-16 |
| MU | Micron Technology | NASDAQ (US) | Watch | Medium | TBD | 2026-08-29 |
| INTC | Intel Corp | NASDAQ (US) | Watch | Medium | TBD | 2026-09-16 |
| BABA | Alibaba Group (ADR) | NYSE (China) | Watch | Medium | TBD | 2026-09-18 |
| BIDU | Baidu Inc (ADR) | NASDAQ (China) | Watch | Low | TBD | 2026-08-29 |
| BEKE | KE Holdings (ADR) | NYSE (China) | Watch | Low | TBD | 2026-08-29 |
| NTES | NetEase Inc (ADR) | NASDAQ (China) | Watch | Low | TBD | 2026-08-29 |
| SPCX | NEEDS VERIFICATION — likely Thai-listed instrument (DR or fund); exact identity unconfirmed | SET? (Thailand) | Watch | Low | TBD | 2026-08-29 |
| KKP | Kiatnakin Phatra Bank PCL (assumed — verify) | SET (Thailand) | Watch | Low | TBD | 2026-08-29 |
| XIAOMI80 | Xiaomi DR on SET (assumed — verify underlying ratio) | SET (Thailand) | Watch | Low | TBD | 2026-08-29 |

## Per-ticker files

One folder per ticker, placed under `own/` or `watchlist/` **by status** (bots move the
folder automatically when the user reports a buy/sell):

```
stock_knowledge/own/<TICKER>/TICKER_overall.md        # slow-changing business knowledge (EN)
stock_knowledge/own/<TICKER>/TICKER_current_status.md # current view + valuation (EN)
stock_knowledge/own/<TICKER>/TICKER_news_YYYY.md      # append-only material news, one file per year
stock_knowledge/watchlist/<TICKER>/...                # same three files for watched names
```

Currently researched (full 3-file set): NVDA, MSFT, GOOGL, NFLX — the other 17 tickers
are pending first-run research (see plan/stock_token_efficient_update_plan.md, lite
version for watch names).

## Machine-readable valuation tag

Every `TICKER_current_status.md` must carry this line under its Valuation section so
scripts can compute Margin of Safety without an LLM:

`<!-- FV: bear=<low>-<high> base=<low>-<high> bull=<low>-<high> price=<ref> asof=<YYYY-MM-DD> -->`

## Notes

- SPCX, KKP, XIAOMI80: Thai-listed / DR instruments — per user decision (2026-09-03)
  these are **manual research only** (Yahoo + web_search, best effort); they are excluded
  from the automated daily price fetch but stay in this universe.
- Opportunity Status TBD = pending first-run valuation.
- Transactions (buys/sells) are recorded in [ledger.md](ledger.md) — append-only.
- Methodology the bots follow: [knowledge/falling_angle.md](../../knowledge/falling_angle.md).
