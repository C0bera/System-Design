# Lab 3: Personal Investment Dashboard - Baseline Architecture

Scope: the Lab 3 given behavior (browse and filter Stocks, read prices and history, manage a private Watchlist) with the Lab 2 load targets. The Brokerage from Lab 1 stays in the views; none of the three flows uses it.

---

## 1. System Context diagram

```mermaid
flowchart LR
    user["User<br/>[Person]"]
    dashboard["Personal Investment Dashboard<br/>[Software System]<br/>Shows delayed Stock prices, history, and a private Watchlist"]
    provider["Market Data Provider<br/>[External System]"]
    brokerage["Brokerage<br/>[External System]"]

    user -->|"Browses and filters Stocks, reads prices and history, manages private Watchlist, connects broker accounts"| dashboard
    user -.->|"Authorizes read access"| brokerage
    dashboard -->|"Requests Stock reference data, delayed prices, and history"| provider
    provider -->|"Returns data with provider time, or invalid data, rate limit, or outage"| dashboard
    dashboard -->|"Requests read-only holdings for an authorized account"| brokerage
    brokerage -->|"Returns holdings, or access denied / unavailable"| dashboard
```

---

## 2. Container diagram

| Container | Responsibility |
| --------- | -------------- |
| Mobile App | Shows Stocks, prices, history, and the Watchlist to the User |
| Dashboard Application | Answers every User request from stored data |
| Market Data Collector | Syncs market data from the provider; holds the provider credentials |
| Market Data Store | Keeps accepted market data and the sync record |
| User Data Store | Keeps Users, Watchlists, broker connections, and imported holdings |

```mermaid
flowchart LR
    user["User<br/>[Person]"]
    provider["Market Data Provider<br/>[External System]"]
    brokerage["Brokerage<br/>[External System]"]

    subgraph dashboard["Personal Investment Dashboard"]
        mobile["Mobile App"]
        app["Dashboard Application"]
        collector["Market Data Collector"]
        marketStore[("Market Data Store")]
        userStore[("User Data Store")]

        mobile -->|"Sends User requests"| app
        app -->|"Reads accepted market data"| marketStore
        app -->|"Reads and writes Watchlists and broker holdings"| userStore
        collector -->|"Writes validated data and sync record"| marketStore
    end

    user -->|"Browses Stocks, manages Watchlist, connects broker accounts"| mobile
    user -.->|"Authorizes read access"| brokerage
    collector --->|"Requests market data with server credentials"| provider
    app -->|"Requests read-only holdings with the User's token"| brokerage
```

**Design choices:** User reads never call the provider. The Stock price read is 6,000 of 7,920 steady RPS, while the provider updates about once per minute, so reads use stored data and do not spend provider quota or inherit provider latency and outages. The Market Data Collector is a separate application so a failing or rate-limited sync cannot stop reads, and read load cannot delay sync. Stores are grouped by related data: public market data written only by the Collector, and private User data written only by the Dashboard Application. The Mobile App calls the Dashboard Application directly; with one client and one backend there is nothing to route.

---

## 3. Component diagram

| Dashboard Application component | Responsibility |
| ------------------------------- | -------------- |
| IdentityService | Verifies the User's token on every request and passes the verified User ID on |
| StockService | Checks Stock requests, reads Stocks, prices, and history, applies the 20-minute freshness rule, and changes the User's own Watchlist |
| WealthService | Calculates holding value as price x quantity, using labeled prices from StockService |
| BrokerImportService | Requests holdings from the Brokerage with the User's token and saves them |

```mermaid
flowchart LR
    mobile["Mobile App"]
    marketStore[("Market Data Store")]
    userStore[("User Data Store")]
    brokerage["Brokerage<br/>[External System]"]

    subgraph app["Dashboard Application"]
        identity["IdentityService"]
        stock["StockService"]
        wealth["WealthService"]
        broker["BrokerImportService"]

        identity -->|"Passes Stock and Watchlist requests with verified User ID"| stock
        identity -->|"Passes wealth requests with verified User ID"| wealth
        identity -->|"Passes broker requests with verified User ID"| broker
        wealth -->|"Requests labeled prices"| stock
    end

    mobile -->|"Sends all requests with token"| identity
    identity -->|"Reads User records"| userStore
    stock -->|"Reads Stocks, prices, and history"| marketStore
    stock -->|"Reads and writes the User's Watchlist"| userStore
    wealth -->|"Reads the User's holdings"| userStore
    broker -->|"Requests read-only holdings with the User's token"| brokerage
    broker -->|"Writes imported holdings"| userStore
```

**Access checks:** IdentityService checks identity on every request, not only at sign-in. StockService checks Watchlist ownership before any read or write: it selects the Watchlist only by the verified User ID, and anything else is denied. The Market Data Collector is not shown because it never talks to the Dashboard Application, only to the Market Data Store.

---

## 4. Sequence diagrams

Results return to the Mobile App through IdentityService; the return arrows are drawn directly to keep the diagrams readable.

### A. Sync market data

```mermaid
sequenceDiagram
    participant Collector as Market Data Collector
    participant Provider as Market Data Provider
    participant Store as Market Data Store

    Note over Collector: Cron trigger every 1 min in market hours, skipped if the previous run is still active
    Collector->>Store: Record sync attempt
    Collector->>Provider: Request latest prices with server credentials
    alt Provider returns data
        Provider-->>Collector: Records with provider times
        Collector->>Collector: Validate each record
        Note over Collector: Reject unsupported symbol, missing or non-positive price, missing or future provider time
        Collector->>Store: Save valid records only if provider time is newer, plus failed symbols and last success
        alt Write confirmed
            Store-->>Collector: Saved
            Note over Store: Accepted prices are now available to later reads
        else Write fails
            Store-->>Collector: Write failed
            Note over Collector: Nothing new is available, the next run tries again
        end
    else Provider times out or returns a server error
        Collector->>Provider: Retry up to 2 times, 3 s apart
        Note over Collector: A successful retry continues as above, otherwise the run ends
    else Provider rate-limits
        Provider-->>Collector: Rate limit, optional Retry-After
        Note over Collector: No immediate retry, next attempt after Retry-After or at the next run
    end
    Note over Store: On any failure, previously accepted prices stay unchanged
```

**Assumptions:**

- The Collector is the only process that syncs, and the supported Stock list is already stored.
- One run requests the latest prices of all supported Stocks; provider paging is not shown.
- Provider credentials stay in the Collector's server environment and never reach the Mobile App.
- Failed symbols are requested again in the next run. When a sync fails, previously accepted prices are kept, and reads label them by Lab 2 CON-1: "Delayed" up to 20 minutes of age, then "Price unavailable."

### B. Read a Stock price

```mermaid
sequenceDiagram
    actor User
    participant Mobile as Mobile App
    participant Identity as IdentityService
    participant Stock as StockService
    participant Store as Market Data Store

    User->>Mobile: Open a Stock
    Mobile->>Identity: Request Stock price with token
    alt Token invalid or expired
        Identity-->>Mobile: Rejected
        Mobile-->>User: Session expired, sign in again
    else Token valid
        Identity->>Stock: Request price with verified User ID
        Stock->>Store: Read Stock and latest price with provider time
        alt Store fails or does not reply in time
            Store-->>Stock: Read failed
            Stock-->>Mobile: Price unavailable
            Mobile-->>User: Price unavailable, retry
        else Symbol unknown or unsupported
            Store-->>Stock: No supported Stock
            Stock-->>Mobile: Rejected input
            Mobile-->>User: Not supported
        else No price stored
            Store-->>Stock: Stock without price
            Stock-->>Mobile: Price unavailable
            Mobile-->>User: Price unavailable
        else Price found
            Store-->>Stock: Price and provider time
            alt Market hours, price age up to 20 min
                Stock-->>Mobile: Price, delayed
                Mobile-->>User: $X, Delayed, as of HH:MM ET
            else Market hours, price age over 20 min
                Stock-->>Mobile: Price unavailable
                Mobile-->>User: Price unavailable
            else Outside market hours
                Stock-->>Mobile: Close price
                Mobile-->>User: $X, At close, HH:MM ET
            end
        end
    end
```

**Assumptions:**

- The User is signed in on the Mobile App, and at least one sync has run.
- A User read needs no new provider request: StockService reads only the Market Data Store.
- Price age = read time - provider time, and market hours are as defined in Lab 2.
- If no result arrives within 2 s, the Mobile App stops waiting and shows "Price unavailable, retry" (Lab 2 LAT-3). The User decides when to retry.

### C. Change a private Watchlist

```mermaid
sequenceDiagram
    actor User
    participant Mobile as Mobile App
    participant Identity as IdentityService
    participant Stock as StockService
    participant Store as User Data Store

    User->>Mobile: Add or remove a Stock
    Mobile->>Identity: Watchlist change with token
    alt Token missing, invalid, or expired
        Identity-->>Mobile: Rejected, no change made
        Mobile-->>User: Session expired, sign in again
    else Token valid
        Identity->>Stock: Change with verified User ID
        Note over Stock: Selects the Watchlist only by verified User ID, a User ID sent by the client is ignored
        alt Symbol unsupported
            Stock-->>Mobile: Rejected input
            Mobile-->>User: Not supported
        else Symbol supported
            Stock->>Store: Apply change to this User's Watchlist
            alt Change stored
                Store-->>Stock: Change confirmed
                Note over Stock,Store: Success point
                Stock-->>Mobile: Change accepted
                Mobile-->>User: Added or Removed
            else Stock already on the list, or not on it
                Store-->>Stock: Nothing to change
                Stock-->>Mobile: Rejected input
                Mobile-->>User: Already on Watchlist, or Not on Watchlist
            else Write fails
                Store-->>Stock: Write failed
                Stock-->>Mobile: Change failed
                Mobile-->>User: Can't update Watchlist now, try again, item shown in red
            else No reply in time
                Stock-->>Mobile: Outcome unknown
                Mobile-->>User: Couldn't confirm, refresh to check
            end
        end
    end
```

**Assumptions:**

- Each User has one Watchlist. StockService checks the symbol against the stored Stock list.
- Because the Watchlist is selected only by the verified User ID, a request cannot address another User's Watchlist; an unauthorized attempt is rejected by IdentityService.
- Success is reported only after the User Data Store confirms the change. On a failed write the list stays as last confirmed, and the failed item is shown in semi-transparent red.
- **Next read (Lab 2 CON-2):** after "Added" or "Removed," every later Watchlist read by the same User, from any device, includes the change. If that cannot be guaranteed, the read shows "Watchlist unavailable" instead of the old list.
