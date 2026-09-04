#!/usr/bin/env python3
"""
daily_scan.py — 0-token daily layer (Plan: งานที่ 2 ระดับ 0). Cron: every day 19:00 +07.

1. Yahoo spark: ONE batch call -> closes for every ticker (US + .BK Thai)
2. Reads Bear/Base/Bull FV from TICKER_current_status.md -> recomputes MoS
   (machine-readable `<!-- FV: ... -->` block preferred; regex fallback)
3. Google News RSS per ticker -> keyword-filtered material headlines
   (if RSS fails: skip news layer entirely, no paid fallback — per user decision)
4. Writes _daily/YYYY-MM-DD_scan.md + _daily/trigger.txt + _daily/prev_mos.json

Cron `monitor` should watch trigger.txt to wake the analysis agent (ระดับ 1).
Exit 0 always.
"""
import json, os, re, sys, datetime, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.expanduser("~/obsedian/knowledge/stock")
DAILY = os.path.join(ROOT, "_daily")
UA = {"User-Agent": "Mozilla/5.0 (VI-research)"}
THAI = {"KKP", "XIAOMI80", "SPCX"}

# STRONG keywords wake the agent (ระดับ 1); weak ones are recorded in the scan only.
STRONG_KW = ["earnings", "guidance", "downgrade", "upgrade", "lawsuit", "sec ",
    "merger", "acquisition", "layoff", "investigation", "antitrust", "recall",
    "stock split", "offering", "guidance cut", "profit warning"]
WEAK_KW = ["revenue", "profit", "dividend", "buyback", "ceo", "cfo", "ban",
    "export", "misses", "beats", "forecast"]
PRICE_TRIGGER = 5.0   # abs daily % move
MOS_ENTER = 0.20      # crossing INTO >=20% MoS is interesting
MOS_EXIT = 0.0        # losing all MoS


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def tickers():
    out = []
    for line in open(os.path.join(ROOT, "watch_list.md")):
        m = re.match(r"\|\s*([A-Z0-9]+)\s*\|", line)
        if m and m.group(1) != "Ticker":
            out.append(m.group(1))
    return out


def prices(ticks):
    """One batch spark call; if any bad symbol poisons the batch (HTTP 400),
    fall back to per-symbol calls (still 0-token, just more HTTP)."""
    def parse(key, node):
        closes = [c for c in node["close"] if c]
        prev, last = closes[-2], closes[-1]
        return {"price": round(last, 4), "prev": round(prev, 4),
                "pct": round((last - prev) / prev * 100, 2)}
    ymap = {t: (t + ".BK" if t in THAI else t) for t in ticks}
    url = ("https://query1.finance.yahoo.com/v8/finance/spark?symbols="
           + ",".join(ymap.values()) + "&range=5d&interval=1d")
    out = {}
    try:
        data = json.loads(get(url))
        for t, ys in ymap.items():
            try:
                out[t] = parse(ys, data[ys])
            except Exception as e:
                out[t] = {"error": str(e)[:80]}
        return out
    except Exception:
        pass  # batch poisoned -> per-symbol fallback
    for t, ys in ymap.items():
        u = f"https://query1.finance.yahoo.com/v8/finance/spark?symbols={ys}&range=5d&interval=1d"
        try:
            data = json.loads(get(u))
            out[t] = parse(ys, data[ys])
        except Exception as e:
            out[t] = {"error": str(e)[:80]}
    return out


def fv(ticker):
    """Return {'bear':(lo,hi),'base':(lo,hi),'bull':(lo,hi)} or None."""
    p = os.path.join(ROOT, ticker, f"{ticker}_current_status.md")
    if not os.path.exists(p):
        return None
    txt = open(p).read()
    m = re.search(r"<!--\s*FV:\s*bear=([\d.]+)-([\d.]+)\s+base=([\d.]+)-([\d.]+)\s+bull=([\d.]+)-([\d.]+)", txt)
    if m:
        g = [float(x) for x in m.groups()]
        return {"bear": (g[0], g[1]), "base": (g[2], g[3]), "bull": (g[4], g[5])}
    out = {}
    for name in ("Bear", "Base", "Bull"):
        m = re.search(name + r"[^\d]{0,40}\$?([\d,]+(?:\.\d+)?)\s*[–—-]\s*\$?([\d,]+(?:\.\d+)?)", txt)
        if m:
            out[name.lower()] = (float(m[1].replace(",", "")), float(m[2].replace(",", "")))
    return out if len(out) == 3 else None


def news(ticker):
    """Return list of {'title','date','link','strong'} or None if RSS unavailable."""
    q = ticker + "+stock"
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    try:
        root = ET.fromstring(get(url, 15))
    except Exception:
        return None
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    items, seen = [], set()
    for it in root.iter("item"):
        title = it.findtext("title") or ""
        pub = it.findtext("pubDate") or ""
        link = it.findtext("link") or ""
        try:
            dt = datetime.datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z")
        except Exception:
            continue
        if (now - dt).total_seconds() > 36 * 3600:
            continue
        low = title.lower()
        if not any(k in low for k in STRONG_KW + WEAK_KW):
            continue
        sig = re.sub(r"[^a-z0-9 ]", "", low)[:50]  # dedupe syndicated repeats
        if sig in seen:
            continue
        seen.add(sig)
        items.append({"title": title[:160], "date": dt.strftime("%Y-%m-%d %H:%M"),
                      "link": link, "strong": any(k in low for k in STRONG_KW)})
        if len(items) >= 3:
            break
    return items


def main():
    os.makedirs(DAILY, exist_ok=True)
    today = datetime.date.today().isoformat()
    ticks = tickers()
    px = prices(ticks)

    prev_mos = {}
    pmfile = os.path.join(DAILY, "prev_mos.json")
    if os.path.exists(pmfile):
        prev_mos = json.load(open(pmfile))
    new_mos = {}
    triggers, notes = [], []

    lines = [f"# Daily scan — {today} (0-token layer)", "",
             "| Ticker | Price | Δ% | Base FV | MoS% |", "|---|---:|---:|---|---:|"]
    for t in ticks:
        p = px.get(t, {})
        f = fv(t)
        mos = None
        base_txt = "—"
        if "price" in p and f:
            mid = (f["base"][0] + f["base"][1]) / 2
            mos = (mid - p["price"]) / mid
            base_txt = f'{f["base"][0]:g}–{f["base"][1]:g}'
            new_mos[t] = round(mos, 4)
        lines.append(f'| {t} | {p.get("price", "ERR")} | {p.get("pct", "")} | {base_txt} '
                     f'| {round(mos * 100, 1) if mos is not None else "n/a"} |')
        if "pct" in p and abs(p["pct"]) >= PRICE_TRIGGER:
            triggers.append(f"{t}: price {p['pct']}% today")
        if mos is not None:
            pm = prev_mos.get(t)
            if (pm is None or pm < MOS_ENTER) and mos >= MOS_ENTER:
                triggers.append(f"{t}: MoS entered >=20% zone ({mos * 100:.1f}%)")
            if pm is not None and pm > MOS_EXIT and mos <= MOS_EXIT:
                triggers.append(f"{t}: MoS lost (now {mos * 100:.1f}%)")
        if f is None:
            notes.append(f"{t}: no FV data yet (research pending)")
    lines.append("")

    lines.append("## Material news (last ~36h, keyword-filtered)")
    news_down = 0
    any_news = False
    for t in ticks:
        ns = news(t)
        if ns is None:
            news_down += 1
            continue
        if ns:
            any_news = True
            lines.append(f"\n### {t}")
            for n in ns:
                tag = " **[strong]**" if n["strong"] else ""
                lines.append(f"- [{n['date']}]{tag} {n['title']}\n  {n['link']}")
            if any(n["strong"] for n in ns):
                triggers.append(f"{t}: strong material headline(s)")
    if news_down == len(ticks):
        lines.append("\n(news layer unavailable today — price triggers only)")
    elif not any_news:
        lines.append("\n(none)")

    lines.append("\n## Triggers")
    lines += [f"- {x}" for x in triggers] or ["- none"]
    if notes:
        lines.append("\n## Notes")
        lines += [f"- {x}" for x in notes]

    scan = os.path.join(DAILY, f"{today}_scan.md")
    open(scan, "w").write("\n".join(lines) + "\n")
    open(os.path.join(DAILY, "trigger.txt"), "w").write("\n".join(triggers) if triggers else "none")
    json.dump(new_mos, open(pmfile, "w"))
    print(f"wrote {scan}; tickers={len(ticks)}; triggers={len(triggers)}")


if __name__ == "__main__":
    main()
