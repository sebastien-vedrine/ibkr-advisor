"""Synthetic data so you can explore the app without IBKR / internet."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analytics import Position
from sectors import SECTORS
from universe import UNIVERSE


def make_demo_raw(seed: int = 11) -> dict:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=520)
    mkt = rng.normal(0.0004, 0.009, len(idx))

    def px(mu, vol, beta, start=100):
        r = mu / 252 + beta * mkt + rng.normal(0, vol / np.sqrt(252), len(idx))
        return pd.Series(start * np.cumprod(1 + r), index=idx)

    spec = {"AAPL": (.14, .22, 1.1), "MSFT": (.16, .20, 1.0), "NVDA": (.35, .38, 1.5),
            "JNJ": (.05, .14, .4), "KO": (.06, .12, .3), "XOM": (.08, .22, .7)}
    qty = {"AAPL": 60, "MSFT": 35, "NVDA": 90, "JNJ": 40, "KO": 120, "XOM": 70}
    hist = pd.DataFrame({k: px(*v) for k, v in spec.items()}).iloc[-252:]
    positions = [Position(k, "STK", "USD", qty[k], hist[k].iloc[-1], hist[k].iloc[0], 0.92,
                          qty[k] * hist[k].iloc[-1] * 0.92, qty[k] * (hist[k].iloc[-1] - hist[k].iloc[0]) * 0.92)
                 for k in spec]
    cands = pd.DataFrame({t: px(rng.uniform(.02, .16), rng.uniform(.05, .3), rng.uniform(-.1, 1.2))
                          for t in UNIVERSE if t not in spec}).iloc[-252:]
    bench = px(.10, .15, 1.0).iloc[-252:]
    drift = dict(zip(SECTORS, [.22, .10, .04, -.06, .12, .02, .14, .08, -.02, .01, .18]))
    sp = pd.DataFrame({e: px(drift[e], .16, 1.0) for e in SECTORS})
    sp["SPY"] = px(.10, .15, 1.0)

    year = pd.Timestamp.today().year - 1

    def v(pe, a5, a10, a15, fwd=None, n=(5, 10, 15), src="FMP"):
        # 15 synthetic annual P/Es whose 5/10/15y means roughly match the averages
        lvl = [a5] * 5 + [2 * a10 - a5] * 5 + [3 * a15 - 2 * a10] * 5
        hist = [(str(year - i), round(x * (1 + 0.12 * np.sin(1.7 * i)), 1)) for i, x in enumerate(lvl)]
        return dict(pe=pe, fwd=fwd, avg5=a5, n5=n[0], avg10=a10, n10=n[1], avg15=a15, n15=n[2], source=src,
                    hist=hist, info={})

    val = {"AAPL": v(33.8, 28.1, 24.3, 20.2, 30.1), "MSFT": v(36.2, 33.5, 31.0, 27.4, 31.8),
           "NVDA": v(52.4, 62.0, 48.7, 38.9, 33.0), "JNJ": v(16.1, 22.7, 21.4, 19.9, 15.0),
           "KO": v(25.9, 26.2, 24.8, 23.1, 22.4), "XOM": v(14.2, 11.9, 16.8, 15.2, 13.1)}
    account = dict(base="EUR", nav=82_400.0, cash=6_150.0, accounts="U1234567 (demo)", fx={"EUR": 1.0, "USD": 0.92})
    return dict(positions=positions, hist=hist, account=account, cands=cands, bench=bench,
                sector_prices=sp, valuation=val, fmp_key="", offline=True)
