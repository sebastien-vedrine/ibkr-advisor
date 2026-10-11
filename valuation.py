"""P/E: current (Yahoo) and 5/10/15-year averages.

- With a Financial Modeling Prep key: annual P/E ratios from FMP (/stable/ratios), up to 15 years
  (the depth available depends on your FMP plan; the app shows how many years each average uses).
- Without a key: P/E per fiscal year rebuilt from Yahoo annual EPS and the year-end price
  (usually only the last ~4 years are available).
Loss-making years (P/E <= 0) and absurd values (> 500) are excluded from averages.
"""
from __future__ import annotations

import math

import pandas as pd
import requests
import yfinance as yf

FMP = "https://financialmodelingprep.com/stable"


def _clean(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and 0 < x < 500 else None


def _fmp_history(sym: str, key: str) -> list[tuple[str, float | None]]:
    r = requests.get(f"{FMP}/ratios", params=dict(symbol=sym, period="annual", limit=15, apikey=key),
                     timeout=20)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(str(data)[:120])
    data.sort(key=lambda d: d.get("date", ""), reverse=True)  # newest first
    return [(str(d.get("fiscalYear") or d.get("date", "")[:4]), _clean(d.get("priceToEarningsRatio")))
            for d in data]


def _yahoo_history(t: yf.Ticker) -> list[tuple[str, float | None]]:
    inc = t.income_stmt
    if inc is None or inc.empty:
        return []
    row = next((r for r in ("Diluted EPS", "Basic EPS") if r in inc.index), None)
    if row is None:
        return []
    px = t.history(period="max", auto_adjust=False)["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None)
    out = []
    for col in sorted(inc.columns, reverse=True):
        eps = inc.loc[row, col]
        past = px[:pd.Timestamp(col)]
        out.append((str(pd.Timestamp(col).year),
                    _clean(past.iloc[-1] / eps) if len(past) and eps and eps > 0 else None))
    return out


def _avg(hist: list, n: int):
    v = [x for _, x in hist[:n] if x is not None]
    return (sum(v) / len(v), len(v)) if v else (None, 0)


def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _profile(info: dict) -> dict:
    """Extra valuation / quality figures shown in the stock detail view."""
    g = lambda *keys: next((_num(info.get(k)) for k in keys if _num(info.get(k)) is not None), None)  # noqa: E731
    return dict(name=info.get("longName") or info.get("shortName") or "", sector=info.get("sector") or "",
                industry=info.get("industry") or "", kind=info.get("quoteType") or "",
                currency=info.get("currency") or "", price=g("currentPrice", "regularMarketPrice", "navPrice"),
                mcap=g("marketCap", "totalAssets"), peg=g("trailingPegRatio", "pegRatio"),
                pb=g("priceToBook"), ps=g("priceToSalesTrailing12Months"), ev_ebitda=g("enterpriseToEbitda"),
                div=g("trailingAnnualDividendYield", "yield"), margin=g("profitMargins"),
                roe=g("returnOnEquity"), growth=g("earningsGrowth"), lo52=g("fiftyTwoWeekLow"),
                hi52=g("fiftyTwoWeekHigh"), target=g("targetMeanPrice"),
                n_analysts=g("numberOfAnalystOpinions"), rec=info.get("recommendationKey") or "")


def get_valuations(symbols: list[str], key: str, cache: dict, say=lambda m: None, norm=lambda s: s):
    """Fills cache[symbol] = dict(pe, fwd, avg5, n5, avg10, n10, avg15, n15, source,
    hist [(year, P/E)] newest first, info {...extra figures})."""
    todo = [s for s in symbols if s not in cache]
    for i, sym in enumerate(todo, 1):
        say(f"Valuation (P/E) {i}/{len(todo)}: {sym}")
        out = dict(pe=None, fwd=None, source="-", hist=[], info={})
        for k in ("avg5", "avg10", "avg15"):
            out[k], out["n" + k[3:]] = None, 0
        try:
            t = yf.Ticker(norm(sym))
            info = t.info or {}
            out["pe"] = _clean(info.get("trailingPE"))
            out["fwd"] = _clean(info.get("forwardPE"))
            out["info"] = _profile(info)
            if info.get("quoteType", "EQUITY") == "EQUITY":
                hist, src = [], "-"
                if key:
                    try:
                        hist, src = _fmp_history(norm(sym), key), "FMP"
                    except Exception:
                        hist = []
                if not hist:
                    hist, src = _yahoo_history(t), "Yahoo"
                for n in (5, 10, 15):
                    out[f"avg{n}"], out[f"n{n}"] = _avg(hist, n)
                out["source"], out["hist"] = src, hist
        except Exception:
            pass
        cache[sym] = out
    return cache


def signal(v: dict):
    """(premium of current P/E vs its 10y average (or 5y), label)."""
    ref = v.get("avg10") or v.get("avg5")
    if not v.get("pe") or not ref:
        return None, "-"
    prem = v["pe"] / ref - 1
    return prem, "Cheap" if prem < -0.15 else "Expensive" if prem > 0.15 else "Fair"
