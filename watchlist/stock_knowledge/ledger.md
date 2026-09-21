# Portfolio Ledger — append-only transaction history

Rules (from plan/stock.md):

- **Append-only.** Never silently edit or delete a historical transaction.
  A mistake is corrected by appending a reversing entry with an explanation.
- Only the **user** reports transactions (via ZCode chat). Bots never invent one.
- Missing information is recorded as `unknown`, never inferred.
- `stock_knowledge/index.md` Status column and folder placement (`own/` vs
  `watchlist/`) must be updated together with every BUY/SELL.
- Portfolio snapshot (assets) is **derived** from this ledger — it is never
  maintained separately.

Supported transaction types:
`BUY` `SELL` `DIVIDEND` `SPLIT` `TRANSFER` `CASH_IN` `CASH_OUT`

Entry format:

```
## YYYY-MM-DD — BUY <TICKER>
Shares: <n | unknown>
Price: <price> <currency>
Fees: <fees | unknown>
Reason: <why, in the user's words>
Notes: <context, thesis at time of purchase>
```

---

<!-- Provenance (batch 2026-09-19): the 24 entries below were transcribed from
     Dime! activity-feed screenshots provided by the user (5 images).
     Coverage 2026-07-08 → 2026-09-14; the feed may continue before
     2026-07-08 (not visible in the screenshots) — earlier history unknown.
     "Price" = executed price in USD. Notes carry the THB/USD total the app
     debited/credited. User stated no reasons → Reason recorded as unknown.
     Entries are chronological (oldest first); new entries append at the end. -->

## 2026-07-08 — BUY NVDA
Shares: 0.4529226
Price: 197.186 USD
Fees: none shown in app
Reason: unknown
Notes: Total 2,999.92 THB (Dime!).

## 2026-07-08 — BUY TSLA
Shares: 0.0754327
Price: 394.6560 USD
Fees: none shown in app
Reason: unknown
Notes: Total 999.97 THB (Dime!).

## 2026-07-08 — BUY GOOG
Shares: 0.0830348
Price: 358.5240 USD
Fees: none shown in app
Reason: unknown
Notes: Total 999.97 THB (Dime!). GOOG = Alphabet Class C (distinct from GOOGL Class A).

## 2026-07-12 — BUY MSFT
Shares: 0.1543556
Price: 388.00 USD
Fees: none shown in app
Reason: unknown
Notes: Total 1,999.73 THB (Dime!).

## 2026-07-12 — BUY TSLA
Shares: 0.1480446
Price: 404.54 USD
Fees: none shown in app
Reason: unknown
Notes: Total 1,999.73 THB (Dime!).

## 2026-07-17 — BUY GOOG
Shares: 0.4287573
Price: 345.79 USD
Fees: none shown in app
Reason: unknown
Notes: Total 5,000.00 THB (Dime!).

## 2026-07-20 — BUY TSLA
Shares: 0.3832107
Price: 386.08 USD
Fees: none shown in app
Reason: unknown
Notes: Total 4,999.93 THB (Dime!).

## 2026-07-20 — BUY GOOG
Shares: 0.0844467
Price: 350.28 USD
Fees: none shown in app
Reason: unknown
Notes: Total 999.72 THB (Dime!).

## 2026-07-25 — BUY AMD
Shares: 2.8055734
Price: 526.42 USD
Fees: none shown in app
Reason: unknown
Notes: Total 49,999.66 THB (Dime!).

## 2026-07-25 — BUY GOOGL
Shares: 2.7199201
Price: 325.80 USD
Fees: none shown in app
Reason: unknown
Notes: Total 29,999.87 THB (Dime!). GOOGL = Alphabet Class A.

## 2026-07-25 — BUY MSFT
Shares: 1.5128297
Price: 390.50 USD
Fees: none shown in app
Reason: unknown
Notes: Total 19,999.80 THB (Dime!).

## 2026-08-03 — BUY IREN
Shares: 40.9668674
Price: 36.52 USD
Fees: none shown in app
Reason: unknown
Notes: Total 50,000.00 THB (Dime!).

## 2026-08-03 — BUY NVDA
Shares: 7.5627056
Price: 197.51 USD
Fees: none shown in app
Reason: unknown
Notes: Total 50,000.00 THB (Dime!).

## 2026-08-07 — BUY GDS
Shares: 36.2971911
Price: 33.11 USD
Fees: none shown in app
Reason: unknown
Notes: Total 39,999.95 THB (Dime!).

## 2026-08-11 — SELL GOOG
Shares: 0.5962389
Price: 354.24 USD
Fees: 0.02 USD (SEC Fee 0.01 + TAF Fee 0.01, deducted from Dime! USD on 2026-08-12)
Reason: unknown
Notes: Proceeds ~211.23 USD to Dime! USD. Disposes of the full GOOG (Class C) position — equals the sum of the three prior GOOG lots (0.5962388 sh, rounding at 7th decimal). A 210.00 USD AMD buy followed on 2026-08-12.

## 2026-08-12 — BUY AMD
Shares: 0.4297368
Price: 487.88 USD
Fees: none shown in app
Reason: unknown
Notes: Total 210.00 USD paid from Dime! USD balance (not THB).

## 2026-08-12 — BUY NFLX
Shares: 1.6305967
Price: 73.8380 USD
Fees: none shown in app
Reason: unknown
Notes: Total 3,999.97 THB (Dime!).

## 2026-08-30 — BUY NFLX
Shares: 0.7422106
Price: 80.88 USD
Fees: none shown in app
Reason: unknown
Notes: Total 1,999.92 THB (Dime!). Order carries the app's schedule (DCA) icon.

## 2026-08-30 — BUY IREN
Shares: 33.6427570
Price: 35.69 USD
Fees: none shown in app
Reason: unknown
Notes: Total 39,999.81 THB (Dime!).

## 2026-08-30 — BUY BABA
Shares: 10.2915059
Price: 116.67 USD
Fees: none shown in app
Reason: unknown
Notes: Total 39,999.81 THB (Dime!).

## 2026-08-30 — BUY VT
Shares: 0.1864785
Price: 160.93 USD
Fees: none shown in app
Reason: unknown
Notes: Total 999.80 THB (Dime!). VT = Vanguard Total World Stock ETF.

## 2026-09-10 — BUY AAPL
Shares: 0.9572290
Price: 316.57 USD
Fees: none shown in app
Reason: unknown
Notes: Total 9,999.99 THB (Dime!).

## 2026-09-10 — DIVIDEND MSFT
Shares: 1.6671853 (held on record date 2026-08-20)
Price: 0.91 USD/share gross
Fees: 0.22 USD US dividend withholding tax
Reason: n/a
Notes: Gross 1.52 USD, net 1.30 USD deposited to Dime! USD.

## 2026-09-14 — DIVIDEND GOOGL
Shares: 2.7199201 (held on record date 2026-09-04)
Price: 0.22 USD/share gross
Fees: 0.09 USD US dividend withholding tax
Reason: n/a
Notes: Gross 0.60 USD, net 0.51 USD deposited to Dime! USD.

<!-- Derived positions as of 2026-09-19 (from the entries above; assumes no
     pre-2026-07-08 history):
     NVDA 8.0156282 · MSFT 1.6671853 · GOOGL 2.7199201 · AMD 3.2353102
     IREN 74.6096244 · GDS 36.2971911 · NFLX 2.3728073 · TSLA 0.6066880
     BABA 10.2915059 · AAPL 0.9572290 · VT 0.1864785
     GOOG 0 (position closed 2026-08-11) -->
