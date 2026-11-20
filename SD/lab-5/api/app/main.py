"""Personal Investment Dashboard API, v1 (Lab 5).

The routes, models, validation, errors, authentication, and examples here are
the source of the OpenAPI document. Handlers are STUBS: they read the in-memory
facts in stub_data.py instead of the Market Data Store and the User Data Store.
"""

import base64
import hashlib
import json
import time
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import stub_data as db
from .models import (
    SYMBOL_PATTERN,
    DailyBar,
    ErrorResponse,
    Exchange,
    HistoryRange,
    MarketOverview,
    OverviewRow,
    PriceHistory,
    PriceState,
    Quote,
    Sector,
    SecurityType,
    StockDetail,
    StockPage,
    StockPrice,
    StockSummary,
    TrendingList,
    TrendingStock,
    UnavailableReason,
    WatchlistItem,
    WatchlistItemCreate,
    WatchlistPage,
)

DESCRIPTION = """
Market data and the private Watchlist for the Personal Investment Dashboard.

* **Version:** major version in the path (`/v1`). Compatible changes stay in v1.
* **Authentication:** every operation needs `Authorization: Bearer <access token>`
  from the external identity provider. The owner of a Watchlist is the token subject.
* **Errors:** one shape, `{"error": {"code", "message"}}`. Invalid input is `400`.
* **Pagination:** cursor lists take `limit` (1-50, default 20) and `cursor`.
  `nextCursor: null` means the end. A cursor is valid only with the same filters.
* **Rate limits:** `429` with `Retry-After` (seconds). Wait that long before a retry.
"""

app = FastAPI(
    title="Personal Investment Dashboard API",
    version="1.0.0",
    description=DESCRIPTION,
    servers=[
        {"url": "https://api.dashboard.example", "description": "Production (example host)"},
        {"url": "http://localhost:8000", "description": "Local stub"},
    ],
    openapi_tags=[
        {"name": "Market data", "description": "Public market data; any signed-in User"},
        {"name": "Watchlist", "description": "Private; only the owner from the access token"},
    ],
)

_START = time.monotonic()


def stub_now() -> datetime:
    """STUB clock: starts at the fixed example read time and moves forward in real time."""
    return (db.NOW + timedelta(seconds=time.monotonic() - _START)).replace(microsecond=0)


# ---------- Errors ----------


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict | None = None):
        self.status, self.code, self.message, self.headers = status, code, message, headers


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(ApiError)
async def on_api_error(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(_error_body(exc.code, exc.message), status_code=exc.status, headers=exc.headers)


_FIELD_CODES = {"q": "query"}


@app.exception_handler(RequestValidationError)
async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Every validation failure is 400 with the shared error shape (not FastAPI's 422)."""
    err = exc.errors()[0]
    field = str(err["loc"][-1]) if err["loc"] else "body"
    if err["type"] == "json_invalid":
        code, message = "invalid_json", "Request body is not valid JSON"
    elif err["type"] == "extra_forbidden":
        code, message = "unknown_field", f"{field} is not an accepted field"
    elif err["type"] == "missing":
        code, message = "missing_field", f"{field} is required"
    else:
        code, message = f"invalid_{_FIELD_CODES.get(field, field)}", f"{field}: {err['msg']}"
    return JSONResponse(_error_body(code, message), status_code=400)


def errors(status: int, description: str, *cases: tuple[str, str]) -> dict:
    """OpenAPI response entry with one example per error code."""
    entry = {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "examples": {code: {"value": _error_body(code, message)} for code, message in cases}
            }
        },
    }
    if status == 429:
        entry["headers"] = {
            "Retry-After": {"description": "Seconds to wait before the next request", "schema": {"type": "integer"}}
        }
    return {status: entry}


E401 = errors(401, "Missing, invalid, or expired access token", ("authentication_required", "Sign in to continue"))
E429 = errors(429, "Rate limit reached", ("rate_limited", "Too many requests; retry after the Retry-After interval"))
E503_MARKET = errors(503, "Market data store unavailable", ("market_data_unavailable", "Market data is temporarily unavailable, retry"))
E503_WATCHLIST = errors(
    503,
    "Watchlist store unavailable, or the latest confirmed change cannot be guaranteed (CON-2)",
    ("watchlist_unavailable", "Watchlist is temporarily unavailable, retry"),
)
E404_STOCK = errors(404, "No supported Stock has this symbol", ("stock_not_found", "No supported Stock has symbol ABCD"))
E400_SYMBOL = ("invalid_symbol", "symbol: String should match pattern '^[A-Za-z][A-Za-z0-9.\\-]{0,9}$'")


# ---------- Authentication ----------

bearer = HTTPBearer(
    auto_error=False,
    scheme_name="bearerAuth",
    bearerFormat="JWT",
    description="Access token from the external identity provider (OIDC). The `sub` claim is the User ID.",
)


def current_user(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    """Return the verified User ID (token subject).

    STUB: accepts any bearer token and uses its value as the User ID. The real
    server verifies the JWT signature, issuer, audience, and expiry on every request.
    """
    if creds is None or not creds.credentials:
        raise ApiError(401, "authentication_required", "Sign in to continue")
    return creds.credentials


User = Annotated[str, Depends(current_user)]
SymbolPath = Annotated[str, Path(pattern=SYMBOL_PATTERN, description="Case-insensitive symbol", examples=["AAPL"])]
Limit = Annotated[int, Query(ge=1, le=50, description="Page size, 1-50")]
Cursor = Annotated[str | None, Query(min_length=1, max_length=200, description="nextCursor from the previous page")]


# ---------- Derived values (computed at read time, never stored) ----------

FRESHNESS_LIMIT = timedelta(minutes=20)  # Lab 2 CON-1: 15 min provider delay + 5 min sync slack
CENT = Decimal("0.01")


def market_open(now: datetime) -> bool:
    """STUB: Monday-Friday 14:30-21:00 UTC (09:30-16:00 EST). The real server reads TradingDay."""
    minutes = now.hour * 60 + now.minute
    return now.weekday() < 5 and 14 * 60 + 30 <= minutes < 21 * 60


def make_quote(s: dict, now: datetime) -> Quote:
    def unavailable(reason: UnavailableReason) -> Quote:
        return Quote(price=None, previousClose=None, change=None, changePercent=None, dayVolume=None,
                     priceState=PriceState.unavailable, unavailableReason=reason, providerTime=s["provider_time"])

    if s["delisted_on"]:
        return unavailable(UnavailableReason.delisted)
    if s["last_price"] is None:
        return unavailable(UnavailableReason.no_price)
    if market_open(now):
        if now - s["provider_time"] > FRESHNESS_LIMIT:
            return unavailable(UnavailableReason.stale)
        state = PriceState.delayed
    else:
        state = PriceState.at_close
    change = s["last_price"] - s["previous_close"]
    pct = (change / s["previous_close"] * 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return Quote(price=str(s["last_price"]), previousClose=str(s["previous_close"]), change=str(change),
                 changePercent=str(pct), dayVolume=s["day_volume"], priceState=state,
                 unavailableReason=None, providerTime=s["provider_time"])


def relative_volume(s: dict) -> Decimal:
    return (Decimal(s["day_volume"]) / Decimal(s["avg_volume_20d"])).quantize(CENT, rounding=ROUND_HALF_UP)


def find_stock(symbol: str) -> dict:
    s = db.STOCKS.get(symbol.upper())
    if s is None:
        raise ApiError(404, "stock_not_found", f"No supported Stock has symbol {symbol.upper()}")
    return s


# ---------- Cursor pagination ----------


def _fingerprint(filters: dict) -> str:
    return hashlib.sha256(json.dumps(filters, sort_keys=True, default=str).encode()).hexdigest()[:12]


def encode_cursor(after: list, filters: dict) -> str:
    raw = json.dumps({"after": after, "f": _fingerprint(filters)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None, filters: dict) -> list | None:
    if cursor is None:
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        assert data["f"] == _fingerprint(filters)
        return data["after"]
    except Exception:
        raise ApiError(400, "invalid_cursor", "cursor is not valid for these filters; start from the first page")


def paginate(rows: list, key, limit: int, cursor: str | None, filters: dict) -> tuple[list, str | None]:
    after = decode_cursor(cursor, filters)
    if after is not None:
        rows = [r for r in rows if key(r) > after]
    page = rows[:limit]
    more = len(rows) > limit
    return page, (encode_cursor(key(page[-1]), filters) if more else None)


# ---------- Market data ----------

STOCK_PAGE_EXAMPLES = {
    "filtered": {
        "summary": "type=stock&sector=information_technology&limit=2 (first page)",
        "value": {
            "items": [
                {"symbol": "AAPL", "name": "Apple Inc. - Common Stock", "type": "stock", "exchange": "nasdaq",
                 "sector": "information_technology", "active": True,
                 "quote": {"price": "229.35", "previousClose": "227.50", "change": "1.85", "changePercent": "0.81",
                           "dayVolume": 18400000, "currency": "USD", "priceState": "delayed",
                           "unavailableReason": None, "providerTime": "2026-11-10T15:00:00Z"}},
                {"symbol": "INTC", "name": "Intel Corporation - Common Stock", "type": "stock", "exchange": "nasdaq",
                 "sector": "information_technology", "active": True,
                 "quote": {"price": "22.40", "previousClose": "23.14", "change": "-0.74", "changePercent": "-3.20",
                           "dayVolume": 61800000, "currency": "USD", "priceState": "delayed",
                           "unavailableReason": None, "providerTime": "2026-11-10T15:00:00Z"}},
            ],
            "nextCursor": "eyJhZnRlciI6IFswLCAiSU5UQyJdLCAiZiI6ICJlNGNmNjVmMWVkZDQifQ",
        },
    },
    "empty": {"summary": "q=zzzz (no match)", "value": {"items": [], "nextCursor": None}},
}


@app.get(
    "/v1/market/overview",
    tags=["Market data"],
    operation_id="getMarketOverview",
    summary="US market overview: top gainers, top losers, most active",
    response_model=MarketOverview,
    responses={**E401, **E429, **E503_MARKET},
)
def get_market_overview(_: User) -> MarketOverview:
    """Each list has up to 10 rows. Stocks whose priceState is unavailable are left out.
    Ties are ordered by symbol. STUB."""
    now = stub_now()
    rows = [(s, make_quote(s, now)) for s in db.STOCKS.values()]
    rows = [(s, q) for s, q in rows if q.priceState != PriceState.unavailable]

    def row(s, q):
        return OverviewRow(symbol=s["symbol"], name=s["name"], quote=q)

    pct = lambda r: Decimal(r[1].changePercent)  # noqa: E731
    gainers = sorted((r for r in rows if pct(r) > 0), key=lambda r: (-pct(r), r[0]["symbol"]))
    losers = sorted((r for r in rows if pct(r) < 0), key=lambda r: (pct(r), r[0]["symbol"]))
    active = sorted(rows, key=lambda r: (-r[1].dayVolume, r[0]["symbol"]))
    return MarketOverview(
        gainers=[row(*r) for r in gainers[:10]],
        losers=[row(*r) for r in losers[:10]],
        mostActive=[row(*r) for r in active[:10]],
        builtAt=now,
    )


@app.get(
    "/v1/stocks",
    tags=["Market data"],
    operation_id="listStocks",
    summary="Browse, filter, and search active Stocks",
    response_model=StockPage,
    responses={
        200: {"description": "One page of matching Stocks", "content": {"application/json": {"examples": STOCK_PAGE_EXAMPLES}}},
        **errors(400, "Invalid filter, query, limit, or cursor",
                 ("invalid_type", "type: Input should be 'stock' or 'etf'"),
                 ("invalid_query", "q: String should have at least 1 character"),
                 ("invalid_limit", "limit: Input should be less than or equal to 50"),
                 ("invalid_cursor", "cursor is not valid for these filters; start from the first page")),
        **E401, **E429, **E503_MARKET,
    },
)
def list_stocks(
    _: User,
    q: Annotated[str | None, Query(min_length=1, max_length=50, description="Search by symbol or name, case-insensitive", examples=["apple"])] = None,
    type: Annotated[SecurityType | None, Query(description="Omit for stocks and ETFs")] = None,
    exchange: Annotated[Exchange | None, Query()] = None,
    sector: Annotated[Sector | None, Query(description="ETFs have no sector, so they never match")] = None,
    limit: Limit = 20,
    cursor: Cursor = None,
) -> StockPage:
    """Filters are applied before the limit. Without `q`, the order is symbol A-Z.
    With `q`, the order is: exact symbol, symbol prefix, word prefix in the name,
    text inside the name; symbol A-Z inside each group. Delisted Stocks are left out. STUB."""
    now = stub_now()
    query = q.strip().upper() if q else None

    def match(s: dict) -> int | None:
        if query is None:
            return 0
        name = s["name"].upper()
        if s["symbol"] == query:
            return 0
        if s["symbol"].startswith(query):
            return 1
        if any(word.startswith(query) for word in name.split()):
            return 2
        return 3 if query in name else None

    rows = []
    for s in db.STOCKS.values():
        group = match(s)
        if (group is None or s["delisted_on"] or (type and s["security_type"] != type.value)
                or (exchange and s["exchange"] != exchange.value) or (sector and s["sector"] != sector.value)):
            continue
        rows.append((group, s))
    rows.sort(key=lambda r: (r[0], r[1]["symbol"]))
    filters = {"q": query, "type": type, "exchange": exchange, "sector": sector}
    page, next_cursor = paginate(rows, lambda r: [r[0], r[1]["symbol"]], limit, cursor, filters)
    items = [
        StockSummary(symbol=s["symbol"], name=s["name"], type=s["security_type"], exchange=s["exchange"],
                     sector=s["sector"], active=not s["delisted_on"], quote=make_quote(s, now))
        for _, s in page
    ]
    return StockPage(items=items, nextCursor=next_cursor)


@app.get(
    "/v1/stocks/trending",
    tags=["Market data"],
    operation_id="listTrendingStocks",
    summary="Stocks ranked by relative volume",
    response_model=TrendingList,
    responses={
        **errors(400, "Invalid limit or type", ("invalid_limit", "limit: Input should be less than or equal to 50")),
        **E401, **E429, **E503_MARKET,
    },
)
def list_trending(
    _: User,
    type: Annotated[SecurityType | None, Query(description="Omit for stocks and ETFs")] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="Number of ranked Stocks, 1-50")] = 20,
) -> TrendingList:
    """relativeVolume = dayVolume / averageVolume20d, highest first, ties by symbol.
    Only active Stocks with a usable price (priceState not unavailable), 20 daily
    bars, and averageVolume20d >= 1,000,000 are ranked. One page only. STUB."""
    now = stub_now()
    ranked = []
    for s in db.STOCKS.values():
        quote = make_quote(s, now)
        if (quote.priceState == PriceState.unavailable or s["avg_volume_20d"] < 1_000_000
                or (type and s["security_type"] != type.value)):
            continue
        ranked.append((relative_volume(s), s, quote))
    ranked.sort(key=lambda r: (-r[0], r[1]["symbol"]))
    items = [
        TrendingStock(rank=i, symbol=s["symbol"], name=s["name"], type=s["security_type"],
                      relativeVolume=str(rv), averageVolume20d=s["avg_volume_20d"], quote=quote)
        for i, (rv, s, quote) in enumerate(ranked[:limit], start=1)
    ]
    return TrendingList(items=items, rankedAt=now)


@app.get(
    "/v1/stocks/{symbol}",
    tags=["Market data"],
    operation_id="getStock",
    summary="Stock reference data",
    response_model=StockDetail,
    responses={**errors(400, "Invalid symbol", E400_SYMBOL), **E401, **E404_STOCK, **E429, **E503_MARKET},
)
def get_stock(_: User, symbol: SymbolPath) -> StockDetail:
    """A delisted Stock is still returned, with active false. STUB."""
    s = find_stock(symbol)
    return StockDetail(symbol=s["symbol"], name=s["name"], type=s["security_type"], exchange=s["exchange"],
                       sector=s["sector"], industry=s["industry"], active=not s["delisted_on"],
                       listedOn=s["listed_on"], delistedOn=s["delisted_on"])


@app.get(
    "/v1/stocks/{symbol}/price",
    tags=["Market data"],
    operation_id="getStockPrice",
    summary="Latest accepted price with freshness state",
    response_model=StockPrice,
    responses={**errors(400, "Invalid symbol", E400_SYMBOL), **E401, **E404_STOCK, **E429, **E503_MARKET},
)
def get_stock_price(_: User, symbol: SymbolPath) -> StockPrice:
    """A stale or missing price is 200 with priceState unavailable, not an error. STUB."""
    s = find_stock(symbol)
    return StockPrice(symbol=s["symbol"], quote=make_quote(s, stub_now()))


@app.get(
    "/v1/stocks/{symbol}/history",
    tags=["Market data"],
    operation_id="getStockHistory",
    summary="Daily price history, split-adjusted",
    response_model=PriceHistory,
    responses={
        **errors(400, "Invalid symbol or range", E400_SYMBOL,
                 ("invalid_range", "range: Input should be '1m', '3m', '6m', 'ytd', '1y' or '5y'")),
        **E401, **E404_STOCK, **E429, **E503_MARKET,
    },
)
def get_stock_history(
    _: User,
    symbol: SymbolPath,
    range: Annotated[HistoryRange, Query(description="Bounded by 5 years of retained daily bars")] = HistoryRange.one_year,
) -> PriceHistory:
    """At most about 1,260 bars (5y), so the response has no pagination.
    STUB: returns the few stored bars for AAPL and no splits apply."""
    s = find_stock(symbol)
    bars = [DailyBar(date=d, open=o, high=h, low=lo, close=c, volume=v)
            for d, o, h, lo, c, v in db.DAILY_BARS.get(s["symbol"], [])]
    return PriceHistory(symbol=s["symbol"], range=range, adjusted=True, bars=bars)


# ---------- Watchlist ----------

WATCHLIST_PAGE_EXAMPLES = {
    "page": {
        "summary": "limit=20, two items",
        "value": {
            "items": [
                {"symbol": "PLTR", "name": "Palantir Technologies Inc. - Class A Common Stock", "active": True,
                 "addedAt": "2026-11-10T15:16:02Z",
                 "quote": {"price": "182.40", "previousClose": "171.25", "change": "11.15", "changePercent": "6.51",
                           "dayVolume": 96900000, "currency": "USD", "priceState": "delayed",
                           "unavailableReason": None, "providerTime": "2026-11-10T15:00:00Z"}},
                {"symbol": "SOFI", "name": "SoFi Technologies, Inc. - Common Stock", "active": True,
                 "addedAt": "2026-11-10T15:15:41Z",
                 "quote": {"price": None, "previousClose": None, "change": None, "changePercent": None,
                           "dayVolume": None, "currency": "USD", "priceState": "unavailable",
                           "unavailableReason": "stale", "providerTime": "2026-11-10T14:40:00Z"}},
            ],
            "itemCount": 2,
            "capacity": 100,
            "nextCursor": None,
        },
    },
    "empty": {"summary": "New User, nothing added yet", "value": {"items": [], "itemCount": 0, "capacity": 100, "nextCursor": None}},
}


def watchlist_item(symbol: str, added_at: datetime, now: datetime) -> WatchlistItem:
    s = db.STOCKS[symbol]
    return WatchlistItem(symbol=symbol, name=s["name"], active=not s["delisted_on"], addedAt=added_at,
                         quote=make_quote(s, now))


@app.get(
    "/v1/watchlist/items",
    tags=["Watchlist"],
    operation_id="listWatchlistItems",
    summary="Read my Watchlist",
    response_model=WatchlistPage,
    responses={
        200: {"description": "One page of the caller's Watchlist", "content": {"application/json": {"examples": WATCHLIST_PAGE_EXAMPLES}}},
        **errors(400, "Invalid limit or cursor",
                 ("invalid_limit", "limit: Input should be less than or equal to 50"),
                 ("invalid_cursor", "cursor is not valid for these filters; start from the first page")),
        **E401, **E429, **E503_WATCHLIST,
    },
)
def list_watchlist(user: User, response: Response, limit: Limit = 20, cursor: Cursor = None) -> WatchlistPage:
    """The Watchlist is selected only by the verified User ID. A User with no
    Watchlist yet gets an empty page. Order: newest addedAt first, then symbol. STUB."""
    response.headers["Cache-Control"] = "no-store"
    now = stub_now()
    items = db.WATCHLISTS.get(user, {})
    rows = sorted(items.items(), key=lambda r: (-r[1].timestamp(), r[0]))
    page, next_cursor = paginate(rows, lambda r: [-r[1].timestamp(), r[0]], limit, cursor, {"owner": user})
    return WatchlistPage(items=[watchlist_item(sym, at, now) for sym, at in page], itemCount=len(items),
                         nextCursor=next_cursor)


@app.get(
    "/v1/watchlist/items/{symbol}",
    tags=["Watchlist"],
    operation_id="getWatchlistItem",
    summary="Check whether a Stock is on my Watchlist",
    response_model=WatchlistItem,
    responses={
        **errors(400, "Invalid symbol", E400_SYMBOL),
        **E401,
        **errors(404, "The Stock is not on the caller's Watchlist", ("not_on_watchlist", "PLTR is not on your Watchlist")),
        **E429, **E503_WATCHLIST,
    },
)
def get_watchlist_item(user: User, symbol: SymbolPath, response: Response) -> WatchlistItem:
    """STUB."""
    response.headers["Cache-Control"] = "no-store"
    symbol = symbol.upper()
    added_at = db.WATCHLISTS.get(user, {}).get(symbol)
    if added_at is None:
        raise ApiError(404, "not_on_watchlist", f"{symbol} is not on your Watchlist")
    return watchlist_item(symbol, added_at, stub_now())


@app.post(
    "/v1/watchlist/items",
    tags=["Watchlist"],
    operation_id="addWatchlistItem",
    summary="Add a Stock to my Watchlist",
    status_code=201,
    response_model=WatchlistItem,
    responses={
        201: {"description": "Added; the change is confirmed by the User Data Store",
              "headers": {"Location": {"description": "URL of the new item", "schema": {"type": "string"},
                                       "example": "/v1/watchlist/items/PLTR"}}},
        **errors(400, "Invalid body, unsupported symbol, or delisted Stock",
                 ("invalid_json", "Request body is not valid JSON"),
                 ("missing_field", "symbol is required"),
                 ("unknown_field", "userId is not an accepted field"),
                 ("invalid_symbol", "symbol: String should match pattern '^[A-Za-z][A-Za-z0-9.\\-]{0,9}$'"),
                 ("unsupported_symbol", "ABCD is not a supported Stock"),
                 ("stock_delisted", "TWTR is delisted and cannot be added")),
        **E401,
        **errors(409, "The change conflicts with the Watchlist state",
                 ("already_on_watchlist", "PLTR is already on your Watchlist"),
                 ("watchlist_full", "A Watchlist holds at most 100 Stocks")),
        **E429, **E503_WATCHLIST,
    },
)
def add_watchlist_item(user: User, body: WatchlistItemCreate, response: Response) -> WatchlistItem:
    """Success is returned only after the User Data Store confirms the write. STUB."""
    symbol = body.symbol.upper()
    s = db.STOCKS.get(symbol)
    if s is None:
        raise ApiError(400, "unsupported_symbol", f"{symbol} is not a supported Stock")
    if s["delisted_on"]:
        raise ApiError(400, "stock_delisted", f"{symbol} is delisted and cannot be added")
    items = db.WATCHLISTS.setdefault(user, {})
    if symbol in items:
        raise ApiError(409, "already_on_watchlist", f"{symbol} is already on your Watchlist")
    if len(items) >= 100:
        raise ApiError(409, "watchlist_full", "A Watchlist holds at most 100 Stocks")
    now = stub_now()
    items[symbol] = now
    response.headers["Location"] = f"/v1/watchlist/items/{symbol}"
    response.headers["Cache-Control"] = "no-store"
    return watchlist_item(symbol, now, now)


@app.delete(
    "/v1/watchlist/items/{symbol}",
    tags=["Watchlist"],
    operation_id="removeWatchlistItem",
    summary="Remove a Stock from my Watchlist",
    status_code=204,
    response_class=Response,
    responses={
        204: {"description": "Removed; the change is confirmed by the User Data Store"},
        **errors(400, "Invalid symbol", E400_SYMBOL),
        **E401,
        **errors(404, "The Stock is not on the caller's Watchlist", ("not_on_watchlist", "PLTR is not on your Watchlist")),
        **E429, **E503_WATCHLIST,
    },
)
def remove_watchlist_item(user: User, symbol: SymbolPath) -> Response:
    """STUB."""
    symbol = symbol.upper()
    if db.WATCHLISTS.get(user, {}).pop(symbol, None) is None:
        raise ApiError(404, "not_on_watchlist", f"{symbol} is not on your Watchlist")
    return Response(status_code=204)


# ---------- OpenAPI ----------


def custom_openapi() -> dict:
    """Generated document without FastAPI's default 422 entries: this API uses 400."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, description=app.description,
                         routes=app.routes, servers=app.servers, tags=app.openapi_tags)
    for path in schema["paths"].values():
        for operation in path.values():
            operation["responses"].pop("422", None)
    # FastAPI removes null values from examples; put the exact examples back.
    for path, examples in (("/v1/stocks", STOCK_PAGE_EXAMPLES), ("/v1/watchlist/items", WATCHLIST_PAGE_EXAMPLES)):
        schema["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["examples"] = examples
    for name in ("HTTPValidationError", "ValidationError"):
        schema["components"]["schemas"].pop(name, None)
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
