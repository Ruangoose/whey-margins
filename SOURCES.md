# Sources and terms

Checked 21 and 22 October 2026.

| Source | What | Route | Terms |
|---|---|---|---|
| USDA AMS, National Dairy Products Sales Report | Weekly dry whey and nonfat dry milk prices, March 2012 on | MPR Datamart (report 2993), no key | No restrictions on use; USDA data shown as USDA data must not be altered |
| USDA AMS, Dairy Market News | WPC 34% "mostly" price, Central and West US: monthly table for 2022 on (`dymawpc.pdf`); weekly reports November 2018 to September 2025 from the ESMIS archive, averaged by month for earlier years. WPC 80% and isolate quotes in words, May to October 2026 (`data/dmn-wpc80-isolate-2026.csv`) | ams.usda.gov, esmis.nal.usda.gov, no key | Public domain (USDA policy); credit "U.S. Department of Agriculture" |
| USDA ERS | Supply and utilization of dairy product categories: WPC and dry whey production, stocks, exports, monthly from 2011 | ers.usda.gov CSV, no key | Public domain (USDA policy) |
| SEC EDGAR | Quarterly sales, cost of goods, gross profit, operating income, D&A, impairments, EPS, debt, cash, shares (XBRL company facts); results releases (8-K item 2.02, and item 9.01 alone when the exhibit announces results) | `data.sec.gov` and `sec.gov/Archives`, no key; a User-Agent naming a contact is required | US government work, public domain; fair-access limit of 10 requests a second |
| Alpaca market data | Daily bars since 2016 for BRBR, SMPL and XLP (consolidated SIP feed, adjusted for splits, dividends and spin-offs) | `data.alpaca.markets`, free key pair | Personal, non-commercial use; nothing may be republished without Alpaca's written consent. Used only for summary statistics: raw prices, and any series built from them, are never committed or published |

Not used: CME whey futures (licensed data), and Yahoo, S&P, MSCI, ICE, AQR and JSE data.

## Limits
- There is no public price history for WPC 80%, whey protein isolate or milk protein concentrate, the proteins the
  brands mostly buy. Dry whey, WPC 34% and nonfat dry milk are proxies.
- Gross margin moves with much more than protein costs: selling prices, promotions, product mix, packaging,
  freight, and any hedges or fixed-price contracts.
- About 20 to 30 quarters per regression, and the lag is chosen as the one that fits best, which flatters the
  fit.
- BellRing was an Up-C until its spin-off from Post in March 2022: cover-page share counts before then cover
  Class A only, so its valuation starts in 2022.
- Simply Good Foods' first filings (2016–17) skip quarters; its lag tests start in November 2017.
