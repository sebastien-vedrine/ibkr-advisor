"""Read-only IBKR access through TWS / IB Gateway (ib_async)."""
from __future__ import annotations

import asyncio
import math

import pandas as pd
from ib_async import IB, util

from analytics import Position


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x)) and x != 0


def fetch_portfolio(host: str, port: int, client_id: int, years: int, say):
    """Returns (positions, history {symbol: close Series}, account info dict)."""
    asyncio.set_event_loop(asyncio.new_event_loop())  # we run in a worker thread
    ib = IB()
    try:
        ib.connect(host, port, clientId=client_id, readonly=True, timeout=20)
    except Exception as e:
        raise ConnectionError(
            f"Could not connect to {host}:{port}. Is TWS / IB Gateway running with the API "
            f"enabled (and this port)? Details: {e!r}")
    try:
        vals = ib.accountValues()
        base = next((v.currency for v in vals
                     if v.tag == "NetLiquidation" and v.currency not in ("BASE", "")), "USD")
        fx = {v.currency: float(v.value) for v in vals
              if v.tag == "ExchangeRate" and v.currency != "BASE"}
        fx[base] = 1.0

        def total(tag):
            return sum(float(v.value) for v in vals if v.tag == tag and v.currency == base)

        account = dict(base=base, nav=total("NetLiquidation"), cash=total("TotalCashValue"),
                       accounts=", ".join(ib.managedAccounts()), fx=fx)

        # aggregate identical contracts across accounts
        agg: dict[int, dict] = {}
        for it in ib.portfolio():
            c = it.contract
            if it.position == 0:
                continue
            a = agg.setdefault(c.conId, dict(c=c, qty=0.0, cost=0.0, pnl=0.0, px=it.marketPrice))
            a["qty"] += it.position
            a["cost"] += it.position * it.averageCost
            a["pnl"] += it.unrealizedPNL if _ok(it.unrealizedPNL) else 0.0

        positions, history, used = [], {}, set()
        items = list(agg.values())
        for i, a in enumerate(items, 1):
            c = a["c"]
            key = c.symbol if c.symbol not in used else f"{c.symbol}_{c.currency}"
            used.add(key)
            f = fx.get(c.currency, 1.0)
            px = a["px"]
            if c.secType == "STK":
                say(f"Downloading history from IBKR ({i}/{len(items)}): {c.symbol}")
                if not c.exchange:
                    c.exchange = "SMART"
                bars = []
                for what in ("ADJUSTED_LAST", "TRADES"):
                    try:
                        bars = ib.reqHistoricalData(c, "", f"{years} Y", "1 day", what, True, 1)
                    except Exception:
                        bars = []
                    if bars:
                        break
                if bars:
                    df = util.df(bars)
                    s = pd.Series(df["close"].values, index=pd.to_datetime(df["date"]), name=key)
                    history[key] = s[~s.index.duplicated()]
                    if not _ok(px):
                        px = float(s.iloc[-1])
                ib.sleep(0.25)  # stay clear of historical-data pacing limits
            if not _ok(px):
                px = a["cost"] / a["qty"] if a["qty"] else 0.0
            mult = float(c.multiplier) if c.multiplier else 1.0
            positions.append(Position(
                symbol=key, sec_type=c.secType, currency=c.currency, qty=a["qty"], price=px,
                avg_cost=a["cost"] / a["qty"] / mult if a["qty"] else 0.0, fx=f,
                value_base=a["qty"] * px * mult * f, pnl_base=a["pnl"] * f))
        hist_df = pd.DataFrame(history).sort_index()
        return positions, hist_df, account
    finally:
        ib.disconnect()
