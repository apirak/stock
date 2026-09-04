#!/usr/bin/env python3
"""
prefetch_ticker.py — 0-token fundamentals data layer (Plan: งานที่ 1 ชั้น A)

Fetches FMP + Yahoo data for tickers and writes compact facts JSON to
_facts/TICKER_facts.json. Research subagents read this file directly
instead of burning tokens on their own API/tool loops.

Usage:
    python3 prefetch_ticker.py NVDA MSFT --tier owned
    python3 prefetch_ticker.py AAPL AMZN --tier watch
"""
import json, os, sys, time, datetime, urllib.request

ROOT = os.path.expanduser("~/obsedian/knowledge/stock")
FACTS_DIR = os.path.join(ROOT, "_facts")
FMP_BASE = "https://financialmodelingprep.com/stable"
UA = {"User-Agent": "Mozilla/5.0 (VI-research)"}
THAI_TICKERS = {"KKP", "XIAOMI80", "SPCX"}  # SET listings — no FMP coverage

OWNED_ENDPOINTS = [  # 9 FMP calls/ticker
    ("profile", "profile?symbol={s}"),
    ("quote", "quote?symbol={s}"),
    ("key_metrics", "key-metrics?symbol={s}&limit=4"),
    ("ratios", "ratios?symbol={s}&limit=4"),
    ("income_statement", "income-statement?symbol={s}&limit=4"),
    ("balance_sheet", "balance-sheet-statement?symbol={s}&limit=2"),
    ("cash_flow", "cash-flow-statement?symbol={s}&limit=4"),
    ("price_target_consensus", "price-target-consensus?symbol={s}"),
    ("dcf", "discounted-cash-flow?symbol={s}"),
]
WATCH_ENDPOINTS = [  # 5 FMP calls/ticker (lite)
    ("profile", "profile?symbol={s}"),
    ("quote", "quote?symbol={s}"),
    ("key_metrics", "key-metrics?symbol={s}&limit=2"),
    ("price_target_consensus", "price-target-consensus?symbol={s}"),
    ("dcf", "discounted-cash-flow?symbol={s}"),
]

STMT_KEEP = ["date", "fiscalYear", "revenue", "grossProfit", "operatingIncome",
    "netIncome", "eps", "epsDiluted", "ebitda", "totalAssets", "totalDebt",
    "totalStockholdersEquity", "cashAndCashEquivalents", "operatingCashFlow",
    "capitalExpenditure", "freeCashFlow", "dividendsPaid",
    "commonStockRepurchased", "weightedAverageShsOut", "weightedAverageShsOutDil"]


def load_key():
    k = os.environ.get("FMP_API_KEY")
    if k:
        return k.strip()
    env = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env):
        for line in open(env):
            if line.startswith("FMP_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("FMP_API_KEY not found in env or ~/.hermes/.env")


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def compact_stmt(rows):
    return [{k: row[k] for k in STMT_KEEP if k in row}
            for row in (rows if isinstance(rows, list) else [])]


def yahoo_meta(symbol):
    ys = symbol + ".BK" if symbol in THAI_TICKERS else symbol
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ys}?interval=1d&range=5d"
    try:
        d = get(url)
        res = d.get("chart", {}).get("result")
        if not res:
            return {"error": str(d.get("chart", {}).get("error"))[:200]}
        m = res[0]["meta"]
        ts = res[0].get("timestamp") or []
        closes = res[0]["indicators"]["quote"][0]["close"]
        last = [(t, c) for t, c in zip(ts, closes) if c]
        return {
            "symbol": m.get("symbol"),
            "name": m.get("shortName") or m.get("longName"),
            "exchange": m.get("fullExchangeName"),
            "currency": m.get("currency"),
            "instrument_type": m.get("instrumentType"),
            "price": m.get("regularMarketPrice"),
            "price_time_utc": (datetime.datetime.fromtimestamp(m["regularMarketTime"], datetime.UTC).strftime("%Y-%m-%d %H:%M")
                               if m.get("regularMarketTime") else None),
            "last_closes": [[datetime.datetime.fromtimestamp(t, datetime.UTC).strftime("%Y-%m-%d"), round(c, 4)]
                            for t, c in last[-5:]],
        }
    except Exception as e:
        return {"error": str(e)[:200]}


def fetch(ticker, tier, key):
    facts = {"ticker": ticker, "tier": tier,
             "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
             "yahoo": yahoo_meta(ticker), "fmp": {}}
    if ticker in THAI_TICKERS:
        facts["fmp_note"] = "Thai SET listing — no FMP coverage; use Yahoo + web_search"
    else:
        eps = OWNED_ENDPOINTS if tier == "owned" else WATCH_ENDPOINTS
        calls = 0
        for name, tmpl in eps:
            url = f"{FMP_BASE}/{tmpl.format(s=ticker)}&apikey={key}"
            data = None
            for attempt in range(4):
                try:
                    data = get(url)
                    calls += 1
                    break
                except Exception as e:
                    if "402" in str(e) and attempt < 3:
                        time.sleep(6 * (attempt + 1))  # transient burst limit
                        continue
                    data = {"error": str(e)[:200]}
                    break
            if isinstance(data, dict) and any(
                    x in str(data) for x in ("Restricted", "Premium", "Error Message")):
                facts["fmp"][name] = {"error": str(data)[:200]}
            elif name in ("income_statement", "balance_sheet", "cash_flow"):
                facts["fmp"][name] = compact_stmt(data)
            else:
                facts["fmp"][name] = data
        facts["fmp_calls_used"] = calls
    os.makedirs(FACTS_DIR, exist_ok=True)
    path = os.path.join(FACTS_DIR, f"{ticker}_facts.json")
    with open(path, "w") as f:
        json.dump(facts, f, indent=1, ensure_ascii=False)
    print(f"{ticker}: wrote {path} ({os.path.getsize(path)} bytes, "
          f"fmp_calls={facts.get('fmp_calls_used', 0)})")


if __name__ == "__main__":
    args = sys.argv[1:]
    tier = "watch"
    if "--tier" in args:
        i = args.index("--tier")
        tier = args[i + 1]
        args = args[:i] + args[i + 2:]
    if not args:
        sys.exit("usage: prefetch_ticker.py TICKER [TICKER...] [--tier owned|watch]")
    api_key = load_key()
    for t in args:
        fetch(t.upper(), tier, api_key)
        time.sleep(0.3)
