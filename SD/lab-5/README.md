# Lab 5: Personal Investment Dashboard - Data Model and API

Scope: market overview, trending Stocks, filter and search, Stock detail, latest accepted prices, daily history, and the private Watchlist. Orders, Holdings, profit and loss, SSE, public sharing, and broker import are outside this lab. The brief asks for `SOLUTION.md`, but the presentation rules require `README.md`, so the solution is in this README. Source definitions and the generated OpenAPI are in [`api/`](./api/).

---

## 1. Data model

### Entities

| Entity | Store | Purpose | Identity | Relationships |
| ------ | ----- | ------- | -------- | ------------- |
| Stock | Market Data Store | One supported US common stock or ETF (Lab 2 definition) | `stock_id` (internal); `symbol` is unique among listed Stocks | Has 0..1 LatestPrice, 0..* DailyBar, 0..* StockSplit. Followed in 0..* WatchlistItem. |
| LatestPrice | Market Data Store | Latest accepted price; each sync overwrites it | `stock_id` (one per Stock) | Belongs to 1 Stock |
| DailyBar | Market Data Store | Raw prices of one trading day, kept 5 years | (`stock_id`, `trading_date`) | Belongs to 1 Stock and 1 TradingDay |
| StockSplit | Market Data Store | A split, used to adjust history (Lab 2 corporate actions) | (`stock_id`, `ex_date`) | Belongs to 1 Stock |
| TradingDay | Market Data Store | Market calendar for market hours and "At close" | `trading_date` | Dates 0..* DailyBar |
| SyncRun | Market Data Store (internal) | One Collector run, the Lab 3 sync record | `sync_run_id` | Has 0..* SyncRejection |
| SyncRejection | Market Data Store (internal) | One provider record that a run rejected | (`sync_run_id`, `symbol`) | Belongs to 1 SyncRun |
| Watchlist | User Data Store | The private list of one User, created on the first add | `watchlist_id`; `owner_user_id` is unique | Owned by 1 external User. Contains 0..100 WatchlistItem. |
| WatchlistItem | User Data Store | One followed Stock | (`watchlist_id`, `stock_id`) | Belongs to 1 Watchlist. Refers to 1 Stock in the other store. |
| User (external) | Identity provider | The authenticated person; no local table | Token `sub` claim | Owns 0..1 Watchlist |

### Fields

All prices are in USD. "Rejected" means that the Market Data Collector does not save the provider record and writes a SyncRejection.

#### Stock

| Field | Meaning | Example | Missing value |
| ----- | ------- | ------- | ------------- |
| `stock_id` | Internal ID; it stays the same when the symbol changes | `104` | Never missing; set by the Collector |
| `symbol` | Ticker from the provider symbol files | `AAPL` | Rejected |
| `figi` | Global identifier; the Collector uses it to match a renamed symbol | `BBG000B9XRY4` | `null`; matching then uses `symbol` |
| `name` | Security name from the symbol files | `Apple Inc. - Common Stock` | Rejected |
| `security_type` | `stock` or `etf` | `stock` | Rejected |
| `exchange` | Primary listing exchange | `nasdaq` | Rejected |
| `sector` | GICS sector | `information_technology` | `null` for ETFs and unclassified stocks |
| `industry` | GICS industry | `Technology Hardware, Storage & Peripherals` | `null` when `sector` is `null` |
| `listed_on` | First listing date | `1980-12-12` | `null`; the API returns `null` |
| `delisted_on` | Date the listing ended | `null` | `null` while listed |
| `reference_updated_at` | Time of the last reference sync that changed the record | `2026-11-10T11:00:00Z` | Never missing |

#### LatestPrice

| Field | Meaning | Example | Missing value |
| ----- | ------- | ------- | ------------- |
| `stock_id` | Stock of the price | `104` | Never missing |
| `last_price` | Last trade price in the provider snapshot | `229.35` | No row before the first accepted price: the API returns `priceState: unavailable`, `no_price` |
| `previous_close` | Close of the previous session | `227.50` | `null` on the first trading day: `change` and `changePercent` are `null` |
| `day_volume` | Shares traded in the current session | `18400000` | `0` before the first trade of the session |
| `provider_time` | Time the provider assigned to the price | `2026-11-10T15:00:00Z` | Rejected (Lab 3) |
| `received_at` | Time the Collector saved the price | `2026-11-10T15:01:04Z` | Never missing. Used only to monitor syncs. |

#### DailyBar

| Field | Meaning | Example | Missing value |
| ----- | ------- | ------- | ------------- |
| `stock_id` | Stock of the bar | `104` | Never missing |
| `trading_date` | Session date (ET) | `2026-11-09` | Never missing |
| `open`, `high`, `low`, `close` | Raw session prices, not adjusted | `226.90`, `228.75`, `226.10`, `227.50` | Rejected; the day has no bar, and the chart shows a gap |
| `volume` | Shares traded in the session | `41300000` | Rejected |

#### StockSplit

| Field | Meaning | Example | Missing value |
| ----- | ------- | ------- | ------------- |
| `stock_id` | Stock that split | `104` | Never missing |
| `ex_date` | First session at the split-adjusted price | `2020-08-31` | Rejected |
| `split_from`, `split_to` | Ratio: `split_from` old shares become `split_to` new shares | `1`, `4` | Rejected |

#### TradingDay

| Field | Meaning | Example | Missing value |
| ----- | ------- | ------- | ------------- |
| `trading_date` | Calendar date | `2026-11-27` | Never missing |
| `session` | `full`, `half`, or `closed` | `half` | A date without a row: the server uses Monday-Friday 09:30-16:00 ET and alerts the operator |
| `open_time`, `close_time` | Session times in ET | `09:30`, `13:00` | `null` when `session` is `closed` |

#### SyncRun

| Field | Meaning | Example | Missing value |
| ----- | ------- | ------- | ------------- |
| `sync_run_id` | Run ID | `7c1e...` (UUID) | Never missing |
| `data_set` | `reference`, `latest_prices`, `daily_bars`, `splits`, or `calendar` | `latest_prices` | Never missing |
| `started_at` | Start of the run | `2026-11-10T15:01:00Z` | Never missing |
| `finished_at` | End of the run | `2026-11-10T15:01:06Z` | `null` while the run is active |
| `outcome` | `running`, `succeeded`, `partial`, or `failed` | `partial` | Never missing |
| `accepted_count`, `rejected_count` | Saved and rejected records | `11140`, `12` | `0` |
| `error_code` | Provider failure: `timeout`, `rate_limited`, or `server_error` | `null` | `null` unless `outcome` is `failed` |

#### SyncRejection

| Field | Meaning | Example | Missing value |
| ----- | ------- | ------- | ------------- |
| `sync_run_id` | Run that rejected the record | `7c1e...` | Never missing |
| `symbol` | Symbol as the provider sent it. Not `stock_id`, because the symbol can be unknown. | `XYZW` | `"?"` when the provider sent no symbol |
| `reason` | Lab 3 rule: `unsupported_symbol`, `missing_price`, `non_positive_price`, `missing_provider_time`, `future_provider_time`, or `not_newer` | `missing_price` | Never missing |

#### Watchlist and WatchlistItem

| Field | Meaning | Example | Missing value |
| ----- | ------- | ------- | ------------- |
| `watchlist_id` | Watchlist ID | `9b2d...` (UUID) | Never missing |
| `owner_user_id` | `sub` claim of the owner's access token | `5f0c2b7e-8d4a-4c1e-9b2a-3e6f1d9c7a10` | Never missing; set only from the token, never from the request body |
| `created_at` | Time of the first add | `2026-11-10T15:15:20Z` | Never missing |
| `stock_id` (item) | Followed Stock, a reference into the Market Data Store | `231` | Never missing. A delisted Stock stays on the list with `active: false` (Lab 2). |
| `added_at` (item) | Time the User added the Stock | `2026-11-10T15:15:20Z` | Never missing |

### ER diagram

```mermaid
erDiagram
    EXTERNAL_USER ||--o| WATCHLIST : "owns"
    WATCHLIST ||--o{ WATCHLIST_ITEM : "contains, max 100"
    STOCK ||--o{ WATCHLIST_ITEM : "is followed in (other store)"
    STOCK ||--o| LATEST_PRICE : "has"
    STOCK ||--o{ DAILY_BAR : "has"
    STOCK ||--o{ STOCK_SPLIT : "has"
    TRADING_DAY ||--o{ DAILY_BAR : "dates"
    SYNC_RUN ||--o{ SYNC_REJECTION : "records"

    EXTERNAL_USER {
        id sub PK "token subject, identity provider"
    }
    WATCHLIST {
        id watchlist_id PK
        id owner_user_id UK "token sub"
        time created_at
    }
    WATCHLIST_ITEM {
        id watchlist_id PK, FK
        id stock_id PK, FK "Market Data Store"
        time added_at
    }
    STOCK {
        id stock_id PK
        text symbol UK "unique among listed Stocks"
        text figi
        text name
        enum security_type
        enum exchange
        enum sector
        text industry
        date listed_on
        date delisted_on
        time reference_updated_at
    }
    LATEST_PRICE {
        id stock_id PK, FK
        decimal last_price
        decimal previous_close
        count day_volume
        time provider_time
        time received_at
    }
    DAILY_BAR {
        id stock_id PK, FK
        date trading_date PK, FK
        decimal open
        decimal high
        decimal low
        decimal close
        count volume
    }
    STOCK_SPLIT {
        id stock_id PK, FK
        date ex_date PK
        count split_from
        count split_to
    }
    TRADING_DAY {
        date trading_date PK
        enum session
        time open_time
        time close_time
    }
    SYNC_RUN {
        id sync_run_id PK
        enum data_set
        time started_at
        time finished_at
        enum outcome
        count accepted_count
        count rejected_count
        enum error_code
    }
    SYNC_REJECTION {
        id sync_run_id PK, FK
        text symbol PK
        enum reason
    }
```

**Cardinality and ownership:** A Stock has no LatestPrice until the first accepted price, and then exactly one. A User has no Watchlist until the first add, and then exactly one, with at most 100 items (Mermaid cannot draw the number). The User owns the Watchlist and its items. The Market Data Collector is the only writer of market data and sync records. The Dashboard Application is the only writer of Watchlists. WatchlistItem refers to Stock across two stores, so the server checks the Stock at add time; no store enforces the reference.

### Stored facts and derived values

Stored fields are snake_case and API fields are camelCase; the server maps between them. The Lab 4 cache entries are copies of the values below and do not count as stored facts.

| API field | Derived from | Rule | Why it is not stored |
| --------- | ------------ | ---- | -------------------- |
| `active` | `delisted_on` | `delisted_on is null` | A second field could disagree with `delisted_on` |
| `change` | `last_price`, `previous_close` | `last_price - previous_close` | Changes with every price |
| `changePercent` | `change`, `previous_close` | `change / previous_close x 100`, half-up to 2 decimals | Same |
| `priceState`, `unavailableReason` | `provider_time`, read time, TradingDay, `delisted_on` | Freshness policy below | Changes with the clock, without new data |
| `averageVolume20d` | DailyBar | Mean `volume` of the last 20 bars before today | Changes once per day |
| `relativeVolume` | `day_volume`, `averageVolume20d` | `day_volume / averageVolume20d`, half-up to 2 decimals | Changes with every price |
| Adjusted bar prices | DailyBar, StockSplit | For each split with `ex_date > trading_date`: price x `split_from / split_to`, volume x `split_to / split_from` | A new split would make stored adjusted prices wrong |
| `itemCount` | WatchlistItem | Count of the owner's items | A second count could disagree with the items |
| Overview lists, trending `rank` | Latest prices | Sort rules below | Change with every price |
| `nextCursor` | Last row of the page, filters | Opaque token | Exists only for one response |

### Freshness policy (Lab 2 CON-1, unchanged)

`provider_time` decides freshness; `received_at` never does. Price age = read time - `provider_time`.

| Condition | `priceState` | Price fields |
| --------- | ------------ | ------------ |
| Market hours (TradingDay, ET), age <= 20 min | `delayed` | Set; the UI shows "Delayed, as of HH:MM ET" |
| Market hours, age > 20 min | `unavailable`, reason `stale` | `null` |
| Outside market hours, `provider_time` >= last session `close_time` - 20 min | `at_close` | Set; the UI shows "At close, HH:MM ET" |
| Outside market hours, older price | `unavailable`, reason `stale` | `null` |
| No LatestPrice row | `unavailable`, reason `no_price` | `null` |
| `delisted_on` set | `unavailable`, reason `delisted` | `null` |

### Ranking rules

| List | Eligible Stocks | Order | Size |
| ---- | --------------- | ----- | ---- |
| Trending | Listed; `priceState` is not `unavailable`; 20 daily bars; `averageVolume20d` >= 1,000,000 | `relativeVolume` high to low, then `symbol` A-Z | Up to 50 |
| Overview gainers | Listed; `priceState` is not `unavailable`; `changePercent > 0` | `changePercent` high to low, then `symbol` | 10 |
| Overview losers | Same, `changePercent < 0` | `changePercent` low to high, then `symbol` | 10 |
| Overview most active | Listed; `priceState` is not `unavailable` | `day_volume` high to low, then `symbol` | 10 |

Relative volume finds Stocks that trade much more than usual. Raw volume always puts the same large companies first, and Overview "most active" already shows that list. Early in the session every ratio is low because the day is not complete, but all Stocks are measured at the same point in the day, so the order holds. The 1,000,000-share floor removes thin Stocks where a few trades can double the ratio. Trending is cached like Overview (Lab 4): key `trending:us-market`, `EX 60`.

### Changes to Labs 1-4

| Earlier decision | Lab 5 change |
| ---------------- | ------------ |
| Lab 3: the User Data Store keeps Users; IdentityService reads User records | The User is an external identity. IdentityService verifies the access token; `sub` is the owner ID. |
| Lab 2: the latest price record stores a state | The state is derived at read time, because it changes with the clock |
| Lab 2: History uses daily and 5-minute bars | This lab models daily bars only (brief scope). 5-minute bars stay for a later lab. |
| No Watchlist size limit | A Watchlist holds at most 100 Stocks |

---

## 2. Client endpoints

### Endpoint inventory

Base URL: `https://api.dashboard.example` (example host). Every operation needs `Authorization: Bearer <access token>`.

| Product action | Method and versioned path | Parameters or body | Success | Access rule |
| -------------- | ------------------------- | ------------------ | ------- | ----------- |
| See market overview (Lab 2 Overview) | `GET /v1/market/overview` | None | `200` MarketOverview | Any signed-in User |
| See trending Stocks | `GET /v1/stocks/trending` | `type`, `limit` | `200` TrendingList | Any signed-in User |
| Browse and filter Stocks (Lab 2 Filter) | `GET /v1/stocks` | `type`, `exchange`, `sector`, `limit`, `cursor` | `200` StockPage | Any signed-in User |
| Search by name or symbol (Lab 2 Search) | `GET /v1/stocks` | `q`, plus the filter parameters | `200` StockPage | Any signed-in User |
| Open Stock detail | `GET /v1/stocks/{symbol}` | `symbol` | `200` StockDetail | Any signed-in User |
| Read the latest accepted price (Lab 2 Stock price) | `GET /v1/stocks/{symbol}/price` | `symbol` | `200` StockPrice | Any signed-in User |
| Read daily history (Lab 2 History) | `GET /v1/stocks/{symbol}/history` | `symbol`, `range` | `200` PriceHistory | Any signed-in User |
| Read my Watchlist (Lab 2 Watchlist) | `GET /v1/watchlist/items` | `limit`, `cursor` | `200` WatchlistPage | Owner only, from the token |
| Check whether a Stock is on my Watchlist | `GET /v1/watchlist/items/{symbol}` | `symbol` | `200` WatchlistItem | Owner only, from the token |
| Add a Stock to my Watchlist | `POST /v1/watchlist/items` | Body `{"symbol"}` | `201` WatchlistItem, `Location` header | Owner only, from the token |
| Remove a Stock from my Watchlist | `DELETE /v1/watchlist/items/{symbol}` | `symbol` | `204`, no body | Owner only, from the token |

The Stock detail screen uses the check operation to decide between "Add" and "Remove." Stock price has its own path because the Mobile App polls the price every second (Lab 2) and the price uses a different cache key from reference data (Lab 4).

### Parameters and validation

| Parameter | Used by | Required | Default | Validation |
| --------- | ------- | -------- | ------- | ---------- |
| `symbol` (path or body) | Stock and Watchlist operations | Yes | - | 1-10 characters: a letter, then letters, digits, `.`, or `-`. Case-insensitive; the server uses upper case. |
| `q` | `GET /v1/stocks` | No | No search | 1-50 characters, case-insensitive |
| `type` | `GET /v1/stocks`, trending | No | Stocks and ETFs | `stock` or `etf` |
| `exchange` | `GET /v1/stocks` | No | All | `nasdaq`, `nyse`, `nyse_american`, `nyse_arca`, `cboe_bzx` |
| `sector` | `GET /v1/stocks` | No | All | One of the 11 GICS sectors, for example `information_technology`. ETFs never match. |
| `limit` | Cursor lists and trending | No | 20 | 1-50 |
| `cursor` | Cursor lists | No | First page | `nextCursor` of the previous page, with the same filters |
| `range` | History | No | `1y` | `1m`, `3m`, `6m`, `ytd`, `1y`, `5y` |

The body of `POST /v1/watchlist/items` accepts only `symbol`. The input model has no owner ID and none of the server-controlled fields (`addedAt`, `active`, `quote`, `itemCount`), so a body that sends one gets `400 unknown_field`. An empty or unsupported parameter value returns `400`. The server ignores unknown query parameters.

### Error shape and statuses

```json
{
  "error": {
    "code": "invalid_type",
    "message": "type: Input should be 'stock' or 'etf'"
  }
}
```

| Status | Meaning | Codes |
| ------ | ------- | ----- |
| `400` | Invalid input | `invalid_json`, `missing_field`, `unknown_field`, `invalid_symbol`, `invalid_query`, `invalid_type`, `invalid_exchange`, `invalid_sector`, `invalid_limit`, `invalid_cursor`, `invalid_range`, `unsupported_symbol`, `stock_delisted` |
| `401` | Missing, invalid, or expired token | `authentication_required` |
| `404` | No such Stock, or the Stock is not on the caller's Watchlist | `stock_not_found`, `not_on_watchlist` |
| `409` | The add conflicts with the Watchlist state | `already_on_watchlist`, `watchlist_full` |
| `429` | Rate limit reached; `Retry-After` header | `rate_limited` |
| `503` | A store is unavailable, or CON-2 cannot be guaranteed | `market_data_unavailable`, `watchlist_unavailable` |

A stale or missing price is not an error: `GET /v1/stocks/{symbol}/price` returns `200` with `priceState: unavailable`. A `503` means the server could not read the store at all.

| Operation | Errors |
| --------- | ------ |
| `GET /v1/market/overview` | 401, 429, 503 |
| `GET /v1/stocks` | 400 (`invalid_query`, `invalid_type`, `invalid_exchange`, `invalid_sector`, `invalid_limit`, `invalid_cursor`), 401, 429, 503 |
| `GET /v1/stocks/trending` | 400 (`invalid_type`, `invalid_limit`), 401, 429, 503 |
| `GET /v1/stocks/{symbol}`, `.../price` | 400 (`invalid_symbol`), 401, 404 (`stock_not_found`), 429, 503 |
| `GET /v1/stocks/{symbol}/history` | 400 (`invalid_symbol`, `invalid_range`), 401, 404 (`stock_not_found`), 429, 503 |
| `GET /v1/watchlist/items` | 400 (`invalid_limit`, `invalid_cursor`), 401, 429, 503 |
| `GET /v1/watchlist/items/{symbol}` | 400 (`invalid_symbol`), 401, 404 (`not_on_watchlist`), 429, 503 |
| `POST /v1/watchlist/items` | 400 (`invalid_json`, `missing_field`, `unknown_field`, `invalid_symbol`, `unsupported_symbol`, `stock_delisted`), 401, 409, 429, 503 |
| `DELETE /v1/watchlist/items/{symbol}` | 400 (`invalid_symbol`), 401, 404 (`not_on_watchlist`), 429, 503 |

### Response models

The examples are responses from the stub API (Section 3), whose clock starts at 2026-11-10 15:15:20Z (10:15:20 ET, inside market hours). Stock detail, price, and history examples are in Section 4.

#### Quote

Every market-data row carries a Quote:

```json
{
  "price": "229.35",
  "previousClose": "227.50",
  "change": "1.85",
  "changePercent": "0.81",
  "dayVolume": 18400000,
  "currency": "USD",
  "priceState": "delayed",
  "unavailableReason": null,
  "providerTime": "2026-11-10T15:00:00Z"
}
```

SOFI has a 35-minute-old price, so `GET /v1/stocks/SOFI/price` returns no price:

```json
{
  "symbol": "SOFI",
  "quote": {
    "price": null, "previousClose": null, "change": null, "changePercent": null,
    "dayVolume": null, "currency": "USD", "priceState": "unavailable",
    "unavailableReason": "stale", "providerTime": "2026-11-10T14:40:00Z"
  }
}
```

#### Market overview

`GET /v1/market/overview`, shortened to one row per list (the stub returns up to 10):

```json
{
  "market": "US",
  "gainers": [
    { "symbol": "PLTR", "name": "Palantir Technologies Inc. - Class A Common Stock",
      "quote": { "price": "182.40", "previousClose": "171.25", "change": "11.15", "changePercent": "6.51",
                 "dayVolume": 96900000, "currency": "USD", "priceState": "delayed",
                 "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z" } }
  ],
  "losers": [
    { "symbol": "INTC", "name": "Intel Corporation - Common Stock",
      "quote": { "price": "22.40", "previousClose": "23.14", "change": "-0.74", "changePercent": "-3.20",
                 "dayVolume": 61800000, "currency": "USD", "priceState": "delayed",
                 "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z" } }
  ],
  "mostActive": [
    { "symbol": "NVDA", "name": "NVIDIA Corporation - Common Stock",
      "quote": { "price": "141.20", "previousClose": "135.64", "change": "5.56", "changePercent": "4.10",
                 "dayVolume": 98500000, "currency": "USD", "priceState": "delayed",
                 "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z" } }
  ],
  "builtAt": "2026-11-10T15:15:29Z"
}
```

#### Filtered page

`GET /v1/stocks?type=stock&sector=information_technology&limit=2`. Without `q`, the order is `symbol` A-Z. Filters are applied before `limit`.

```json
{
  "items": [
    { "symbol": "AAPL", "name": "Apple Inc. - Common Stock", "type": "stock", "exchange": "nasdaq",
      "sector": "information_technology", "active": true,
      "quote": { "price": "229.35", "previousClose": "227.50", "change": "1.85", "changePercent": "0.81",
                 "dayVolume": 18400000, "currency": "USD", "priceState": "delayed",
                 "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z" } },
    { "symbol": "INTC", "name": "Intel Corporation - Common Stock", "type": "stock", "exchange": "nasdaq",
      "sector": "information_technology", "active": true,
      "quote": { "price": "22.40", "previousClose": "23.14", "change": "-0.74", "changePercent": "-3.20",
                 "dayVolume": 61800000, "currency": "USD", "priceState": "delayed",
                 "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z" } }
  ],
  "nextCursor": "eyJhZnRlciI6IFswLCAiSU5UQyJdLCAiZiI6ICJlNGNmNjVmMWVkZDQifQ"
}
```

The same request plus `&cursor=eyJhZnRl...` returns the next page, MSFT and NVDA. The same cursor with `type=etf` returns `400 invalid_cursor`.

#### Search

With `q`, the order is: exact symbol, symbol prefix, word prefix in the name, text in the name; `symbol` A-Z in each group. `GET /v1/stocks?q=so` returns SOFI (symbol prefix), then MSFT ("MicroSOft"). Delisted Stocks are not in the list; their detail path still works.

#### Empty result

`GET /v1/stocks?q=zzzz` returns `200`:

```json
{ "items": [], "nextCursor": null }
```

#### Trending

`GET /v1/stocks/trending?limit=2`. The list is the complete result, with no next page.

```json
{
  "items": [
    { "rank": 1, "symbol": "PLTR", "name": "Palantir Technologies Inc. - Class A Common Stock", "type": "stock",
      "relativeVolume": "2.16", "averageVolume20d": 44800000,
      "quote": { "price": "182.40", "previousClose": "171.25", "change": "11.15", "changePercent": "6.51",
                 "dayVolume": 96900000, "currency": "USD", "priceState": "delayed",
                 "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z" } },
    { "rank": 2, "symbol": "INTC", "name": "Intel Corporation - Common Stock", "type": "stock",
      "relativeVolume": "0.86", "averageVolume20d": 71500000,
      "quote": { "price": "22.40", "previousClose": "23.14", "change": "-0.74", "changePercent": "-3.20",
                 "dayVolume": 61800000, "currency": "USD", "priceState": "delayed",
                 "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z" } }
  ],
  "rankedAt": "2026-11-10T15:15:20Z"
}
```

SOFI has a relative volume of 0.50 but a stale price, so SOFI is not ranked.

#### Watchlist page

`GET /v1/watchlist/items?limit=20`. The order is newest `addedAt` first, then `symbol`. `itemCount` counts the whole Watchlist, not the page.

```json
{
  "items": [
    { "symbol": "SOFI", "name": "SoFi Technologies, Inc. - Common Stock", "active": true,
      "addedAt": "2026-11-10T15:15:29Z",
      "quote": { "price": null, "previousClose": null, "change": null, "changePercent": null,
                 "dayVolume": null, "currency": "USD", "priceState": "unavailable",
                 "unavailableReason": "stale", "providerTime": "2026-11-10T14:40:00Z" } },
    { "symbol": "PLTR", "name": "Palantir Technologies Inc. - Class A Common Stock", "active": true,
      "addedAt": "2026-11-10T15:15:20Z",
      "quote": { "price": "182.40", "previousClose": "171.25", "change": "11.15", "changePercent": "6.51",
                 "dayVolume": 96900000, "currency": "USD", "priceState": "delayed",
                 "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z" } }
  ],
  "itemCount": 2,
  "capacity": 100,
  "nextCursor": null
}
```

A User with no Watchlist yet gets `200` with `"items": []`, `"itemCount": 0`, `"nextCursor": null`.

#### Add and remove

The Lab 3 rules still apply. The API reports success only after the User Data Store confirms the write, and it rejects a duplicate add or the removal of a Stock that is not on the list.

| Request | Result |
| ------- | ------ |
| `POST /v1/watchlist/items` `{"symbol": "pltr"}` | `201`, `Location: /v1/watchlist/items/PLTR`, WatchlistItem |
| Same request again | `409 already_on_watchlist` |
| `{"symbol": "SOFI", "userId": "x"}` | `400 unknown_field` |
| `{"symbol": "ABCD"}` | `400 unsupported_symbol` |
| Add number 101 | `409 watchlist_full` |
| `DELETE /v1/watchlist/items/sofi` | `204` |
| Same request again | `404 not_on_watchlist` |

After an unknown outcome (timeout), the client reads the item before it repeats the change. A `404 not_on_watchlist` on a repeated `DELETE` means the first `DELETE` succeeded.

### Shared API policies

1. **Version.** The major version is in the path: `/v1`. Compatible change: add an optional response field, for example `marketCap` in StockDetail; clients ignore unknown fields. Breaking change: change `price` from a decimal string to a JSON number. That change needs `/v2`, while `/v1` stays available until measured `/v1` use stops. A new `priceState` value needs a documented fallback; clients treat an unknown value as `unavailable`.
2. **Authentication.** OAuth 2.0 / OIDC access token (JWT) from the external identity provider, sent as `Authorization: Bearer`. IdentityService checks the signature, issuer, audience, and expiry on every request. The API has no sign-in endpoints. Every Watchlist operation selects the Watchlist by the token `sub` only. Another User's item gives the same `404` as a missing item, so the API does not show that it exists. Watchlist responses have `Cache-Control: no-store`.
3. **Pagination and rate limits.**
   - Cursor lists (`/v1/stocks`, `/v1/watchlist/items`): `limit` 1-50, default 20. Each list has a stable order with a tie-breaker. Filters are applied before `limit`. `nextCursor: null` means the end. An empty list is `200`. A cursor is valid only with the filters that made it; other filters return `400 invalid_cursor`. Ownership is checked on every page.
   - Bounded lists have no cursor: trending (max 50) and history (max 5 years, about 1,260 bars).
   - Rate limits per User (token `sub`): 10 market-data requests per second (the Mobile App needs about 1 per second, Lab 2) and 30 Watchlist changes per minute. Above the limit the API returns `429` and `Retry-After` in seconds.
   - Client handling of `429`: wait for `Retry-After`, and send no other request to the same operation during the wait. Without the header, wait 1 s, 2 s, 4 s, up to 30 s, with random jitter. Stop price polling during the wait. The UI keeps the last price only while its label is still valid (`providerTime` + 20 min). After that time, the UI shows "Price unavailable." A `POST` after `429` is safe to repeat, because the server did not process the first one.

### Market Data Collector integrations

The Collector is a server process that calls the Market Data Provider with server credentials; the Mobile App never calls these integrations. The Lab 3 retry rules apply: up to 2 retries 3 s apart after a timeout or server error, and no immediate retry after a rate limit. Each run writes one SyncRun, plus one SyncRejection per rejected record. The Lab 4 Redis and L1 copies have no client endpoints either.

| Integration | Trigger | Collector requests | Writes |
| ----------- | ------- | ------------------ | ------ |
| Reference data | Daily, 06:00 ET | Supported symbol list with reference fields | Stock: insert, update, set `delisted_on` |
| Latest prices | Every 1 min in market hours (TradingDay) | Snapshots of all supported Stocks, in batches | LatestPrice, only if `provider_time` is newer |
| Daily bars | After the close | The session bar of each Stock | DailyBar |
| Splits | Daily | Splits with an ex-date | StockSplit |
| Calendar | Yearly | Trading calendar for the next year | TradingDay |

---

## 3. OpenAPI generation

### Source and dependencies

| File | Content |
| ---- | ------- |
| [`api/app/models.py`](./api/app/models.py) | Request and response models, enums, field validation, and field examples (Pydantic) |
| [`api/app/main.py`](./api/app/main.py) | Routes, parameter validation, the error handlers, bearer authentication, response examples, and stub handlers |
| [`api/app/stub_data.py`](./api/app/stub_data.py) | Stub in-memory facts in place of the two stores, with a fixed start time |
| [`api/export_openapi.py`](./api/export_openapi.py) | Writes the generated document to `openapi.yaml` |
| [`api/pyproject.toml`](./api/pyproject.toml), [`api/uv.lock`](./api/uv.lock) | Dependencies: Python 3.12, FastAPI 0.163.2, Pydantic 2.14.3, Uvicorn 0.54.0, PyYAML 6.0.3 |
| [`api/openapi.yaml`](./api/openapi.yaml) | Generated OpenAPI 3.1.0 document; do not edit by hand |

The stub handlers read `stub_data.py`, accept any bearer token, and use the token value as the User ID. The derived values (`change`, `changePercent`, `priceState`, `relativeVolume`, `itemCount`) follow the Section 1 rules with two simplifications: market hours are fixed at Monday-Friday 09:30-16:00 EST instead of coming from TradingDay, and trending does not check for 20 daily bars. The stub does not enforce rate limits; they exist only in the contract.

```bash
cd SD/lab-5/api
uv sync                                      # install the locked dependencies
uv run python export_openapi.py              # generate openapi.yaml
uv run uvicorn app.main:app --port 8811      # stub API; Swagger UI at http://localhost:8811/docs
npx @redocly/cli lint openapi.yaml           # check the generated document
```

### Mismatches fixed in the source

| Mismatch in the generated document | Fix in the source |
| ---------------------------------- | ----------------- |
| FastAPI adds a `422` response to every operation; this API uses `400` | A validation handler returns `400` in the shared error shape; `custom_openapi()` removes the `422` entries and their schemas |
| FastAPI removed every `null` from the examples, so `nextCursor` and the stale quote did not match their schemas (11 lint warnings) | `custom_openapi()` puts the exact list examples back; 0 example warnings after regeneration |
| The filtered-page example had a cursor that the stub API did not produce | The example now uses the cursor from the real response |

### Check record (2026-11-18)

| Check | Result |
| ----- | ------ |
| Redocly CLI lint of `openapi.yaml` | Valid. 2 warnings, accepted: `info-license` (course API, no license) and `no-server-example.com` (example host, intended). |
| Inventory vs generated document | 10 of 10 operations, same methods and paths. `bearerAuth` (HTTP bearer, JWT) on every operation. |
| Served `/openapi.json` vs `openapi.yaml` | Same content |
| Examples in the viewer | `listStocks` 200 has `filtered` and `empty`; `listWatchlistItems` 200 has `page` and `empty`; every error response has an example per code |
| Filtered page on the stub | `200` with 2 items and `nextCursor`; the next page returns MSFT and NVDA |
| Old cursor with other filters | `400 invalid_cursor` |
| Empty search `q=zzzz` | `200`, `{"items": [], "nextCursor": null}` |
| `type=bond`, `limit=500`, `range=2y` | `400 invalid_type`, `invalid_limit`, `invalid_range` |
| No token | `401 authentication_required` |
| Another User reads and deletes | Empty Watchlist, and `DELETE /v1/watchlist/items/PLTR` returns `404`; the owner's item stays |

[Screenshot: Swagger UI at /docs, operation list with the two tags]

[Screenshot: Swagger UI, GET /v1/stocks 200 response with the "filtered" and "empty" examples]

[Screenshot: Swagger UI, POST /v1/watchlist/items 400 and 409 error examples]

---

## 4. Client flow

```text
Open trending Stocks -> open one Stock for more market data -> add it to Watchlist
```

Every request goes to `https://api.dashboard.example` with `Authorization: Bearer <access token>` and `Accept: application/json`.

| Order | Screen | Request | Result in this flow |
| ----- | ------ | ------- | ------------------- |
| 1 | Trending | `GET /v1/stocks/trending?limit=20` | `200`, PLTR is rank 1 |
| 2 | Stock detail | `GET /v1/stocks/PLTR` | `200`, reference data |
| 3 | Stock detail | `GET /v1/stocks/PLTR/price`, then every 1 s while the screen is open | `200`, `delayed` |
| 4 | Stock detail | `GET /v1/stocks/PLTR/history?range=3m` | `200`, daily bars |
| 5 | Stock detail | `GET /v1/watchlist/items/PLTR` | `404 not_on_watchlist`, the button shows "Add to Watchlist" |
| 6 | Stock detail | `POST /v1/watchlist/items` | `201`, the button shows "On Watchlist" |

Requests 2-5 start together when the User opens the Stock. Each part of the screen has its own state, so a slow history request does not hold back the price.

#### 1. Trending

The response is the trending example in Section 2.

```http
GET /v1/stocks/trending?limit=20 HTTP/1.1
Host: api.dashboard.example
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

#### 2. Stock detail

```http
GET /v1/stocks/PLTR HTTP/1.1
```

```json
{
  "symbol": "PLTR",
  "name": "Palantir Technologies Inc. - Class A Common Stock",
  "type": "stock",
  "exchange": "nasdaq",
  "sector": "information_technology",
  "industry": "Software",
  "active": true,
  "listedOn": "2020-09-30",
  "delistedOn": null
}
```

#### 3. Price

```http
GET /v1/stocks/PLTR/price HTTP/1.1
```

```json
{
  "symbol": "PLTR",
  "quote": {
    "price": "182.40", "previousClose": "171.25", "change": "11.15", "changePercent": "6.51",
    "dayVolume": 96900000, "currency": "USD", "priceState": "delayed",
    "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z"
  }
}
```

#### 4. History

Prices are split-adjusted. The stub stores bars only for AAPL (three of them), so the example uses AAPL; PLTR gets the same response shape.

```http
GET /v1/stocks/AAPL/history?range=1m HTTP/1.1
```

```json
{
  "symbol": "AAPL",
  "range": "1m",
  "adjusted": true,
  "currency": "USD",
  "bars": [
    { "date": "2026-11-05", "open": "226.10", "high": "228.40", "low": "225.30", "close": "227.90", "volume": 48200000 },
    { "date": "2026-11-06", "open": "227.80", "high": "229.10", "low": "226.20", "close": "226.85", "volume": 45900000 },
    { "date": "2026-11-09", "open": "226.90", "high": "228.75", "low": "226.10", "close": "227.50", "volume": 41300000 }
  ]
}
```

#### 5. Watchlist check

```http
GET /v1/watchlist/items/PLTR HTTP/1.1
```

```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{"error": {"code": "not_on_watchlist", "message": "PLTR is not on your Watchlist"}}
```

#### 6. Add

```http
POST /v1/watchlist/items HTTP/1.1
Content-Type: application/json

{"symbol": "PLTR"}
```

```http
HTTP/1.1 201 Created
Location: /v1/watchlist/items/PLTR
Cache-Control: no-store
Content-Type: application/json

{"symbol": "PLTR", "name": "Palantir Technologies Inc. - Class A Common Stock", "active": true,
 "addedAt": "2026-11-10T15:15:20Z",
 "quote": {"price": "182.40", "previousClose": "171.25", "change": "11.15", "changePercent": "6.51",
           "dayVolume": 96900000, "currency": "USD", "priceState": "delayed",
           "unavailableReason": null, "providerTime": "2026-11-10T15:00:00Z"}}
```

### UI states

On every screen, `401` shows "Session expired, sign in again." If a part gets no result within 2 s, that part shows its "retry" message (Lab 2 LAT-3), and the User decides when to retry.

| Part | Loading | Success | Empty | Failure |
| ---- | ------- | ------- | ----- | ------- |
| Trending list | Placeholder rows | Ranked rows: symbol, name, price with its label, relative volume | "No trending Stocks now," for example before the first sync of the day | `429`: keep the list, wait for `Retry-After`. `503`, network error, or 2 s: "Trending unavailable, retry." |
| Stock header (request 2) | Placeholder name | Name, exchange, sector; "Delisted" when `active` is false | - | `404`: "Not supported." Other errors: "Stock unavailable, retry." |
| Price (request 3) | Placeholder for the price only | "$182.40, Delayed, as of 10:00 ET," or "At close, 16:00 ET" | `priceState: unavailable`: "Price unavailable," never the old price | "Price unavailable, retry." The poll continues after `Retry-After` on `429`. |
| History (request 4) | Empty chart frame | Daily chart for the range | `bars: []`: "No history yet" | "History unavailable, retry." Price and header stay on screen. |
| Watchlist button (request 5) | Disabled button | `200`: "On Watchlist" (tap removes). `404 not_on_watchlist`: "Add to Watchlist." | - | Button disabled, "Watchlist status unavailable" |
| Add (request 6) | Spinner on the button; the UI does not show "Added" before the response | `201`: "On Watchlist" | - | `409 already_on_watchlist`: "On Watchlist." `409 watchlist_full`: "Watchlist full (100)." `503`: "Can't update Watchlist now, try again." No reply: "Couldn't confirm, refresh to check" (Lab 3). |
