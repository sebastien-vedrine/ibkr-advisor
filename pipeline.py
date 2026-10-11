"""Glue: fetch (IBKR + Yahoo) then analyse. Both steps run in a worker thread."""
from __future__ import annotations

import pandas as pd

from analytics import Settings, analyze
from ibkr_client import fetch_portfolio
from market_data import fetch_yahoo, norm
from sectors import SECTORS, momentum
from universe import UNIVERSE
from valuation import get_valuations, signal

BENCH = "SPY"


def load_data(cfg: dict, say) -> dict:
    positions, hist, account = fetch_portfolio(cfg["host"], cfg["port"], cfg["client_id"],
                                               cfg["years"], say)
    # fall back to Yahoo for stocks IBKR could not give history for (e.g. no data subscription)
    missing = [p.symbol for p in positions if p.sec_type == "STK" and p.symbol not in hist.columns]
    if missing:
        say("Fetching missing histories from Yahoo Finance…")
        y = fetch_yahoo([norm(m) for m in missing], cfg["years"])
        for m in missing:
            if norm(m) in y.columns:
                hist[m] = y[norm(m)]

    held_norm = {norm(p.symbol) for p in positions}
    extras = [norm(t) for t in cfg.get("extras", []) if t.strip()]
    universe = [t for t in list(UNIVERSE) + extras if t not in held_norm]
    say(f"Downloading market data for {len(universe)} candidates…")
    y = fetch_yahoo(universe + [BENCH], cfg["years"])
    bench = y[BENCH] if BENCH in y.columns else None
    cands = y.drop(columns=[BENCH], errors="ignore")
    say("Downloading sector data...")
    sp = fetch_yahoo(list(SECTORS) + [BENCH], 2)
    raw = dict(positions=positions, hist=hist, account=account, cands=cands, bench=bench,
               sector_prices=sp, valuation={}, fmp_key=cfg.get("fmp_key", ""), offline=False)
    stocks = [p.symbol for p in positions if p.sec_type == "STK"]
    get_valuations(stocks, raw["fmp_key"], raw["valuation"], say, norm)
    return raw


def compute(raw: dict, s: Settings, say=lambda m: None) -> dict:
    res = analyze(raw["positions"], raw["hist"], raw["cands"], raw["bench"], s,
                  meta=UNIVERSE, usd_fx=raw["account"]["fx"].get("USD", 1.0))
    res["account"] = raw["account"]

    # valuation for held positions + suggested new names
    val = raw["valuation"]
    new = [x["symbol"] for x in res["suggestions"] if x["action"] == "BUY (NEW)"]
    if not raw.get("offline"):
        get_valuations(new, raw.get("fmp_key", ""), val, say, norm)
    for x in res["suggestions"]:
        v = val.get(x["symbol"])
        prem, label = signal(v) if v else (None, "-")
        if prem is not None and x["action"] != "HOLD":
            x["why"] += f" P/E {v['pe']:.1f} vs {(v['avg10'] or v['avg5']):.1f} historical avg ({prem:+.0%})."
    rows = []
    for d in res["positions"]:
        rows.append(dict(symbol=d["symbol"], kind="held", weight=d["weight"], **_vrow(val.get(d["symbol"]))))
    for sym in new:
        rows.append(dict(symbol=sym, kind="new", weight=None, **_vrow(val.get(sym))))
    res["valuation"] = rows
    res["has_fmp"] = any(v.get("source") == "FMP" for v in val.values())
    res["sectors"] = momentum(raw["sector_prices"], BENCH) if raw.get("sector_prices") is not None else []
    return res


def _vrow(v):
    v = v or {}
    prem, label = signal(v) if v else (None, "-")
    return dict(pe=v.get("pe"), fwd=v.get("fwd"), avg5=v.get("avg5"), n5=v.get("n5", 0),
                avg10=v.get("avg10"), n10=v.get("n10", 0), avg15=v.get("avg15"), n15=v.get("n15", 0),
                prem=prem, signal=label, source=v.get("source", "-"))
