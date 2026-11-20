"""API models for the Personal Investment Dashboard, v1.

API fields are camelCase. Stored fields are snake_case; the server maps them.
Decimal values (prices, changes, percentages, ratios) are strings, so clients
do not lose precision. Every response field is set by the server.
"""

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

SYMBOL_PATTERN = r"^[A-Za-z][A-Za-z0-9.\-]{0,9}$"

Decimal2 = Annotated[str, Field(pattern=r"^-?\d+\.\d{2}$", examples=["229.35"])]


class SecurityType(str, Enum):
    stock = "stock"
    etf = "etf"


class Exchange(str, Enum):
    nasdaq = "nasdaq"
    nyse = "nyse"
    nyse_american = "nyse_american"
    nyse_arca = "nyse_arca"
    cboe_bzx = "cboe_bzx"


class Sector(str, Enum):
    """GICS sectors. ETFs have no sector."""

    communication_services = "communication_services"
    consumer_discretionary = "consumer_discretionary"
    consumer_staples = "consumer_staples"
    energy = "energy"
    financials = "financials"
    health_care = "health_care"
    industrials = "industrials"
    information_technology = "information_technology"
    materials = "materials"
    real_estate = "real_estate"
    utilities = "utilities"


class PriceState(str, Enum):
    """Lab 2 CON-1, evaluated at read time from providerTime."""

    delayed = "delayed"
    at_close = "at_close"
    unavailable = "unavailable"


class UnavailableReason(str, Enum):
    no_price = "no_price"
    stale = "stale"
    delisted = "delisted"


class HistoryRange(str, Enum):
    one_month = "1m"
    three_months = "3m"
    six_months = "6m"
    year_to_date = "ytd"
    one_year = "1y"
    five_years = "5y"


# ---------- Shared parts ----------


class Quote(BaseModel):
    """Latest accepted price with its derived values and freshness state.

    When priceState is unavailable, every price field is null; an old price is
    never returned as current. providerTime still shows the last accepted price
    time, or null when no price was ever accepted.
    """

    price: Decimal2 | None = Field(description="Latest accepted price in USD")
    previousClose: Decimal2 | None = Field(examples=["227.50"])
    change: Decimal2 | None = Field(description="Derived: price - previousClose", examples=["1.85"])
    changePercent: Decimal2 | None = Field(
        description="Derived: change / previousClose x 100, rounded half-up to 2 decimals",
        examples=["0.81"],
    )
    dayVolume: int | None = Field(ge=0, description="Shares traded in the current session", examples=[18400000])
    currency: Literal["USD"] = "USD"
    priceState: PriceState
    unavailableReason: UnavailableReason | None = Field(
        description="Set only when priceState is unavailable", examples=[None]
    )
    providerTime: datetime | None = Field(
        description="Time the provider assigned to the price (not the time the Dashboard received it)",
        examples=["2026-11-10T15:00:00Z"],
    )


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable code; the client selects behavior by it", examples=["invalid_type"])
    message: str = Field(description="Human-readable explanation", examples=["type: Input should be 'stock' or 'etf'"])


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------- Market data ----------


class StockSummary(BaseModel):
    symbol: str = Field(examples=["AAPL"])
    name: str = Field(examples=["Apple Inc. - Common Stock"])
    type: SecurityType
    exchange: Exchange
    sector: Sector | None = Field(description="Null for ETFs and unclassified Stocks")
    active: bool = Field(description="Derived: false when the Stock is delisted")
    quote: Quote


class StockPage(BaseModel):
    items: list[StockSummary]
    nextCursor: str | None = Field(description="Opaque token for the next page, or null at the end", examples=[None])


class StockDetail(BaseModel):
    symbol: str = Field(examples=["AAPL"])
    name: str = Field(examples=["Apple Inc. - Common Stock"])
    type: SecurityType
    exchange: Exchange
    sector: Sector | None
    industry: str | None = Field(examples=["Technology Hardware, Storage & Peripherals"])
    active: bool
    listedOn: date | None = Field(description="Null when the provider has no listing date", examples=["1980-12-12"])
    delistedOn: date | None = Field(examples=[None])


class StockPrice(BaseModel):
    symbol: str = Field(examples=["AAPL"])
    quote: Quote


class DailyBar(BaseModel):
    date: date
    open: Decimal2
    high: Decimal2
    low: Decimal2
    close: Decimal2
    volume: int = Field(ge=0)


class PriceHistory(BaseModel):
    symbol: str = Field(examples=["AAPL"])
    range: HistoryRange
    adjusted: bool = Field(description="True: prices are split-adjusted (derived from StockSplit records)")
    currency: Literal["USD"] = "USD"
    bars: list[DailyBar] = Field(description="One bar per trading day, oldest first; empty for a new listing")


class TrendingStock(BaseModel):
    rank: int = Field(ge=1, examples=[1])
    symbol: str = Field(examples=["PLTR"])
    name: str = Field(examples=["Palantir Technologies Inc. - Class A Common Stock"])
    type: SecurityType
    relativeVolume: Decimal2 = Field(description="Derived: dayVolume / averageVolume20d", examples=["2.16"])
    averageVolume20d: int = Field(ge=0, description="Derived: mean volume of the last 20 daily bars", examples=[44800000])
    quote: Quote


class TrendingList(BaseModel):
    items: list[TrendingStock] = Field(description="Complete ranked result; there is no next page")
    rankedAt: datetime = Field(description="Read time of the latest prices used for the ranking")


class OverviewRow(BaseModel):
    symbol: str
    name: str
    quote: Quote


class MarketOverview(BaseModel):
    market: Literal["US"] = "US"
    gainers: list[OverviewRow] = Field(description="Up to 10, highest positive changePercent first")
    losers: list[OverviewRow] = Field(description="Up to 10, lowest negative changePercent first")
    mostActive: list[OverviewRow] = Field(description="Up to 10, highest dayVolume first")
    builtAt: datetime = Field(description="Time of the source read (Lab 4 cached_at)")


# ---------- Watchlist ----------


class WatchlistItemCreate(BaseModel):
    """Only input model. The owner comes from the access token, never from the body."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(pattern=SYMBOL_PATTERN, description="Case-insensitive; stored by Stock identity", examples=["PLTR"])


class WatchlistItem(BaseModel):
    symbol: str = Field(examples=["PLTR"])
    name: str = Field(examples=["Palantir Technologies Inc. - Class A Common Stock"])
    active: bool = Field(description="False for a delisted Stock; it stays until the User removes it")
    addedAt: datetime = Field(examples=["2026-11-10T15:16:02Z"])
    quote: Quote


class WatchlistPage(BaseModel):
    items: list[WatchlistItem] = Field(description="Newest addedAt first")
    itemCount: int = Field(ge=0, le=100, description="Derived: number of items on the whole Watchlist", examples=[2])
    capacity: Literal[100] = Field(100, description="Maximum number of items on one Watchlist")
    nextCursor: str | None = Field(examples=[None])
