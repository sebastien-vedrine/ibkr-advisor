# IBKR Portfolio Advisor

Windows desktop app: connects (read-only) to your Interactive Brokers account, analyses the
portfolio, tracks the Sharpe ratio and suggests trades plus new candidates.

## Run
1. `pip install -r requirements.txt`
2. In IB Gateway (live), enable the API once: Configure > Settings > API > Settings >
   *Enable ActiveX and Socket Clients* (default live port 4001).
3. `python main.py` -> the app launches IB Gateway (if not already running), you log in, and the
   portfolio loads automatically. The sidebar dot shows the connection: green = connected,
   amber = waiting for login, red = not running (click it to launch the Gateway).
   The Gateway is found under `C:\Jts\ibgateway\<version>`; otherwise set its path in Settings
   (along with host / port / client ID).

Install: get **`Installer-IBKR-Advisor.exe`** from the latest GitHub release (or add
`sebastien-vedrine/ibkr-advisor` to [Vedware](https://github.com/sebastien-vedrine/vedware), which
also installs updates). Per-user install, no admin rights.

Build the installer: run `build.bat` on Windows (installs Python / Inno Setup with winget if needed;
output `dist\Installer-IBKR-Advisor.exe`), or push a tag matching `__version__` in `main.py`
(e.g. `v1.1.0`): GitHub Actions builds it and publishes the release.

Offline test with synthetic data: `python test_analytics.py`.

## What it does
(New UI: sidebar navigation, KPI cards, sector heatmap. No IBKR? Use **Try demo data** in the sidebar.)

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
  Sharpe gained if you put 5% in them, with a fit rating (Strong / Good / Slight / Neutral / Worse), a
  chart of the Sharpe change for every candidate, max drawdown and the weight the proposal gives them.
- **Stock details**: click a stock in Discover, Positions or Valuation (double-click in Suggestions) to
  open its own window: P/E vs its history (with an annual P/E chart), forward P/E, PEG, dividend yield,
  P/B, P/S, EV/EBITDA, margins, analyst target, price vs SPY and how it fits your portfolio. Candidates'
  data is fetched from Yahoo/FMP when the window opens.

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
