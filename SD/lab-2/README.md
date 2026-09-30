# Lab 2: Personal Investment Dashboard - Quality and Estimates

Scope: the reviewed read set from the Lab 2 brief (Overview, Filter, Stock price, History, Watchlist, Search). The Lab 1 portfolio reads are not part of this lab.

---

## 1. Quality requirements

**Definitions**

- **Market hours:** NYSE regular session, Monday to Friday, 09:30-16:00 ET on trading days (until 13:00 ET on half-days). **Rest of the day:** all other time.
- **Correct read:** the requested data, where every price shows its provider time and state ("delayed," "at close," or "unavailable"). An "unavailable" result is never a correct read, even when it is fast.

### Read latency

Measured on the Client, from sending the request until the result is shown on screen.

| ID | Measure + target | Operating condition |
| -- | ---------------- | ------------------- |
| LAT-1 | p95 latency <= 2 s, per read type | Market hours, up to the market-open target workload (section 3), over 30 days |
| LAT-2 | Stock price p95 latency <= 1 s ("feel immediate") | Same as LAT-1 |
| LAT-3 | At 2 s the Client stops waiting and shows "unavailable, retry." The read counts as over the limit and as a failed availability check. | Any time |

A fast "unavailable" result can meet latency but still fails availability and consistency.

### Availability

A minute is **usable** if an external check, run once per minute, gets a correct read within 2 s from all six reads. Each window is measured separately over 30 days, assumed to contain 21 trading days.

```text
downtime budget = measured time x (1 - target)
```

| Window | Measured time in 30 days | Target | Downtime budget |
| ------ | ------------------------ | ------ | --------------- |
| Market hours | 21 x 6.5 h = 136.5 h | **99.9%** | 136.5 h x 0.001 = 0.1365 h = **8 min 11 s** |
| Rest of the day | 720 h - 136.5 h = 583.5 h | **99%** | 583.5 h x 0.01 = 5.835 h = **5 h 50 min** |

**Why different targets:** during market hours prices change, the market-open burst happens, and most Users are active. Outside them prices are frozen at the close, so an outage only delays reading. 99.99% (about 49 s per 30 days) is not justified for a read-only dashboard that does not trade.

### Consistency

- **CON-1, Stock price:** price age = read time - provider time. During market hours, a price with age <= 20 min (15 min provider delay + 5 min sync slack) is shown as "Delayed, as of HH:MM ET." Above 20 min, 100% of reads show **"Price unavailable,"** never the old price as current. Outside market hours the close price is shown as "At close." A missing price is never shown as zero.
- **CON-2, Watchlist:** after a confirmed add or remove, every later Watchlist read by the same User, from any device, includes the change. If that cannot be guaranteed, the read returns "Watchlist unavailable" instead of the old list.

### Throughput

| Operating condition | Target: acceptable completed reads per second (300 / 3,000 / 30,000 Users) |
| ------------------- | -------------------------------------------------------------------------- |
| Market hours, steady mix (section 2) | 79.2 / 792 / 7,920 |
| 10-second market-open window (section 3) | 103 / 1,030 / 10,296 |

A read is acceptable only if it is correct and meets the latency and consistency targets.

---

## 2. Steady RPS estimates

```text
RPS = concurrent Users (N) x participating share x actions per User / seconds
```

Each User action creates one Dashboard request. Provider traffic is not included. All results are in RPS, unrounded.

| Read | Calculation | 300 Users | 3,000 Users | 30,000 Users |
| ---- | ----------- | --------- | ----------- | ------------ |
| Overview | N x 0.70 x 1 / 30 s | 7 | 70 | 700 |
| Filter | N x 0.50 x 3 / 60 s | 7.5 | 75 | 750 |
| Stock price | N x 0.20 x 1 / 1 s | 60 | 600 | 6,000 |
| History | N x 0.20 x 1 / 300 s | 0.2 | 2 | 20 |
| Watchlist | N x 0.60 x 1 / 60 s | 3 | 30 | 300 |
| Search | N x 0.10 x 3 / 60 s | 1.5 | 15 | 150 |
| **Steady total** | sum of the rows | **79.2** | **792** | **7,920** |

The Stock price read is 75.8% of steady traffic at every scale.

---

## 3. Market-open RPS estimates

```text
additional Overview  = N x 0.30 x 1 / 10 s
additional Watchlist = N x 0.30 x 0.60 x 1 / 10 s
```

The steady Overview and Watchlist traffic is already in the steady total and is not counted again.

| Market-open calculation | 300 Users | 3,000 Users | 30,000 Users |
| ----------------------- | --------- | ----------- | ------------ |
| Steady read traffic | 79.2 | 792 | 7,920 |
| Additional Overview refresh flow | 9 | 90 | 900 |
| Additional Watchlist refresh flow | 5.4 | 54 | 540 |
| **Market-open subtotal** | **93.6** | **936** | **9,360** |
| 10% capacity margin | 9.36 | 93.6 | 936 |
| **Rounded-up market-open target** | 102.96 -> **103 RPS** | 1,029.6 -> **1,030 RPS** | **10,296 RPS** |

---

## 4. Storage estimates

### What is a Stock

Market-data symbol lists call anything with a ticker a "stock" (preferred shares, ADRs, funds, warrants), so the term needs a definition.

| Term | Definition | Source (observed 2026-09-29) |
| ---- | ---------- | ---------------------------- |
| Stock | "A type of security that gives stockholders a share of ownership in a company"; common stock carries voting rights, preferred stock usually does not. | [Investor.gov (SEC), "Stocks"](https://www.investor.gov/introduction-investing/investing-basics/investment-products/stocks) |
| ETF | An exchange-traded investment product whose shares are bought and sold "on national securities exchanges at market prices." | [Investor.gov (SEC), "ETF"](https://www.investor.gov/introduction-investing/investing-basics/glossary/exchange-traded-fund-etf) |

<img width="706" height="339" alt="SCR-20260930-labj" src="https://github.com/user-attachments/assets/529d08a7-ffc5-4ed9-96e9-5f80ff3df5e7" />
<img width="723" height="141" alt="SCR-20260930-lafz" src="https://github.com/user-attachments/assets/7868ac3a-7b5b-42be-9bc7-f32f544320cc" />


**Product decision:** in this Dashboard, a **Stock is a US-listed common stock or ETF, priced in USD**.

| Decision | Choice | Why |
| -------- | ------ | --- |
| Markets | US only: Nasdaq, NYSE, NYSE American, NYSE Arca, Cboe BZX | Lab 1 uses one currency (USD); one trading calendar |
| Included | Common stock (including share classes) and ETFs | What individual investors follow; matches Lab 1 scope |
| Excluded | Preferred stock, ADRs, closed-end funds, ETNs, warrants, rights, units, OTC | Different pricing and risk; not needed in version 1 |
| Delisted | Kept with history, labeled "delisted, no current price"; the User decides whether to remove it from the Watchlist | A Watchlist item never disappears without warning |

### How many Stocks

Source: Nasdaq Trader symbol directory, [`nasdaqlisted.txt`](https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt) and [`otherlisted.txt`](https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt), observed **2026-09-29**. Counted by the ETF flag and by security name, without test issues and excluded types.

| Group | Count |
| ----- | ----- |
| ETFs | 5,739 |
| Common stock | 5,254 |
| Ambiguous names (upper bound) | 159 |
| **Supported Stocks** | **11,152** |

<img width="870" height="163" alt="SCR-20260930-lbdo" src="https://github.com/user-attachments/assets/6647965f-14ba-4781-9771-02a453c1613c" />
<img width="744" height="148" alt="SCR-20260930-lbfl" src="https://github.com/user-attachments/assets/bded7f2b-edd6-493b-968c-d8c9f0fae523" />


### Synchronized data

Stored fields per data set are listed in the record sizes below.

| Data set | Product need | Sync (assumption) | Retention |
| -------- | ------------ | ----------------- | --------- |
| Stock reference | Search, Filter, Stock detail, delisted label | Daily | Kept, never deleted |
| Latest prices | Stock price with delay label, Watchlist, Overview | Every 1 min in market hours | 1 per Stock, overwritten |
| Daily bars | History, 3 months to 5 years | Daily, after the close | 5 years rolling |
| 5-minute bars | History, 1 day to 1 month | Every 5 min in market hours | 30 days rolling |
| Corporate actions | Adjust history for splits | Daily | 5 years rolling |
| Trading calendar | Market-hours window, "at close" label | Yearly | 6 years |

Not stored: bid/ask quotes, tick trades, fundamentals, news, and logos, because no reviewed read needs them.

### Representative record

Stock reference sample (average name length measured on the symbol files: 38.4 characters):

```json
{"id": 104, "symbol": "AAPL", "figi": "BBG000B9XRY4", "name": "Apple Inc. - Common Stock",
 "exchange": "Q", "type": "stock", "status": "active", "sector": "Information Technology",
 "industry": "Technology Hardware, Storage & Peripherals", "shares": 14840390000,
 "listed": "1980-12-12", "delisted": null, "updated": "2026-09-29T06:00Z"}
```

| Record | Bytes |
| ------ | ----- |
| Stock reference | id 8 + symbol 8 + FIGI 12 + name 40 + exchange/type/status 3 + sector 16 + industry 28 + shares 8 + dates 8 + updated 8 = **139** |
| Latest price | id, last price, previous close, volume, provider time, received time 6 x 8 + state 1 = **49** |
| Price bar (daily or 5-min) | id 8 + time 8 + open/high/low/close 32 + volume 8 + interval 1 = **57** |
| Corporate action | id 8 + type 1 + ex-date 4 + values 16 + recorded 8 = **37** |
| Calendar day | date 4 + status 1 + open 4 + close 4 + exchange 1 = **14** |

### Calculation

Assumptions: 252 trading days per year (5 years = 1,260), 30 days = 21 trading days, 78 five-minute bars per session, 4 corporate actions per Stock per year, about 1,000 new listings per year. 1 MiB = 2^20 B, 1 GiB = 2^30 B.

```text
raw storage = record count x average bytes per record
history record count = supported Stocks x history points per Stock per day x retained days
```

**Initial load (launch day)**

| Data set | Product decision and retention | Record-count calculation | Bytes per record | Raw storage |
| -------- | ------------------------------ | ------------------------ | ---------------- | ----------- |
| Stock reference data | All supported Stocks, delisted kept | 11,152 | 139 | 1.48 MiB |
| Latest prices | 1 per Stock, overwritten | 11,152 | 49 | 0.52 MiB |
| Price history, daily | 5 years, backfilled | 11,152 x 1 x 1,260 = 14,051,520 | 57 | 763.83 MiB |
| Price history, 5-min | 30 days, backfilled | 11,152 x 78 x 21 = 18,266,976 | 57 | 992.98 MiB |
| Other: corporate actions | 5 years | 11,152 x 4 x 5 = 223,040 | 37 | 7.87 MiB |
| Other: trading calendar | 6 years | 6 x 365 = 2,190 | 14 | 0.03 MiB |
| **Total** | | | | **1.73 GiB** |

**Daily and one-year growth**

| Data set | Per trading day | Written in one year | Held after one year |
| -------- | --------------- | ------------------- | ------------------- |
| Stock reference + latest prices | ~4 new Stocks x (139 + 49) B = 752 B | 1,000 x 188 B = 0.18 MiB | 2.18 MiB |
| Price history, daily | 11,152 x 57 B = 0.61 MiB | x 252 = 152.77 MiB | 763.83 MiB (rolling) |
| Price history, 5-min | 11,152 x 78 x 57 B = 47.28 MiB | x 252 = 11.64 GiB | 992.98 MiB (rolling) |
| Corporate actions + calendar | ~6.5 KB | 1.58 MiB | 7.90 MiB (rolling) |
| **Total** | **47.9 MiB** | **11.79 GiB** | **1.73 GiB** |

Raw data only, without indexes, replicas, or backups. The held size stays flat because of rolling retention.

---

## 5. Potential bottlenecks

| Quality | Potential bottleneck | Evidence from this lab | Possible effect | What to measure next |
| ------- | -------------------- | ---------------------- | --------------- | -------------------- |
| Latency | Stock price read path | 6,000 of 7,920 steady RPS; strictest target (p95 <= 1 s) | p95 above 1 s; other reads queue past 2 s | p95 of Stock price in a load test at 6,000 RPS |
| Consistency | Latest-price sync from the provider | 15 min delay vs 20 min limit | Many prices "unavailable," or an old price labeled current | Price age per read; longest gap between successful syncs |
| Throughput | Market-open burst | 7,920 -> 10,296 RPS (+30%) within 10 s | Reads queue and time out at the peak | Acceptable reads/s and timeouts in a 10 s step test |
| Availability | Single Market Data Provider | One provider in System Context; 8 min 11 s budget | A long provider outage uses the whole monthly budget | Provider incident history and SLA; sync gap durations |

**Latency:** (1) 20% of Users poll the Stock price every second. (2) Slow reads push p95 past 1 s, and shared load pushes other reads past 2 s. (3) It is 75.8% of steady traffic, yet the price changes only once per minute. (4) Load test at 6,000 RPS; reject if p95 stays under 1 s.

**Consistency:** (1) The sync path from the provider into latest prices. (2) Only 5 min of slack remain, so a few failed syncs make prices "unavailable," and using received time instead of provider time would show stale prices as current. (3) 15 min delay vs 20 min limit. (4) Log price age per read; reject if no read over 20 min is labeled current.

**Throughput:** (1) The extra Overview and Watchlist refreshes at the open. (2) If 10,296 acceptable reads/s cannot be completed, requests time out at peak demand. (3) +30% in 10 s, while the first session prices arrive. (4) Step test from 7,920 to 10,296 RPS; reject if the targets hold.

**Availability:** (1) The provider is the only source of prices. (2) An outage of about 13 min (5 min slack + 8 min budget) in market hours breaks the monthly target alone. (3) 99.9% target and one provider in System Context. (4) Provider incident history and sync gaps over 30 days; reject if no gap exceeds slack + budget.
