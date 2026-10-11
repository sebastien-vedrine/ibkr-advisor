"""Yahoo Finance prices, used for the candidate pool and the SPY benchmark."""
import pandas as pd
import yfinance as yf


def norm(sym: str) -> str:
    """IB symbol -> Yahoo ticker (e.g. 'BRK B' / 'BRK.B' -> 'BRK-B')."""
    return sym.strip().upper().replace(" ", "-").replace(".", "-")


def fetch_yahoo(tickers: list[str], years: int) -> pd.DataFrame:
    tickers = sorted(set(tickers))
    if not tickers:
        return pd.DataFrame()
    data = yf.download(tickers, period=f"{years}y", interval="1d", auto_adjust=True,
                       progress=False, threads=True)
    if data is None or data.empty:
        return pd.DataFrame()
    close = data["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.dropna(axis=1, how="all")
