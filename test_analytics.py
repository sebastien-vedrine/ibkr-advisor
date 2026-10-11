"""Offline sanity test with synthetic data: python test_analytics.py"""
import numpy as np, pandas as pd
from analytics import Position, Settings, analyze

DRIFT = float(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else 1.0
rng = np.random.default_rng(7)
idx = pd.bdate_range("2025-10-01", periods=252)
DRIFT = float(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else 1.0
def series(mu, vol, common, beta):
    r = DRIFT*mu/252 + beta*common + rng.normal(0, vol/np.sqrt(252), len(idx))
    return 100*np.cumprod(1+r)
mkt = rng.normal(0.0004*DRIFT, 0.01, len(idx))
held = {"AAA": series(.12,.30,mkt,1.2), "BBB": series(.10,.25,mkt,1.0), "CCC": series(.02,.35,mkt,1.1)}
cands = {"GLD": series(.08,.14,mkt,0.0), "AGG": series(.04,.05,mkt,-0.05), "VTI": series(.10,.15,mkt,1.0),
         "XLU": series(.06,.14,mkt,.3)}
prices = pd.DataFrame(held, index=idx); cp = pd.DataFrame(cands, index=idx)
bench = pd.Series(100*np.cumprod(1+mkt), index=idx)
pos = [Position(k, "STK", "USD", 100, v[-1], 90, 1.0, v[-1]*100*w, 0) for (k, v), w in zip(held.items(), (1, 1, 1.5))]
pos.append(Position("OPT1", "OPT", "USD", 1, 5, 5, 1.0, 500))
res = analyze(pos, prices, cp, bench, Settings(), usd_fx=1.0)
print("warnings:", res["warnings"])
print("current :", {k: round(float(v), 3) for k, v in res["current"].items()})
print("proposed:", {k: round(float(v), 3) for k, v in res["proposed"].items()})
print("oos:", res["oos"])
for s in res["suggestions"]:
    print(f"{s['symbol']:6}{s['action']:15}{s['cur_w']:6.1%} -> {s['tgt_w']:6.1%}  {s['shares']:>6} sh  {s['why']}")
print("top candidates:", [(d['symbol'], round(d['d_sharpe'], 3)) for d in res["candidates"][:3]])
assert abs(sum(res["weights_tgt"].values()) - 1) < 1e-6
assert all(np.isfinite(list(res["weights_tgt"].values())))
assert max(res["weights_tgt"].values()) <= 0.30
print("OK")
