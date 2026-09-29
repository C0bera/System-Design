# Lab 1: Personal Investment Dashboard - Initial Product

Client request: *"Help me follow my investments."*

---

## 1. Product research

**Research question:** How do existing products help a User follow market information, and which parts belong in this Dashboard's first version?

| Product | Likely User and goal | Reusable pattern |
| ------- | -------------------- | ---------------- |
| Google Finance (market data) | An individual investor who wants a free, simple view of what their stocks and ETFs are worth and which securities they follow | (a) The User records a holding manually as symbol, number of shares, purchase date, and purchase price. (b) A portfolio (owned holdings with value and gain/loss) is kept separate from a watchlist (followed symbols with no ownership). |
| Robinhood (trading) | A retail investor who buys and sells stocks and ETFs and wants to see how each position is performing | (a) Each held position shows total return and its share of the portfolio. (b) Holdings and watched assets are treated differently, e.g. in price-movement notifications. |

### Evidence

- Google Finance lets the User add a stock by symbol together with share count, purchase date, and purchase price, and then shows portfolio performance and a separate watchlist. Source: [The Motley Fool, "How to Track Stocks With Google Finance"](https://www.fool.com/investing/how-to-invest/stocks/how-to-track-stocks-with-google-finance/)
- Google's own page describes tracking all investments, real-time pricing updates, and overall portfolio worth. It also states that the data is not financial advice. Source: [Google Finance, Portfolio & Watchlist](https://www.google.com/finance/portfolio/watchlist)
  
- For an open position, Robinhood shows returns, equity, and portfolio diversity, including total return since the position was opened. Source: [Robinhood Support, "Viewing stock details"](https://robinhood.com/us/en/support/articles/viewing-stock-detail-pages/)
- Robinhood offers price-movement alerts for held and watched assets. Watchlist alerts are off by default. Source: [Robinhood Support, "Price alerts"](https://www.robinhood.com/us/en/support/articles/price-alerts/)
- Robinhood's core offer is trading stocks, ETFs, options, and crypto, plus paid features and prediction markets. Source: [Robinhood App Store listing](https://apps.apple.com/us/app/robinhood-investing-for-all/id938003185)

### Scope decisions from the research

| Decision | Effect | Evidence |
| -------- | ------ | -------- |
| Keep portfolio and watchlist separate | Confirmed | Google Finance separates owned holdings from followed symbols |
| Add read-only broker import next to manual entry | Changed | With manual entry only, holdings go out of date after every trade |
| Show value, gain/loss, and allocation per holding | Confirmed | Robinhood shows total return and portfolio diversity per position |
| Exclude trading and money movement | Confirmed | Trading is Robinhood's core offer and is a different product from following investments |
| Exclude advice | Confirmed | Google Finance explicitly positions its data as not advice |
| Defer price alerts, technical indicators, news, earnings calendars, fundamentals, crypto, and options | Deferred | Both products offer these, but they are not needed to follow owned stocks and ETFs |

---

## 2. Stakeholders and actors

| Stakeholder | Motivation | Influence | Reason |
| ----------- | ---------- | --------- | ------ |
| Individual investor (User) | High | High | Relies on the Dashboard to know what their investments are worth. As the client, they decide what the product must do. |
| Dashboard product owner | High | High | Accountable for the product and decides its scope and priorities. |
| Household member who shares finances | High | Low | Affected by investment outcomes but does not use the Dashboard or decide its scope. |
| Brokerage (for connected accounts) | Low | High | Gains little from the Dashboard, but can grant, limit, or revoke read access to account holdings. |
| Market data provider | Low | High | The Dashboard is one customer among many, but its coverage, delay, and terms decide which prices the User can see. |
| Financial regulator | Low | High | Does not use the product, but its rules decide whether presented information counts as investment advice. |
| Companies and ETF issuers whose securities are shown | Low | Low | Their securities appear in the Dashboard, but they are barely affected and cannot change product decisions. |

### Motivation and influence matrix

| Motivation | Low influence | High influence |
| ---------- | ------------- | -------------- |
| High | **Consult with:** household member | **Manage closely:** individual investor, product owner |
| Low | **Keep informed:** companies and ETF issuers | **Keep satisfied:** brokerage, market data provider, financial regulator |

### Classification

| Candidate | Classification | Reason |
| --------- | -------------- | ------ |
| Individual investor (User) | Direct human actor | Records holdings, connects broker accounts, and reads portfolio results |
| Market data provider | External system | Supplies symbol information and latest prices to the Dashboard |
| Brokerage (Broker Account Service) | External system | Supplies read-only holdings for accounts the User has authorized |
| Dashboard product owner | Other stakeholder | Makes product decisions but is not part of the User journey |
| Household member | Other stakeholder | Affected by results, but does not interact with the Dashboard |
| Financial regulator | Other stakeholder | Imposes limits but does not interact with the Dashboard |
| Companies and ETF issuers | Other stakeholder | Their securities are shown, but they do not interact with the Dashboard |

---

## 3. Product promise and scope

### Product promise

> **Personal Investment Dashboard** helps an **individual investor** who holds stocks and ETFs **see all their holdings, manually recorded or imported from a broker, in one place with current value and gain or loss**, so that **they always know what their investments are worth and how they are performing without checking each account separately**.

### Goals

1. Let the User record a stock or ETF holding they own.
2. Let the User import stock and ETF holdings from a broker account they authorize, without being able to trade.
3. Show the User the current value and gain or loss of each holding and of the whole portfolio.
4. Show the User how their portfolio value is split across holdings.
5. Let the User follow stocks and ETFs they do not own, separately from their portfolio.

### Non-goals

1. Place, change, or cancel trades, or move money into or out of any account.
2. Give investment recommendations, advice, or tax calculations.
3. Support crypto, options, bonds, mutual funds, or holdings in more than one currency.

### Constraints and assumptions

| Type | Statement |
| ---- | --------- |
| Constraint | The first version supports stocks and ETFs only. |
| Constraint | The first version uses one currency (USD) for all values. |
| Constraint | Broker access is read-only. |
| Constraint | Imported holdings are kept under their broker account. They are not merged or deduplicated with manual holdings. |
| Constraint | A User sees only their own portfolio and watchlist. |
| Assumption | The market data provider returns a price for supported symbols, possibly with a delay. |
| Assumption | At least one brokerage offers read-only access to holdings for a User who authorizes it. |
| Assumption | Imported holdings include quantity. Purchase cost may be missing. |
| Assumption | Google Finance has no broker import (third-party claim, not yet verified). |

---

## 4. Functional requirements

### DASH-1: Record a holding manually

**Actor goal:** The User needs to record a stock or ETF they own so that the Dashboard can track it.

**User story:** As an individual investor, I want to record a stock or ETF holding with its quantity and purchase price, so that the Dashboard can track a position no connected broker reports.

**Definitions of done:**
- A valid holding appears in the User's manual holdings with symbol, security name, quantity, purchase date, and purchase price.
- If the symbol is unknown, or is not a stock or ETF, the Dashboard shows "not supported" and does not add the holding.
- If the quantity is zero or negative, or the purchase date is in the future, the Dashboard rejects the entry and states the reason.
- The holding is visible only to the User who recorded it.

### DASH-2: Import holdings from a broker account

**Actor goal:** The User needs holdings from a broker account to appear without typing them in.

**User story:** As an individual investor, I want to import my stock and ETF holdings from a broker account I authorize, so that my Dashboard matches that account without manual entry.

**Definitions of done:**
- After the User authorizes read access at the brokerage, the account's stock and ETF holdings appear under that account with quantities and the time of import.
- Positions the Dashboard does not support, such as options or crypto, are listed as "not imported: unsupported" and are not silently dropped.
- If the brokerage denies or revokes access, the Dashboard shows "reconnection needed." It keeps the last imported holdings, labeled with the time of the last successful import, and does not present them as current.
- The Dashboard offers no way to place orders or move money through the connected account.

### DASH-3: See portfolio value and gain or loss

**Actor goal:** The User needs to know what their investments are worth now and whether they are up or down.

**User story:** As an individual investor, I want to see the current value and gain or loss of each holding and of my whole portfolio, so that I know how my investments are performing.

**Definitions of done:**
- Each holding shows quantity, latest price with its price time, current value, and gain or loss against purchase cost. The portfolio shows the total of all priced holdings.
- If a price is older than the agreed freshness limit, the Dashboard marks it "stale" and shows its price time.
- If no price is available, the holding shows "price unavailable." It is excluded from the total, and the total is marked incomplete; it is never counted as zero.
- If an imported holding has no purchase cost, the Dashboard shows its value and marks gain or loss as "unknown."

### DASH-4: See portfolio allocation

**Actor goal:** The User needs to know how concentrated their portfolio is.

**User story:** As an individual investor, I want to see what share of my portfolio value each holding represents, so that I can tell whether I depend too much on a few positions.

**Definitions of done:**
- Each priced holding shows its percentage of the total portfolio value, and the percentages add up to 100%.
- Holdings without a current price are listed as "excluded from allocation" with the reason.
- If the User has no holdings, the Dashboard shows that the portfolio is empty and shows no percentages.

### DASH-5: Follow securities on a watchlist

**Actor goal:** The User needs to follow stocks and ETFs they are considering but do not own.

**User story:** As an individual investor, I want to add stocks and ETFs I do not own to a watchlist, so that I can follow their prices without mixing them into my portfolio.

**Definitions of done:**
- An added symbol appears on the watchlist with its latest price, day change, and price time.
- Watchlist items never count toward portfolio value, gain or loss, or allocation.
- If the symbol is unknown or unsupported, the Dashboard shows "not supported" and does not add it.
- If a watchlist price is stale or unavailable, the Dashboard labels it that way instead of showing an old price as current.

### DASH-6: Correct or remove a manual holding

**Actor goal:** The User needs to fix a mistake or record that they sold a manual holding.

**User story:** As an individual investor, I want to edit or remove a holding I recorded manually, so that my portfolio reflects what I actually own.

**Definitions of done:**
- An edited holding shows the new values, and its value and gain or loss are recalculated. A removed holding no longer appears in holdings, totals, or allocation.
- If the User tries to edit or remove an imported holding, the Dashboard refuses and states that the holding is managed by the broker account.
- A User cannot view, edit, or remove another User's holdings; the Dashboard returns "unauthorized."

### Traceability

| Goal | Stories |
| ---- | ------- |
| 1. Record a holding | DASH-1, DASH-6 |
| 2. Import from a broker | DASH-2 |
| 3. Value and gain/loss | DASH-3 |
| 4. Allocation | DASH-4 |
| 5. Watchlist | DASH-5 |

No story implements a non-goal.

---

## 5. C4 System Context view

<img width="5309" height="1707" alt="SD Lab 1-2026-09-16-085613" src="https://github.com/user-attachments/assets/f9122e3f-6686-486a-b851-0a5f0cdfa796" />


### System boundary

| Inside the Dashboard boundary | Outside the Dashboard boundary |
| ----------------------------- | ------------------------------ |
| Validate and store the User's manual holdings and watchlist | The User supplies symbols, quantities, and purchase prices |
| Request and interpret imported holdings | The Brokerage owns account holdings and decides whether access is granted |
| Request and interpret prices | The Market Data Provider owns prices, symbol coverage, and delay |
| Calculate value, gain or loss, and allocation | The User decides whether to buy or sell |
| Label results as current, stale, unsupported, unavailable, or unauthorized | Trades and money movement happen in the brokerage, outside the Dashboard |

### External dependency check

| External system | Dashboard responsibility that needs it | Source result it supplies | What the User sees when the result is missing, stale, or unsupported |
| --------------- | -------------------------------------- | ------------------------- | -------------------------------------------------------------------- |
| Market Data Provider | Validate symbols; value holdings; show watchlist prices (DASH-1, 3, 4, 5) | Symbol details; latest price with price time | Unknown symbol: "not supported." Old price: "stale" with price time. No price: "price unavailable," holding excluded, total marked incomplete. |
| Brokerage | Import holdings (DASH-2) | Holdings with quantity and, if available, purchase cost | Access denied: "reconnection needed," last import shown with its time. Unsupported position: "not imported: unsupported." Missing cost: gain or loss "unknown." |

The external systems own their source results. The Dashboard owns how those results are labeled so that an old, missing, or unsupported result is never shown as a current, successful one.
