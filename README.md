# IBKR Portfolio Advisor

Windows desktop app: connects (read-only) to your Interactive Brokers account, analyses the
portfolio, tracks the Sharpe ratio and suggests trades plus new candidates.

## Run
1. `pip install -r requirements.txt`
2. Start **TWS** or **IB Gateway**, log in, then enable the API:
   Configuration > API > Settings > *Enable ActiveX and Socket Clients*
   (ports: TWS 7496 live / 7497 paper, Gateway 4001 live / 4002 paper).
3. `python main.py` -> the connection dialog opens -> *Connect & analyze*.

Single .exe: run `build.bat` (output: `dist\IBKR-Advisor.exe`).
Offline test with synthetic data: `python test_analytics.py`.

## What it does
(New UI: sidebar navigation, KPI cards, sector heatmap. No TWS? Use **Try demo data** in the connect dialog.)

- **Overview**: Sharpe, return, volatility, max drawdown, 1-day VaR, beta vs SPY, effective number
  of positions, diversification ratio - current vs proposed - plus charts.
- **Suggestions**: CLOSE / SELL (REDUCE) / BUY MORE / BUY (NEW) / HOLD with approx. shares and value.
- **Positions**: per-holding return, vol, Sharpe, share of total risk, correlation with the rest.
- **Valuation (P/E)**: current and forward P/E, 5/10/15-year average P/E and the premium/discount vs
  history for each holding and each suggested new stock. Without an FMP API key (Settings) the averages
  are rebuilt from Yahoo's last ~4 annual reports; a free key from financialmodelingprep.com gives up to
  15 years (depth depends on your FMP plan; the app shows how many years each average really uses).
  Non-US tickers may have no Yahoo/FMP data. P/E hints are also appended to the suggestion reasons.
- **Sector momentum**: the 11 S&P 500 sectors (SPDR ETFs) ranked by momentum (avg of 3M, 6M, 12-1M),
  with 1M/3M/6M/12M returns, relative strength vs SPY and the 200-day trend.
- **Discover**: candidates (ETFs + large caps in `universe.py`, plus tickers you add) ranked by the
  Sharpe gained if you put 5% in them.

## Method (and its limits)
- Prices: IBKR daily history for your holdings (Yahoo fallback), Yahoo for candidates and SPY.
- Target weights: long-only max-Sharpe, per-position cap (default 20%, new names 10%), optional
  volatility cap. Expected returns are shrunk 50% toward the group average and the covariance 20%
  toward its diagonal to reduce estimation noise. If nothing beats the risk-free rate it minimises
  variance instead.
- Suggestions rebalance within your invested stock/ETF capital (cash not touched).
- The "reality check" refits on the first 70% of the history and tests on the last 30%.
- Known simplifications: returns are in each stock's own currency (no FX effect); options, futures
  and shorts are listed but excluded; taxes, fees and liquidity are ignored.
- Historical Sharpe optimisation overfits easily. Treat output as a screening tool, not advice.
- The app connects with `readonly=True` and has no order-placement code.
