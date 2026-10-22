# whey-margins

When US dairy protein prices rose sharply in 2025 and 2026, how hard and how fast did they hit the gross
margins of the brands that buy them? A study on public data: USDA dairy prices, production and stocks, and SEC
filings for BellRing Brands and The Simply Good Foods Company.

A few summary statistics on the two shares come from Alpaca's market data, which is for personal use only, so no
share price or return series is published here.

The write-up: https://ruangoosen.co.za/projects/protein-squeeze/

## Rerun
```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest -q      # checks on synthetic data, no downloads
.venv\Scripts\python run.py --refresh  # downloads everything, then writes output/
.venv\Scripts\python run.py            # reruns from the downloads in data/raw/
```
Downloading needs two things:
- a free Alpaca key pair in `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`;
- your name and email in `SEC_USER_AGENT` (for example `Jane Doe jane@example.com`): the SEC asks every
  script to name a contact.

Share prices end on 20 October 2026 (`END` in `run.py`); USDA and SEC data are as published when downloaded.
The committed output used downloads of 21 October 2026. A fresh download on 22 October gave the same results
apart from USDA's newer week.
On Windows, keep the clone at a short path: with long paths switched off, pip can install statsmodels
incompletely without an error.

## Method
- **Prices:** monthly averages of the weekly USDA prices. Each company quarter takes the average of its three
  months.
- **Margins:** quarterly gross margin from SEC XBRL filings. Fourth quarters are the year less the first nine
  months.
- **The lag:** the year-on-year change in gross margin (points) against the year-on-year change in each price
  (log, %), 0 to 6 quarters earlier, by ordinary least squares with Newey-West standard errors (four lags).
  Year-on-year changes take out seasonality.
- **The shares:** the fall from the peak, EV/EBITDA now against its 2023–24 average, and moves on results days
  over their first two sessions: the typical move, and the average move against a US consumer staples ETF
  (XLP), split by whether the release mentions protein or ingredient costs. Only these summary figures are
  written.

The study describes the past. It fits nothing forward and makes no recommendation.

## Output
- `protein-prices-monthly.csv`: WPC 34%, nonfat dry milk and dry whey, monthly averages, $/lb.
- `wpc34-check.csv`: WPC 34% from Dairy Market News' monthly table against the average of its weekly reports.
- `whey-supply-monthly.csv`: US whey stocks and exports, million lb.
- `buyer-margins-quarterly.csv`: revenue, cost of goods, gross profit and margin, EPS and net income by quarter.
- `margin-lag-profiles.csv`: the lag regressions, every company, price and lag.
- `results.json`: every headline figure, the share statistics included.
- `site/`: the JSON the web page is built from.
- `charts/`: rough PNG charts for review.

See [SOURCES.md](SOURCES.md) for every source, its terms and its limits. Raw downloads stay in `data/raw/`
(git-ignored).

Code: MIT licence. Ruan Goosen. Not investment advice.
