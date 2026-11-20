"""STUB DATA. In-memory facts that stand in for the Market Data Store and the
User Data Store. Only stored facts are kept here; every derived value (change,
changePercent, relativeVolume, priceState, active, itemCount) is computed in
main.py at read time, as the real server does.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

UTC = timezone.utc

# STUB: fixed read time, so the freshness labels in the examples stay the same.
# 2026-11-10 is a Tuesday; 15:15:20Z = 10:15:20 ET, inside market hours.
NOW = datetime(2026, 11, 10, 15, 15, 20, tzinfo=UTC)

# stock (reference) + latest_price + 20-day average volume from daily_bar
# symbol, name, security_type, exchange, sector, industry, listed_on, delisted_on,
# last_price, previous_close, day_volume, provider_time, avg_volume_20d
_T = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
STOCKS = {
    s[0]: dict(zip(
        ("symbol", "name", "security_type", "exchange", "sector", "industry", "listed_on", "delisted_on",
         "last_price", "previous_close", "day_volume", "provider_time", "avg_volume_20d"), s))
    for s in [
        ("AAPL", "Apple Inc. - Common Stock", "stock", "nasdaq", "information_technology",
         "Technology Hardware, Storage & Peripherals", date(1980, 12, 12), None,
         Decimal("229.35"), Decimal("227.50"), 18_400_000, _T, 52_600_000),
        ("INTC", "Intel Corporation - Common Stock", "stock", "nasdaq", "information_technology",
         "Semiconductors & Semiconductor Equipment", date(1971, 10, 13), None,
         Decimal("22.40"), Decimal("23.14"), 61_800_000, _T, 71_500_000),
        ("MSFT", "Microsoft Corporation - Common Stock", "stock", "nasdaq", "information_technology",
         "Software", date(1986, 3, 13), None,
         Decimal("512.10"), Decimal("509.80"), 6_150_000, _T, 21_300_000),
        ("NVDA", "NVIDIA Corporation - Common Stock", "stock", "nasdaq", "information_technology",
         "Semiconductors & Semiconductor Equipment", date(1999, 1, 22), None,
         Decimal("141.20"), Decimal("135.64"), 98_500_000, _T, 182_000_000),
        ("PLTR", "Palantir Technologies Inc. - Class A Common Stock", "stock", "nasdaq", "information_technology",
         "Software", date(2020, 9, 30), None,
         Decimal("182.40"), Decimal("171.25"), 96_900_000, _T, 44_800_000),
        ("SOFI", "SoFi Technologies, Inc. - Common Stock", "stock", "nasdaq", "financials",
         "Consumer Finance", date(2021, 6, 1), None,
         Decimal("29.80"), Decimal("29.10"), 30_100_000, datetime(2026, 11, 10, 14, 40, tzinfo=UTC), 60_200_000),
        ("SPY", "SPDR S&P 500 ETF Trust", "etf", "nyse_arca", None,
         None, date(1993, 1, 22), None,
         Decimal("681.20"), Decimal("679.90"), 22_700_000, _T, 71_000_000),
        ("XOM", "Exxon Mobil Corporation Common Stock", "stock", "nyse", "energy",
         "Oil, Gas & Consumable Fuels", None, None,
         Decimal("118.62"), Decimal("119.05"), 4_100_000, _T, 15_900_000),
    ]
}

# daily_bar (raw, before split adjustment): three recent bars for AAPL only.
DAILY_BARS = {
    "AAPL": [
        (date(2026, 11, 5), "226.10", "228.40", "225.30", "227.90", 48_200_000),
        (date(2026, 11, 6), "227.80", "229.10", "226.20", "226.85", 45_900_000),
        (date(2026, 11, 9), "226.90", "228.75", "226.10", "227.50", 41_300_000),
    ]
}

# watchlist + watchlist_item, keyed by owner_user_id (the token subject).
WATCHLISTS: dict[str, dict[str, datetime]] = {}
