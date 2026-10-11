"""Portfolio analytics: Sharpe, risk, diversification, optimisation, suggestions.

Everything here is pure pandas/numpy/scipy (no IBKR dependency) so it can be tested offline.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

TD = 252  # trading days per year
NEW_POSITION_CAP = 0.10  # max weight the optimiser may give to a *new* candidate


@dataclass
class Position:
    symbol: str
    sec_type: str
    currency: str
    qty: float
    price: float          # last price, contract currency
    avg_cost: float       # per share, contract currency
    fx: float             # base currency per 1 unit of contract currency
    value_base: float     # market value in account base currency
    pnl_base: float = 0.0  # unrealised P&L in base currency


@dataclass
class Settings:
    rf: float = 0.03               # annual risk-free rate
    max_weight: float = 0.20       # cap per position
    vol_cap: float | None = None   # optional annual volatility ceiling (e.g. 0.15)
    trade_threshold: float = 0.02  # ignore weight changes smaller than this
    close_threshold: float = 0.01  # target weight below this -> close
    n_candidates: int = 6          # candidates allowed into the optimisation
    shrink_mu: float = 0.5         # 0 = raw historical means, 1 = all assets equal
    shrink_cov: float = 0.2        # shrink covariance toward its diagonal


# ----------------------------------------------------------------------------- metrics
def perf(r: pd.Series, rf: float, bench: pd.Series | None = None) -> dict:
    r = r.dropna()
    n = len(r)
    mean = r.mean() * TD
    vol = r.std(ddof=1) * np.sqrt(TD)
    cum = (1 + r).cumprod()
    out = {
        "ret": cum.iloc[-1] ** (TD / n) - 1,
        "vol": vol,
        "sharpe": (mean - rf) / vol if vol > 0 else np.nan,
        "mdd": (cum / cum.cummax() - 1).min(),
        "var95": -np.percentile(r, 5),
        "beta": np.nan,
    }
    if bench is not None:
        b = bench.reindex(r.index).dropna()
        if len(b) > 30 and b.var() > 0:
            out["beta"] = r.reindex(b.index).cov(b) / b.var()
    return out


def diversification(w: np.ndarray, cov: np.ndarray) -> tuple[float, float]:
    """(effective number of positions, diversification ratio)."""
    w = np.asarray(w)
    pv = np.sqrt(w @ cov @ w)
    eff_n = 1.0 / np.sum(w ** 2)
    dr = float(w @ np.sqrt(np.diag(cov)) / pv) if pv > 0 else np.nan
    return eff_n, dr


# ----------------------------------------------------------------------------- optimiser
def _solve(R: pd.DataFrame, caps: np.ndarray, s: Settings) -> tuple[np.ndarray, np.ndarray]:
    """Max-Sharpe, long-only, capped, with shrunk inputs to limit estimation noise.

    Returns (weights, caps actually used). If no asset beats the risk-free rate, Sharpe is
    ill-posed (it would reward volatility), so we minimise variance instead.
    """
    n = R.shape[1]
    m = R.mean().values * TD
    mu = (1 - s.shrink_mu) * m + s.shrink_mu * m.mean()
    cov = R.cov().values * TD
    cov = (1 - s.shrink_cov) * cov + s.shrink_cov * np.diag(np.diag(cov))

    caps = np.asarray(caps, dtype=float)
    if caps.sum() < 1.05:  # caps must allow a fully-invested portfolio; scale them up together
        caps = caps * (1.05 / caps.sum())
    x0 = np.minimum(np.full(n, 1 / n), caps)
    x0 = x0 / x0.sum()

    if mu.max() <= s.rf:
        def objective(w):
            return w @ cov @ w
    else:
        def objective(w):
            v = np.sqrt(w @ cov @ w)
            return -(w @ mu - s.rf) / v if v > 0 else 0.0

    base = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    bounds = [(0, c) for c in caps]
    attempts = []
    if s.vol_cap:
        attempts.append(base + [{"type": "ineq", "fun": lambda w: s.vol_cap - np.sqrt(w @ cov @ w)}])
    attempts.append(base)
    for cons in attempts:
        res = minimize(objective, x0, bounds=bounds, constraints=cons, method="SLSQP",
                       options={"maxiter": 500, "ftol": 1e-9})
        if res.success:
            w = np.clip(res.x, 0, None)
            return w / w.sum(), caps
    return x0, caps


# ----------------------------------------------------------------------------- main entry
def analyze(positions: list[Position], prices: pd.DataFrame, cand_prices: pd.DataFrame,
            bench: pd.Series | None, s: Settings, meta: dict | None = None,
            usd_fx: float = 1.0) -> dict:
    meta = meta or {}
    warnings: list[str] = []

    # ---- 1. which positions can be analysed
    held: list[Position] = []
    for p in positions:
        if p.sec_type != "STK":
            warnings.append(f"{p.symbol} ({p.sec_type}) skipped: only stocks/ETFs are analysed.")
        elif p.value_base <= 0:
            warnings.append(f"{p.symbol} skipped: short or zero-value position.")
        elif p.symbol not in prices.columns or prices[p.symbol].dropna().size < 60:
            warnings.append(f"{p.symbol} skipped: not enough price history.")
        else:
            held.append(p)
    if not held:
        raise ValueError("No analysable long stock/ETF positions found.")
    hs = [p.symbol for p in held]

    # ---- 2. joint return table (held + candidates)
    cp = cand_prices.drop(columns=[c for c in cand_prices.columns if c in hs], errors="ignore")
    allp = pd.concat([prices[hs], cp], axis=1).sort_index().ffill(limit=5)
    cnt = allp.notna().sum()
    keep = [c for c in allp.columns if cnt[c] >= 0.9 * cnt.max()]
    for sym in hs:
        if sym not in keep:
            warnings.append(f"{sym} skipped: history too short vs the others.")
    held = [p for p in held if p.symbol in keep]
    hs = [p.symbol for p in held]
    if not hs:
        raise ValueError("No position has enough history.")
    rets = allp[keep].pct_change().dropna()
    if len(rets) < 60:
        raise ValueError("Not enough overlapping history (need at least 60 trading days).")
    bench_r = None
    if bench is not None and bench.dropna().size > 60:
        bench_r = bench.sort_index().ffill(limit=5).pct_change().reindex(rets.index)

    values = np.array([p.value_base for p in held])
    total = values.sum()
    w = values / total
    cands = [c for c in rets.columns if c not in hs]

    # ---- 3. current portfolio
    port_r = rets[hs] @ w
    cur = perf(port_r, s.rf, bench_r)
    cov_s = rets[hs].cov().values * TD
    cur["eff_n"], cur["div_ratio"] = diversification(w, cov_s)
    pvar = w @ cov_s @ w
    rc = w * (cov_s @ w) / pvar if pvar > 0 else np.zeros(len(w))

    # ---- 4. per-position stats
    rows = []
    stats = {}
    for i, p in enumerate(held):
        r_i = rets[p.symbol]
        pi = perf(r_i, s.rf)
        wi = w[i]
        rest = (port_r - wi * r_i) / (1 - wi) if wi < 0.999 else port_r
        corr = r_i.corr(rest)
        stats[p.symbol] = dict(sharpe=pi["sharpe"], corr=corr, rc=rc[i], w=wi)
        rows.append(dict(symbol=p.symbol, qty=p.qty, price=p.price, currency=p.currency,
                         value=p.value_base, weight=wi, ret=pi["ret"], vol=pi["vol"],
                         sharpe=pi["sharpe"], risk=rc[i], corr=corr, pnl=p.pnl_base))

    # ---- 5. candidate screening: marginal Sharpe of adding 5 %
    crow = []
    for c in cands:
        r_c = rets[c]
        new_r = 0.95 * port_r + 0.05 * r_c
        np_ = perf(new_r, s.rf)
        pc = perf(r_c, s.rf)
        m = meta.get(c, ("", ""))
        crow.append(dict(symbol=c, name=m[0], category=m[1], ret=pc["ret"], vol=pc["vol"],
                         sharpe=pc["sharpe"], mdd=pc["mdd"], corr=r_c.corr(port_r),
                         d_sharpe=np_["sharpe"] - cur["sharpe"], d_vol=np_["vol"] - cur["vol"],
                         price=float(allp[c].dropna().iloc[-1])))
    crow.sort(key=lambda d: d["d_sharpe"], reverse=True)
    top = [d["symbol"] for d in crow[: s.n_candidates] if d["d_sharpe"] > 0]

    # ---- 6. optimisation on held + best candidates
    uni = hs + top
    caps = np.array([s.max_weight] * len(hs) + [min(s.max_weight, NEW_POSITION_CAP)] * len(top))
    w_opt, caps_used = _solve(rets[uni], caps, s)
    if caps_used[0] > s.max_weight + 1e-9:
        warnings.append(f"Max weight raised to {caps_used[0]:.0%} for the optimisation: you hold too few "
                        "positions for the {:.0%} cap to allow a fully invested portfolio.".format(s.max_weight))
    if rets[uni].mean().mean() * TD <= s.rf:
        warnings.append("Average excess return over the risk-free rate is negative on this history: "
                        "the proposal minimises risk rather than maximising Sharpe.")
    w_opt = np.where(w_opt < 0.005, 0, w_opt)
    w_opt = w_opt / w_opt.sum()
    target = dict(zip(uni, w_opt))

    prop_r = rets[uni] @ w_opt
    prop = perf(prop_r, s.rf, bench_r)
    prop["eff_n"], prop["div_ratio"] = diversification(w_opt, rets[uni].cov().values * TD)

    # ---- 7. out-of-sample sanity check (fit on first 70 %, judge on last 30 %)
    oos = None
    try:
        cut = int(len(rets) * 0.7)
        w_tr, _ = _solve(rets[uni].iloc[:cut], caps, s)
        test = rets.iloc[cut:]
        cur_t = perf(test[hs] @ w, s.rf)
        prop_t = perf(test[uni] @ w_tr, s.rf)
        oos = dict(current=cur_t["sharpe"], proposed=prop_t["sharpe"], days=len(test))
    except Exception:
        pass

    # ---- 8. suggestions
    sug = []
    for p in held:
        cw, tw = stats[p.symbol]["w"], target.get(p.symbol, 0.0)
        st = stats[p.symbol]
        unit = p.price * p.fx
        if tw < s.close_threshold:
            act, sh = "CLOSE", p.qty
            why = (f"Sharpe {st['sharpe']:.2f} vs {cur['sharpe']:.2f} for the portfolio; "
                   f"{st['rc']:.0%} of risk for {cw:.0%} of capital.")
        elif tw - cw > s.trade_threshold:
            act, sh = "BUY MORE", (tw - cw) * total / unit
            if st["rc"] < cw:
                why = (f"Only {st['rc']:.0%} of portfolio risk for {cw:.0%} of capital "
                       f"(correlation {st['corr']:.2f} with the rest): room to add diversification.")
            else:
                why = (f"Sharpe {st['sharpe']:.2f}, correlation {st['corr']:.2f} with the rest of the "
                       f"portfolio: better risk-adjusted return than its weight reflects.")
        elif cw - tw > s.trade_threshold:
            act, sh = "SELL (REDUCE)", (cw - tw) * total / unit
            why = (f"{st['rc']:.0%} of portfolio risk for {cw:.0%} of capital; "
                   f"Sharpe {st['sharpe']:.2f}.")
        else:
            act, sh, why = "HOLD", 0.0, "Weight already close to the optimum."
        sug.append(dict(symbol=p.symbol, action=act, cur_w=cw, tgt_w=tw,
                        shares=round(sh), value=(tw - cw) * total, why=why))
    cmap = {d["symbol"]: d for d in crow}
    for c in top:
        tw = target.get(c, 0.0)
        if tw >= s.trade_threshold:
            d = cmap[c]
            px = d["price"] * usd_fx
            sug.append(dict(symbol=c, action="BUY (NEW)", cur_w=0.0, tgt_w=tw,
                            shares=round(tw * total / px) if px > 0 else 0, value=tw * total,
                            why=(f"{d['category'] or 'New exposure'}; correlation {d['corr']:.2f} "
                                 f"with your portfolio; adding 5% moves Sharpe {d['d_sharpe']:+.2f}.")))
    order = {"CLOSE": 0, "SELL (REDUCE)": 1, "BUY MORE": 2, "BUY (NEW)": 3, "HOLD": 4}
    sug.sort(key=lambda d: (order[d["action"]], -abs(d["value"])))

    curves = pd.DataFrame({"Current": (1 + port_r).cumprod(), "Proposed (in-sample)": (1 + prop_r).cumprod()})
    if bench_r is not None:
        curves["SPY"] = (1 + bench_r.fillna(0)).cumprod()

    return dict(warnings=warnings, total=total, current=cur, proposed=prop, oos=oos,
                positions=rows, suggestions=sug, candidates=crow, curves=curves,
                weights_cur=dict(zip(hs, w)), weights_tgt=target, n_days=len(rets))
