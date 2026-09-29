# Lab 2: Personal Investment Dashboard - Quality and Estimates

Goal: turn the reviewed Lab 1 behavior into measurable quality targets, a read workload estimate for three scales, and a market-data storage estimate.

---

## 0. Starting point

This lab uses the reviewed Lab 1 scope given in the Lab 2 brief:

- The authenticated User is the direct human actor.
- The Market Data Provider is the external system.
- The first version supports market overview, filtering, search, Stock detail, price history, and a private Watchlist.
- Market prices show provider time or delay. A missing price is unavailable, not zero.
- A User cannot read or change another User's Watchlist.

The reviewed read set is **Overview, Filter, Stock price, History, Watchlist, and Search**. My Lab 1 also defined portfolio reads (holdings, broker import, gain or loss, allocation). Those reads are not part of the reviewed read set, so they are left out of every estimate in this lab.

### Client brief as product inputs

| Client statement | How this lab uses it |
| ---------------- | -------------------- |
| Stock prices should feel immediate. | A stricter latency target for the Stock price read than for the other reads |
| Most correct reads should complete within 2 seconds during busy periods. | p95 client-observed latency <= 2 s at the market-open target workload |
| Expected provider delay is about 15 minutes. | Accepted staleness of up to 20 minutes, then unavailable |
| Older data must be visibly delayed or unavailable. | Every price shows its provider time and a "delayed," "at close," or "unavailable" label |
| Uptime must be measurable separately during market hours and the rest of the day. | Two uptime windows with separate targets and downtime budgets |

---

## 1. Quality requirements

Each requirement uses the form: **Under _operating condition_, _measure_ must meet _target_.**

### Shared definitions

| Term | Definition |
| ---- | ---------- |
| Market hours | NYSE regular session, Monday to Friday, 09:30-16:00 ET, on trading days in the stored trading calendar. On half-days the window ends at 13:00 ET. |
| Rest of the day | All other time: nights, weekends, exchange holidays, and pre-market and after-hours periods. |
| Correct read | The requested data for the authenticated User, with every price labeled by provider time and state ("delayed," "at close," or "unavailable"). |
| Unavailable result | An explicit "unavailable, retry" response. It is never counted as a correct read, even when it is fast. |
| Target workload | The rounded-up market-open target from section 3 for the scale being tested: 103, 1,030, or 10,296 RPS. |

### Q1. Read latency

**Measurement points:** client-observed, from the moment the Client sends the request until the result is usable on screen. This includes both network legs and Client rendering, because the brief is about what the User feels.

| ID | Operating condition | Measure | Target |
| -- | ------------------- | ------- | ------ |
| LAT-1 | During market hours, up to the target workload | Client-observed latency of all six reads, per read type, over each 30-day window | p50 <= 500 ms and **p95 <= 2 s** |
| LAT-2 | Same | Client-observed latency of the Stock price read ("feel immediate") | p50 <= 300 ms and **p95 <= 1 s** |
| LAT-3 | Any time | Behavior at the 2-second limit | The Client stops waiting at 2 s and shows "unavailable, retry." The attempt counts as over 2 s for LAT-1 and LAT-2 and as a failed attempt for availability. |

"Most reads" means p95: 95 of every 100 reads of a given type meet the limit. An average is not used because it hides the slow tail. A fast "unavailable" result counts toward the latency percentile but still fails availability (Q2) and, for prices, consistency (Q3).

### Q2. Uptime-style availability

**When the Dashboard is usable:** an external synthetic check runs each of the six reads once per minute for a test User. A minute counts as usable only if **all six** reads return a correct read within 2 s. During market hours, a Stock price check for a reference set of liquid Stocks (for example SPY and AAPL) that returns "price unavailable" makes the minute unusable, because a price inside the 20-minute limit should always exist then. Outside market hours, a correctly labeled "at close" price counts as correct.

```text
uptime availability = usable minutes / measured minutes   (per window)
downtime budget     = measured time x (1 - target)
```

**Assumption:** a 30-day window contains 21 full trading days. Half-days and holidays are taken from the trading calendar when the real window is measured.

| Window | Measured time in 30 days | Target | Downtime budget per 30 days |
| ------ | ------------------------ | ------ | --------------------------- |
| Market hours | 21 days x 6.5 h = 136.5 h = 491,400 s | **99.9%** (three nines) | 491,400 s x 0.001 = 491.4 s = **8 min 11 s** |
| Rest of the day | 720 h - 136.5 h = 583.5 h = 2,100,600 s | **99%** (two nines) | 2,100,600 s x 0.01 = 21,006 s = **5 h 50 min 6 s** |

**Why the targets differ:**

- During market hours, prices change every minute, the market-open burst happens, and most Users are active. An outage then hides moves the User cannot see later in the same form.
- Outside market hours, prices are frozen at the session close and traffic is lower. An outage delays reading, but no price change is missed.
- 99.99% in market hours would cut the budget to about 49 s per 30 days. The Dashboard is read-only and does not trade, so a few unavailable minutes do not lose the User money directly. The extra engineering and redundancy against a single provider are not justified by the avoided harm (ROI).
- 99% outside market hours still bounds downtime to under 6 h per 30 days, which leaves room for planned maintenance outside the session.

### Q3. Consistency

#### CON-1: Stock price staleness

**Measure:** price age = time of the read - provider time of the returned price.

| Situation | What a Stock price read may show |
| --------- | -------------------------------- |
| Market hours, price age <= 20 min | The price with "Delayed ~15 min, as of HH:MM ET." |
| Market hours, price age > 20 min | **"Price unavailable."** The last known price may appear only as "last known at HH:MM ET, not current." It is never shown as the current price. |
| First 20 min of the session | The previous close with "previous close," until a price from the new session arrives. |
| Outside market hours | The session close price with "At close, HH:MM ET." |
| No price exists | "Price unavailable." Never zero. |

**Target:** during market hours, 100% of Stock price reads with price age > 20 min are labeled "unavailable." No read shows a price older than 20 minutes as current.

The 20-minute limit is the 15-minute provider delay plus 5 minutes of slack for synchronization and small provider variations.

**Monotonic reads:** for the same User and Stock, a later read never shows an older provider time than an earlier read.

#### CON-2: Watchlist read-your-writes

**Operating condition:** a User adds or removes a Stock, and the Dashboard confirms the change.

**Target:**

- Every later Watchlist read by the same User, from any device, includes the confirmed change.
- No later read returns to the list as it was before the change.
- If the Dashboard cannot guarantee this, the read returns "Watchlist unavailable" instead of the older list.
- A User never sees or changes another User's Watchlist ("unauthorized").

### Q4. Throughput

| ID | Operating condition | Measure | Target |
| -- | ------------------- | ------- | ------ |
| THR-1 | During market hours, at the steady mix from section 2 | Acceptable completed reads per second | 79.2 / 792 / 7,920 RPS for 300 / 3,000 / 30,000 Users |
| THR-2 | In the 10-second market-open window, at the mix from section 3 | Acceptable completed reads per second | **103 / 1,030 / 10,296 RPS** for 300 / 3,000 / 30,000 Users |

A read is acceptable only if it is correct and meets Q1 and Q3. Reads that are started but finish late, stale, or unavailable are not counted.

---

## 2. Steady RPS estimates

```text
RPS = concurrent Users x participating share x actions per User / seconds
```

**Assumptions:**

- Each listed User action creates one Dashboard request.
- All reads happen at the same time.
- Percentages are average shares within the window.
- Provider requests, retries, and background synchronization are excluded.

### Calculations

| Read | Behavior | 300 Users | 3,000 Users | 30,000 Users |
| ---- | -------- | --------- | ----------- | ------------ |
| Overview | 70%, 1 per 30 s | 300 x 0.70 x 1 / 30 = **7** | 3,000 x 0.70 x 1 / 30 = **70** | 30,000 x 0.70 x 1 / 30 = **700** |
| Filter | 50%, 3 per 60 s | 300 x 0.50 x 3 / 60 = **7.5** | 3,000 x 0.50 x 3 / 60 = **75** | 30,000 x 0.50 x 3 / 60 = **750** |
| Stock price | 20%, 1 per 1 s | 300 x 0.20 x 1 / 1 = **60** | 3,000 x 0.20 x 1 / 1 = **600** | 30,000 x 0.20 x 1 / 1 = **6,000** |
| History | 20%, 1 per 300 s | 300 x 0.20 x 1 / 300 = **0.2** | 3,000 x 0.20 x 1 / 300 = **2** | 30,000 x 0.20 x 1 / 300 = **20** |
| Watchlist | 60%, 1 per 60 s | 300 x 0.60 x 1 / 60 = **3** | 3,000 x 0.60 x 1 / 60 = **30** | 30,000 x 0.60 x 1 / 60 = **300** |
| Search | 10%, 3 per 60 s | 300 x 0.10 x 3 / 60 = **1.5** | 3,000 x 0.10 x 3 / 60 = **15** | 30,000 x 0.10 x 3 / 60 = **150** |

All values are in requests per second (RPS) and unrounded.

### Result

| Read | 300 Users | 3,000 Users | 30,000 Users |
| ---- | --------- | ----------- | ------------ |
| Overview | 7 | 70 | 700 |
| Filter | 7.5 | 75 | 750 |
| Stock price | 60 | 600 | 6,000 |
| History | 0.2 | 2 | 20 |
| Watchlist | 3 | 30 | 300 |
| Search | 1.5 | 15 | 150 |
| **Steady total** | **79.2 RPS** | **792 RPS** | **7,920 RPS** |

```text
300:    7 + 7.5 + 60 + 0.2 + 3 + 1.5       = 79.2 RPS
3,000:  70 + 75 + 600 + 2 + 30 + 15        = 792 RPS
30,000: 700 + 750 + 6,000 + 20 + 300 + 150 = 7,920 RPS
```

**Observations:**

- The Stock price read creates 60 / 79.2 = **75.8%** of steady traffic at every scale. It is the first path to investigate for latency, but that alone does not prove it is a bottleneck.
- Every input is linear, so each 10x step in Users gives exactly 10x RPS. This holds only if User behavior, data distribution, and provider limits stay the same at 10x, which the model does not prove.

---

## 3. Market-open RPS estimates

**Market-open behavior:** within a 10-second window, 30% of Users refresh the Overview once, and 60% of that group also refresh their Watchlist. These actions are added on top of steady traffic. The steady Overview and Watchlist traffic already sits in the steady total and is not counted again.

```text
additional Overview  = Users x 0.30 x 1 / 10 s
additional Watchlist = Users x 0.30 x 0.60 x 1 / 10 s
subtotal             = steady + additional Overview + additional Watchlist
margin               = subtotal x 0.10
target               = round up (subtotal + margin)
```

| Market-open calculation | 300 Users | 3,000 Users | 30,000 Users |
| ----------------------- | --------- | ----------- | ------------ |
| Steady read traffic | 79.2 | 792 | 7,920 |
| Additional Overview refresh flow | 300 x 0.30 / 10 = 9 | 3,000 x 0.30 / 10 = 90 | 30,000 x 0.30 / 10 = 900 |
| Additional Watchlist refresh flow | 300 x 0.30 x 0.60 / 10 = 5.4 | 3,000 x 0.30 x 0.60 / 10 = 54 | 30,000 x 0.30 x 0.60 / 10 = 540 |
| **Market-open subtotal** | **93.6** | **936** | **9,360** |
| 10% capacity margin | 9.36 | 93.6 | 936 |
| **Rounded-up market-open target** | 102.96 -> **103 RPS** | 1,029.6 -> **1,030 RPS** | 10,296 -> **10,296 RPS** |

Only the final target is rounded. At 30,000 Users, 10,296 is already a whole number. The market-open target is 30% above steady traffic (10,296 / 7,920 = 1.30). The margin adds headroom above the estimate; it does not fix missing reads or wrong assumptions.

---

## 4. Storage estimates

### 4.1 Research: what is a "Stock"?

In market-data products, "stock" is used loosely. A symbol list can mix common stock, preferred stock, ADRs, ETFs, ETNs, closed-end funds, warrants, rights, and units, all traded on an exchange under a ticker.

| Instrument | Definition | Source |
| ---------- | ---------- | ------ |
| Stock | "A type of security that gives stockholders a share of ownership in a company." There are two main kinds: **common stock**, which carries voting rights and dividends, and **preferred stock**, which usually has no vote but gets dividends first. | [Investor.gov (SEC), "Stocks"](https://www.investor.gov/introduction-investing/investing-basics/investment-products/stocks), observed 2026-09-29 |
| ETF | "An exchange-traded investment product that must register with the SEC as an open-end investment company." Unlike mutual funds, ETF shares are bought and sold "on national securities exchanges at market prices." | [Investor.gov (SEC), "Exchange-Traded Fund (ETF)"](https://www.investor.gov/introduction-investing/investing-basics/glossary/exchange-traded-fund-etf), observed 2026-09-29 |
| Listed-symbol directory | Nasdaq publishes every security listed on Nasdaq (`nasdaqlisted.txt`) and on the other US exchanges (`otherlisted.txt`), with an ETF flag, a test-issue flag, and the listing exchange. Nasdaq updates the files during each day. | [Nasdaq Trader, Symbol Directory Definitions](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs) |

> **Screenshot placeholder:** Investor.gov "Stocks" page, section "What kinds of stocks are there?" (save as `assets/investor-gov-stocks.png`).

> **Screenshot placeholder:** Investor.gov "Exchange-Traded Fund (ETF)" glossary entry (save as `assets/investor-gov-etf.png`).

### 4.2 Product decision: a supported Stock

> In this Dashboard, a **Stock** is a **US-listed common stock or ETF**, priced in **USD**, that is listed on a US national securities exchange: Nasdaq, NYSE, NYSE American, NYSE Arca, or Cboe BZX.

| Decision | Choice | Justification |
| -------- | ------ | ------------- |
| Countries and exchanges | United States only. Common stock on Nasdaq, NYSE, and NYSE American. ETFs on any US national exchange, which in practice is mostly NYSE Arca, Nasdaq, and Cboe BZX. | Matches the Lab 1 one-currency (USD) constraint. One exchange calendar and one set of market hours keeps the uptime windows simple. |
| Included types | Common stock (including ordinary shares and share classes such as GOOG / GOOGL) and ETFs | These are what an individual investor usually follows. Lab 1 already scoped the product to stocks and ETFs. |
| Excluded types | Preferred stock, ADRs / ADSs, closed-end funds, ETNs, warrants, rights, units, notes, OTC securities, test issues | These have different pricing or risk. Lab 1 excluded options, bonds, and mutual funds, and these other types stay out of version 1 too. |
| Inactive or delisted | **Kept and marked "delisted."** They remain searchable, and their stored history stays readable. They have no current price ("delisted, no current price"). If a delisted Stock is on a User's Watchlist, the Watchlist entry shows **"This Stock was delisted. Remove from Watchlist? Yes / No."** The Dashboard never removes it automatically. | Watchlist items never disappear without warning, and the User stays in control of their own list. |

### 4.3 How many Stocks

**Source:** [Nasdaq Trader `nasdaqlisted.txt`](https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt) and [`otherlisted.txt`](https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt). Both files were downloaded on **2026-09-29**, and both show "File Creation Time: 0929202606:00."

**Method:**

1. Remove test issues.
2. Count every row with ETF = Y as an ETF.
3. For the other rows, exclude names that contain preferred, warrant, right, unit, depositary / ADR / ADS, closed-end fund, notes, and similar terms.
4. Count names that contain "Common Stock," "Common Share(s)," or "Ordinary Share(s)" as common stock.
5. Some remaining names are ambiguous, such as "Alphabet Inc. - Class C Capital Stock" and "AMETEK, Inc." Include them as an upper bound.

| Group | Count (2026-09-29) |
| ----- | ------------------ |
| ETFs | 5,739 |
| Common stock, clearly identified by name | 5,254 (Nasdaq 3,192, NYSE 1,816, NYSE American 245, Cboe BZX 1) |
| Ambiguous names kept as an upper bound | 159 |
| Excluded (preferred, ADRs, closed-end funds, warrants, units, notes, and similar) | 2,091 |
| **Supported Stocks used for sizing** | **5,739 + 5,254 + 159 = 11,152** |

> **Screenshot placeholder:** the `nasdaqlisted.txt` and `otherlisted.txt` files open in the browser, showing the header and the "File Creation Time" line (save as `assets/nasdaq-symbol-directory.png`).

**Research effect on scope:**

| Decision | Effect | Evidence |
| -------- | ------ | -------- |
| Define "Stock" as common stock + ETF, not "anything with a ticker" | Changed | About 2,100 listed symbols are preferred shares, ADRs, funds, warrants, or notes that a raw symbol list would include |
| Include ETF exchanges (NYSE Arca, Cboe BZX), not only NYSE / Nasdaq | Changed | Most ETFs are listed on NYSE Arca (2,725) and Cboe BZX (1,642) |
| Stocks and ETFs in USD only | Confirmed | Matches the Lab 1 constraints |

### 4.4 Synchronized data

Every stored field is tied to a product need. Provider fields with no read that uses them are not stored.

| Data set | Stored fields | Product need |
| -------- | ------------- | ------------ |
| Stock reference data | internal id, symbol, FIGI (provider-independent id), name, exchange, type (stock / ETF), status (active / delisted), sector, industry, shares outstanding, listed date, delisted date, updated time | **Search** by symbol and name; **Filter** by exchange, type, sector, and market-cap band (shares outstanding x price); **Stock detail** header; the delisted label |
| Latest prices | Stock id, last price, previous close, day volume, **provider time**, received time, price state | **Stock price** with provider time and delay label (CON-1); **Watchlist** prices; **Overview** index ETFs (SPY, QQQ, DIA), gainers / losers (price vs previous close), and most active (volume) |
| Price history, daily bars | Stock id, bar date, open, high, low, close, volume | **History** charts for ranges from 3 months to 5 years |
| Price history, 5-minute bars | Stock id, bar start time, open, high, low, close, volume | **History** charts for 1 day, 1 week, and 1 month |
| Corporate actions | Stock id, type (split / dividend), ex-date, value A (ratio numerator or dividend amount), value B (ratio denominator), recorded time | Adjust history so that a split does not show a fake price drop |
| Trading calendar | date, session status (open / closed / half-day), open time, close time | Decide market hours vs the rest of the day (Q2), the "at close" and "previous close" labels (CON-1), and which days have bars |

**Not stored:** quotes (bid / ask), tick trades, fundamentals, news, company descriptions, and logos. No reviewed read needs them. Index levels are not stored either; the Overview uses index ETFs as proxies, since index data needs separate licensing.

**Synchronization frequency (assumption):**

| Data set | Frequency |
| -------- | --------- |
| Latest prices | Every 1 minute during market hours, plus once after the close |
| 5-minute bars | Every 5 minutes during market hours |
| Daily bars | Once per trading day, after the close |
| Reference data, corporate actions | Once per day, before the session |
| Trading calendar | Once per year, plus when the exchange publishes a change |

Provider request traffic is not estimated here. It needs its own model.

**Retention:**

| Data set | Retention |
| -------- | --------- |
| Daily bars | 5 years, rolling. Backfilled at launch. |
| 5-minute bars | 30 calendar days (about 21 trading days), rolling |
| Corporate actions | 5 years, the same as daily bars, so that history can be adjusted |
| Trading calendar | 5 years back + 1 year ahead |
| Latest prices | One record per Stock, overwritten on each sync |
| Reference data | Kept for delisted Stocks, never deleted |

### 4.5 Representative records and bytes per record

Sizes use fixed-width fields. Measured on the 2026-09-29 symbol files, the 11,152 supported Stocks have an average name length of **38.4 characters** and an average symbol length of **3.7 characters**, with a maximum of 6.

**Stock reference record** (sample: AAPL)

| Field | Sample value | Bytes (average) |
| ----- | ------ | ----- |
| internal id | 104 | 8 |
| symbol | AAPL | 8 |
| FIGI | BBG000B9XRY4 | 12 |
| name (average 38.4 chars) | Apple Inc. - Common Stock | 40 |
| exchange, type, status | Q, stock, active | 3 |
| sector (average) | Information Technology | 16 |
| industry (average) | Technology Hardware, Storage & Peripherals | 28 |
| shares outstanding | 14,840,390,000 | 8 |
| listed date, delisted date | 1980-12-12, null | 8 |
| updated time | 2026-09-29T06:00Z | 8 |
| **Total** | | **139 bytes** |

**Latest price record:** Stock id 8 + last price 8 + previous close 8 + day volume 8 + provider time 8 + received time 8 + price state 1 = **49 bytes**

**Price bar (daily or 5-minute):** Stock id 8 + bar time 8 + open, high, low, close 4 x 8 + volume 8 + interval 1 = **57 bytes**

**Corporate action:** Stock id 8 + type 1 + ex-date 4 + value A 8 + value B 8 + recorded time 8 = **37 bytes**

**Trading calendar day:** date 4 + status 1 + open time 4 + close time 4 + exchange group 1 = **14 bytes**

### 4.6 Storage calculation

```text
raw storage = record count x average bytes per record

history record count
  = supported Stocks x history points per Stock per day x retained days
```

**Assumptions:**

- 11,152 supported Stocks.
- 252 trading days per year, so 5 years = 1,260 trading days.
- 30 calendar days = 21 trading days.
- A 6.5 h session = 78 five-minute bars per day.
- On average, 4 corporate actions per Stock per year (quarterly dividends).
- About 1,000 new listings per year. This is an unverified assumption, and delisted Stocks are kept.
- 1 MiB = 1,048,576 bytes and 1 GiB = 1,073,741,824 bytes.
- Every Stock is counted as having the full 5 years of history, which gives an upper bound.

#### Initial load (launch day)

| Data set | Product decision and retention | Record-count calculation | Bytes per record | Raw storage |
| -------- | ------------------------------ | ------------------------ | ---------------- | ----------- |
| Stock reference data | Supported Stocks. Delisted ones are kept. | 11,152 Stocks | 139 | 1,550,128 B ~= **1.48 MiB** |
| Latest prices | One per Stock, overwritten each minute | 11,152 Stocks | 49 | 546,448 B ~= **0.52 MiB** |
| Price history, daily | 5 years rolling, backfilled | 11,152 x 1 per day x 1,260 days = 14,051,520 | 57 | 800,936,640 B ~= **763.83 MiB** |
| Price history, 5-min | 30 days rolling, backfilled | 11,152 x 78 per day x 21 days = 18,266,976 | 57 | 1,041,217,632 B ~= **992.98 MiB** |
| Other: corporate actions | 5 years, to adjust history | 11,152 x 4 per year x 5 years = 223,040 | 37 | 8,252,480 B ~= **7.87 MiB** |
| Other: trading calendar | 5 years back + 1 year ahead | 6 x 365 = 2,190 days | 14 | 30,660 B ~= **0.03 MiB** |
| **Total** | | | | 1,852,533,988 B ~= **1.73 GiB** |

#### Daily growth (per trading day)

| Data set | Calculation | Raw storage per day |
| -------- | ----------- | ------------------- |
| Stock reference data | 1,000 / 252 ~= 4 new Stocks x 139 B | ~556 B |
| Latest prices | Overwritten, so 0 new records (4 new Stocks x 49 B) | ~196 B |
| Price history, daily | 11,152 x 1 x 57 B | 635,664 B ~= 0.61 MiB |
| Price history, 5-min | 11,152 x 78 x 57 B | 49,581,792 B ~= 47.28 MiB |
| Corporate actions | 11,152 x 4 / 252 ~= 177 x 37 B | ~6,550 B |
| Trading calendar | Loaded once per year | 0 B |
| **Total written per trading day** | | ~50.2 MB ~= **47.9 MiB** |

5-minute bars are 99% of daily growth. They are also deleted after 30 days, so they grow the amount written each day but not the amount held.

#### One year

| Data set | Written during one year | Held after one year (retention applied) |
| -------- | ----------------------- | --------------------------------------- |
| Stock reference data | 1,000 x 139 B = 139,000 B | (11,152 + 1,000) x 139 B = 1,689,128 B ~= 1.61 MiB |
| Latest prices | 1,000 x 49 B = 49,000 B | 12,152 x 49 B = 595,448 B ~= 0.57 MiB |
| Price history, daily | 11,152 x 252 x 57 B = 160,187,328 B ~= 152.77 MiB | Rolling 5 years, stays ~= 763.83 MiB |
| Price history, 5-min | 11,152 x 78 x 252 x 57 B = 12,494,611,584 B ~= 11.64 GiB | Rolling 30 days, stays ~= 992.98 MiB |
| Corporate actions | 11,152 x 4 x 37 B = 1,650,496 B ~= 1.57 MiB | Rolling 5 years, stays ~= 7.87 MiB |
| Trading calendar | 365 x 14 B = 5,110 B | Rolling, stays ~= 0.03 MiB |
| **Total** | ~= **11.79 GiB** written | ~= **1.73 GiB** held |

This is raw data only. It excludes indexes (for example, for Search), replicas, backups, logs, Watchlist and User data, and temporary copies. It is not a storage purchase plan. The held size stays almost flat because both history sets have rolling retention. Keeping 5-minute bars longer would be the main thing that grows it.

---

## 5. Potential bottlenecks

A high RPS value is a reason to investigate a path, not proof of a bottleneck. Each row below is a hypothesis.

| Quality | Potential bottleneck | Evidence from this lab | Possible effect | What to measure next |
| ------- | -------------------- | ---------------------- | --------------- | -------------------- |
| Latency | Stock price read path | 60 / 600 / 6,000 RPS = 75.8% of steady traffic; LAT-2 is the strictest target (p95 <= 1 s) | Stock price p95 goes above 1 s, or other reads queue behind it and exceed 2 s | Client-observed p50 / p95 of Stock price at 6,000 RPS in a load test, split into network, within-system, and render time |
| Consistency | Latest-price synchronization path from the Market Data Provider | CON-1 allows 20 min; the provider delay is already about 15 min; sync runs every 1 min | Prices become "unavailable" too often, or an old price is shown as current if the label uses received time instead of provider time | Distribution of price age (read time - provider time) during market hours; share of reads over 20 min; sync success rate and duration |
| Throughput | Market-open burst on Overview + Watchlist | At 30,000 Users, 7,920 -> 10,296 RPS (+30%) within 10 s; first prices of the session arrive at the same time | Reads above sustainable throughput queue, pass 2 s, and time out, so fewer acceptable reads per second | Acceptable completed reads per second and p95 in a load test that steps from 7,920 to 10,296 RPS within 10 s with the market-open mix |
| Availability | Market Data Provider as the single external source during market hours | System Context has one provider; every read depends on its data; the market-hours budget is only 8 min 11 s per 30 days | A provider outage longer than the 5-minute staleness slack makes prices "unavailable," and those minutes count as down | Provider incident history and SLA; duration of sync gaps over 30 days; time from provider recovery until prices are fresh again |

### Latency: Stock price read path

1. **Pressure:** the Stock price read. 20% of Users poll it once per second. That is the most frequent read by far, and it has the strictest target.
2. **How it can fail:** every one of the 6,000 RPS (at 30,000 Users) needs the latest price and a correct label. If each read does expensive work, or waits on a dependency, the tail grows. p95 then passes 1 s (LAT-2), and shared resources can push the other reads past 2 s (LAT-1).
3. **Evidence:** section 2 shows the Stock price read is 75.8% of steady traffic at all scales. The price itself changes only once per minute (one sync), but each User requests it up to 60 times in that minute. That is a sign of many repeated reads of the same value. This is a design question for later, not a chosen solution.
4. **Confirm or reject:** run a constant-arrival-rate load test (for example, k6) at 6,000 Stock price RPS plus the rest of the steady mix. Measure client-observed p50 / p95 and how much time is spent inside the Dashboard vs the network. If p95 stays <= 1 s with margin, reject the hypothesis.

### Consistency: latest-price synchronization

1. **Pressure:** the state path from the Market Data Provider into the stored latest prices, which every Stock price, Watchlist, and Overview read uses.
2. **How it can fail:** the provider delay is "about" 15 min, and the limit is 20 min. That leaves only about 5 minutes for missed syncs and provider variation. If the delay drifts to 18 min, or a few syncs fail in a row, many prices become "unavailable." A worse case is an error in which price age is calculated from received time instead of provider time. Then a 25-minute-old price would be shown as current, which is a visible failure of CON-1.
3. **Evidence:** the client brief (15-minute delay), the CON-1 limit (20 min), the sync assumption (every 1 min), and the single provider in the System Context view.
4. **Confirm or reject:** log price age for every Stock price read during market hours. Measure the share of reads over 20 min, the longest gap between successful syncs, and whether any read labeled "current" had an age over 20 min. If there are zero wrong labels and "unavailable" is rare, reject the hypothesis.

### Throughput: market-open burst

1. **Pressure:** in the first 10 seconds of the session, 30% of Users refresh the Overview and 60% of them also refresh their Watchlist, on top of steady traffic.
2. **How it can fail:** at 30,000 Users, acceptable reads per second must jump from 7,920 to 10,296 almost at once. At the same moment the first prices of the session start arriving, and every Overview and Watchlist response must change from "previous close" to fresh values. If the Dashboard cannot complete that many acceptable reads, requests queue and time out at 2 s. Throughput falls exactly when demand peaks.
3. **Evidence:** section 3 shows a 30% jump in a 10-second window, concentrated on two reads. The Overview is the same for all Users, while each Watchlist is different for each User.
4. **Confirm or reject:** in a test environment, step the load from 7,920 to 10,296 RPS within 10 s using the market-open mix. Measure acceptable completed reads per second, p95 latency, and timeouts during the burst. If THR-2 and LAT-1 hold, reject the hypothesis.

### Availability: Market Data Provider dependency

1. **Pressure:** the Market Data Provider is the only external source of Stock identity, prices, and history (System Context view).
2. **How it can fail:** the stored latest prices absorb short provider outages. A provider outage shorter than about 5 minutes leaves prices within the 20-minute limit. A longer outage makes Stock prices "unavailable," and during market hours each such minute is unusable (Q2). The market-hours budget is 8 min 11 s per 30 days, so a single provider outage of about 13 minutes (5 min slack + 8 min budget) during the session breaks the monthly target on its own.
3. **Evidence:** the 99.9% market-hours target and budget (Q2), the 20-minute staleness rule (CON-1), and the single external dependency.
4. **Confirm or reject:** collect the provider's incident history and SLA terms for market hours, and the durations of sync gaps over 30 days. Measure how long it takes after provider recovery until prices are within 20 minutes again. If no gap exceeds the slack plus the budget, reject the hypothesis.

---

## Checklist

- [x] I wrote measurable requirements for all core qualities.
- [x] I chose and justified uptime targets for both parts of the day.
- [x] I showed the steady and market-open RPS calculations for all three scales.
- [x] I researched and defined the supported Stock scope.
- [x] I estimated initial, daily, and one-year raw market-data storage.
- [x] I stated assumptions, units, windows, and final rounding.
- [x] I analyzed one potential bottleneck for each core quality.
