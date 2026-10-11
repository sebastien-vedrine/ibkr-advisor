"""Momentum of the 11 S&P 500 sectors (SPDR sector ETFs)."""
from __future__ import annotations

import numpy as np
import pandas as pd

SECTORS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care", "XLE": "Energy",
    "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", "XLI": "Industrials",
    "XLU": "Utilities", "XLB": "Materials", "XLRE": "Real Estate", "XLC": "Communication Services",
}


def momentum(prices: pd.DataFrame, bench: str = "SPY") -> list[dict]:
    """Ranked list. score = average of 3M, 6M and 12-1M returns (skips the last month)."""
    p = prices.sort_index().ffill()
    has_b = bench in p.columns and p[bench].dropna().size > 260
    rows = []
    for etf, name in SECTORS.items():
        if etf not in p.columns:
            continue
        s = p[etf].dropna()
        if len(s) < 260:
            continue
        last = s.iloc[-1]
        ret = {n: last / s.iloc[-1 - d] - 1 for n, d in (("m1", 21), ("m3", 63), ("m6", 126), ("m12", 252))}
        m12_1 = s.iloc[-22] / s.iloc[-253] - 1
        rs3 = np.nan
        if has_b:
            b = p[bench].dropna()
            rs3 = (1 + ret["m3"]) / (b.iloc[-1] / b.iloc[-64]) - 1
        rows.append(dict(etf=etf, name=name, **ret, m12_1=m12_1, rs3=rs3,
                         above200=bool(last > s.iloc[-200:].mean()),
                         score=float(np.mean([ret["m3"], ret["m6"], m12_1]))))
    rows.sort(key=lambda d: d["score"], reverse=True)
    for i, d in enumerate(rows, 1):
        d["rank"] = i
    return rows
