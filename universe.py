"""Default pool of liquid, US-listed candidates (ticker -> (name, category)).
Edit freely, or add extra tickers in the app's sidebar."""

UNIVERSE = {
    # broad equity
    "VTI": ("Vanguard Total US Market", "US equity (broad)"),
    "VXUS": ("Vanguard Total International", "International equity"),
    "VEA": ("Vanguard Developed Markets", "Developed ex-US equity"),
    "VWO": ("Vanguard Emerging Markets", "Emerging markets equity"),
    "QQQ": ("Invesco Nasdaq 100", "US growth / tech"),
    "IWM": ("iShares Russell 2000", "US small caps"),
    "SCHD": ("Schwab US Dividend Equity", "US dividend / value"),
    "USMV": ("iShares MSCI USA Min Vol", "Low-volatility equity"),
    "QUAL": ("iShares MSCI USA Quality", "Quality factor"),
    "MTUM": ("iShares MSCI USA Momentum", "Momentum factor"),
    # sectors
    "XLU": ("Utilities Select Sector", "Utilities"),
    "XLV": ("Health Care Select Sector", "Health care"),
    "XLP": ("Consumer Staples Select Sector", "Consumer staples"),
    "XLE": ("Energy Select Sector", "Energy"),
    "XLF": ("Financials Select Sector", "Financials"),
    "XLI": ("Industrials Select Sector", "Industrials"),
    "XLK": ("Technology Select Sector", "Technology"),
    # bonds
    "AGG": ("iShares Core US Aggregate Bond", "Bonds (aggregate)"),
    "BND": ("Vanguard Total Bond Market", "Bonds (aggregate)"),
    "TLT": ("iShares 20+ Year Treasury", "Long-term Treasuries"),
    "IEF": ("iShares 7-10 Year Treasury", "Intermediate Treasuries"),
    "LQD": ("iShares Investment Grade Corp", "Corporate bonds"),
    "TIP": ("iShares TIPS Bond", "Inflation-linked bonds"),
    # real assets
    "GLD": ("SPDR Gold Shares", "Gold"),
    "DBC": ("Invesco DB Commodity Index", "Commodities"),
    "VNQ": ("Vanguard Real Estate", "Real estate"),
    # large-cap stocks
    "MSFT": ("Microsoft", "Large-cap tech"),
    "AAPL": ("Apple", "Large-cap tech"),
    "GOOGL": ("Alphabet", "Large-cap tech / communication"),
    "AMZN": ("Amazon", "Large-cap consumer / cloud"),
    "NVDA": ("NVIDIA", "Semiconductors"),
    "BRK-B": ("Berkshire Hathaway B", "Diversified financials"),
    "JNJ": ("Johnson & Johnson", "Health care"),
    "LLY": ("Eli Lilly", "Health care"),
    "UNH": ("UnitedHealth", "Health care"),
    "PG": ("Procter & Gamble", "Consumer staples"),
    "KO": ("Coca-Cola", "Consumer staples"),
    "COST": ("Costco", "Consumer staples / retail"),
    "WMT": ("Walmart", "Consumer staples / retail"),
    "JPM": ("JPMorgan Chase", "Financials"),
    "V": ("Visa", "Payments"),
    "MA": ("Mastercard", "Payments"),
    "XOM": ("Exxon Mobil", "Energy"),
    "HD": ("Home Depot", "Consumer discretionary"),
}
