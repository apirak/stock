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

<!-- No transactions recorded yet.
     Known owned positions per index.md (NVDA, MSFT, GOOGL, NFLX, GDS, IREN, TSLA, AMD)
     need user transaction data: shares / avg cost / dates.
     Do NOT infer them. -->
