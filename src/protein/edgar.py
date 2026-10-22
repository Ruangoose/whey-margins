"""Quarterly sales, cost of goods and gross margin from SEC XBRL company facts.

10-Qs report three-month figures; 10-Ks report only the year, so the fourth
quarter is the year less the nine months to the third quarter (or less the
three quarters, when the nine-month figure is missing). Companies switch tags
over time, so each line merges several us-gaap concepts, latest filing first.
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from .fetch import sec_get

REVENUE = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
           "SalesRevenueGoodsNet", "RevenueFromContractWithCustomerIncludingAssessedTax"]
COGS = ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"]
GROSS = ["GrossProfit"]


def ticker_ciks(refresh: bool = False) -> dict[str, int]:
    data = json.loads(sec_get("https://www.sec.gov/files/company_tickers.json", refresh))
    return {v["ticker"]: int(v["cik_str"]) for v in data.values()}


def company_facts(cik: int, refresh: bool = False) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    return json.loads(sec_get(url, refresh))


def durations(facts: dict, concepts: list[str], unit: str = "USD") -> pd.DataFrame:
    """Every (start, end) value of the concepts, keeping the latest filing of each period.

    Concepts are tried in order: a period already covered by an earlier concept
    keeps that concept's value.
    """
    rows = []
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for rank, c in enumerate(concepts):
        for u in gaap.get(c, {}).get("units", {}).get(unit, []):
            if "start" not in u or u.get("form", "").split("/")[0] not in ("10-Q", "10-K", "10-KT"):
                continue
            rows.append({"start": u["start"], "end": u["end"], "val": float(u["val"]),
                         "filed": u["filed"], "rank": rank, "concept": c})
    if not rows:
        return pd.DataFrame(columns=["start", "end", "val", "days", "concept"])
    df = pd.DataFrame(rows)
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    df = (df.sort_values(["start", "end", "rank", "filed"], ascending=[True, True, True, False])
            .drop_duplicates(["start", "end"]))
    df["days"] = (df["end"] - df["start"]).dt.days + 1
    return df[["start", "end", "val", "days", "concept"]].reset_index(drop=True)


def quarterly(d: pd.DataFrame) -> pd.Series:
    """Three-month values by quarter end, deriving fourth quarters from annual totals.

    Cash-flow items are often reported only year to date (3, 6, 9, 12 months from the
    fiscal year's start); their quarters are the differences between successive totals.
    """
    q = d[(d["days"] >= 80) & (d["days"] <= 100)]
    out = {row.end: (row.start, row.val) for row in q.itertuples()}
    bands = [(80, 100), (170, 195), (260, 285)]
    for start, grp in d.groupby("start"):
        ytd = []
        for lo, hi in bands:
            g = grp[(grp["days"] >= lo) & (grp["days"] <= hi)]
            ytd.append(g.iloc[0] if len(g) else None)
        for prev, cur in zip(ytd, ytd[1:]):
            if prev is not None and cur is not None and cur["end"] not in out:
                out[cur["end"]] = (prev["end"] + pd.Timedelta(days=1), cur["val"] - prev["val"])
    for yr in d[(d["days"] >= 350) & (d["days"] <= 380)].itertuples():
        # The quarter ending on the year's last day already reported: nothing to do.
        if yr.end in out:
            continue
        nine = d[(d["start"] == yr.start) & (d["days"] >= 260) & (d["days"] <= 285) & (d["end"] < yr.end)]
        if len(nine):
            n = nine.iloc[0]
            out[yr.end] = (n["end"] + pd.Timedelta(days=1), yr.val - n["val"])
            continue
        inside = [(e, v) for e, (s, v) in out.items() if s >= yr.start and e < yr.end]
        if len(inside) == 3:
            last = max(e for e, _ in inside)
            out[yr.end] = (last + pd.Timedelta(days=1), yr.val - sum(v for _, v in inside))
    if not out:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    s = pd.Series({e: v for e, (st, v) in out.items()}).sort_index()
    starts = pd.Series({e: st for e, (st, v) in out.items()}).sort_index()
    # Keep true quarters only (a derived Q4 must also span roughly three months).
    span = (s.index - pd.DatetimeIndex(starts.values)).days + 1
    return s[(span >= 80) & (span <= 100)]


def submissions(cik: int, refresh: bool = False) -> pd.DataFrame:
    """Every filing in the SEC's submissions index for a company (recent and older pages)."""
    base = "https://data.sec.gov/submissions/"
    js = json.loads(sec_get(f"{base}CIK{cik:010d}.json", refresh))
    frames = [pd.DataFrame(js["filings"]["recent"])]
    for extra in js["filings"].get("files", []):
        frames.append(pd.DataFrame(json.loads(sec_get(base + extra["name"], refresh))))
    df = pd.concat(frames, ignore_index=True)
    df["filingDate"] = pd.to_datetime(df["filingDate"])
    return df


def earnings_dates(cik: int, refresh: bool = False) -> pd.DataFrame:
    """Results releases: 8-Ks under item 2.02, with the US Eastern time they were accepted.

    A release accepted after 16:00 ET is first traded the next session; one before
    09:30 is traded the same day. The SEC gives acceptance times in UTC; they are
    converted to New York time (SMPL's 7 a.m. releases show as 11:00 UTC in summer).
    """
    df = submissions(cik, refresh)
    items = df["items"].fillna("")
    # Some companies file results under item 9.01 alone (Simply Good Foods in 2024); those are
    # candidates, confirmed from the exhibit's text in releases.results_dates().
    e = df[(df["form"] == "8-K") & (items.str.contains("2.02") | (items == "9.01"))].copy()
    e["item_202"] = items.loc[e.index].str.contains("2.02")
    t = (pd.to_datetime(e["acceptanceDateTime"], utc=True)
           .dt.tz_convert("America/New_York").dt.tz_localize(None))
    e["accepted"] = t
    e["after_close"] = t.dt.hour * 60 + t.dt.minute >= 16 * 60
    e["before_open"] = t.dt.hour * 60 + t.dt.minute < 9 * 60 + 30
    return e[["filingDate", "accepted", "after_close", "before_open", "item_202", "accessionNumber",
              "primaryDocument"]].sort_values("accepted").reset_index(drop=True)


def margins(ticker: str, cik: int, refresh: bool = False) -> pd.DataFrame:
    """Quarterly revenue, cost of goods, gross profit and gross margin for one company."""
    f = company_facts(cik, refresh)
    rev = quarterly(durations(f, REVENUE))
    cogs = quarterly(durations(f, COGS))
    gp = quarterly(durations(f, GROSS))
    df = pd.DataFrame({"revenue": rev, "cogs": cogs, "gross_reported": gp})
    df["gross"] = df["gross_reported"].fillna(df["revenue"] - df["cogs"])
    df["cogs"] = df["cogs"].fillna(df["revenue"] - df["gross_reported"])
    df["gross_margin"] = df["gross"] / df["revenue"]
    df = df.dropna(subset=["revenue", "gross"])
    df["eps_diluted"] = quarterly(durations(f, ["EarningsPerShareDiluted"], "USD/shares"))
    df["net_income"] = quarterly(durations(f, ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]))
    df.index.name = "quarter_end"
    df.insert(0, "ticker", ticker)
    return df.drop(columns="gross_reported")


def instants(facts: dict, concepts: list[str]) -> pd.Series:
    """Balance-sheet values (point in time) by date, merging concepts in order of preference."""
    rows = []
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for rank, c in enumerate(concepts):
        for u in gaap.get(c, {}).get("units", {}).get("USD", []):
            if "start" in u or u.get("form", "").split("/")[0] not in ("10-Q", "10-K", "10-KT"):
                continue
            rows.append({"end": u["end"], "val": float(u["val"]), "filed": u["filed"], "rank": rank})
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    df["end"] = pd.to_datetime(df["end"])
    df = df.sort_values(["end", "rank", "filed"], ascending=[True, True, False]).drop_duplicates("end")
    return df.set_index("end")["val"]


def fundamentals(cik: int, refresh: bool = False) -> pd.DataFrame:
    """Quarterly operating income, depreciation and amortisation, debt and cash, for EV/EBITDA.

    Debt is total debt where tagged, otherwise long-term plus current portions.
    """
    f = company_facts(cik, refresh)
    op = quarterly(durations(f, ["OperatingIncomeLoss"]))
    da = quarterly(durations(f, ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                                 "DepreciationAmortizationAndAccretionNet"]))
    debt_total = instants(f, ["LongTermDebt", "DebtLongtermAndShorttermCombinedAmount"])
    debt_split = instants(f, ["LongTermDebtNoncurrent"]).add(instants(f, ["LongTermDebtCurrent"]), fill_value=0)
    debt = debt_total.combine_first(debt_split)
    cash = instants(f, ["CashAndCashEquivalentsAtCarryingValue", "Cash"])
    # Write-downs are added back, so EBITDA reflects trading rather than one-off impairments.
    # Goodwill plus intangibles; the intangible tags overlap, so the first one present in a quarter is used.
    goodwill = quarterly(durations(f, ["GoodwillImpairmentLoss"]))
    intangibles = quarterly(durations(f, ["ImpairmentOfIntangibleAssetsExcludingGoodwill",
                                          "ImpairmentOfIntangibleAssetsIndefinitelivedExcludingGoodwill",
                                          "ImpairmentOfIntangibleAssetsFinitelived"]))
    combined = quarterly(durations(f, ["GoodwillAndIntangibleAssetImpairment"]))
    df = pd.DataFrame({"op_income": op, "da": da})
    parts = pd.concat([goodwill, intangibles], axis=1).reindex(df.index).sum(axis=1, min_count=1)
    df["impairments"] = parts.fillna(combined.reindex(df.index)).fillna(0)
    df["debt"] = debt.reindex(df.index)
    df["cash"] = cash.reindex(df.index)
    return df


def shares_outstanding(cik: int, refresh: bool = False) -> pd.Series:
    """Shares outstanding from each filing's cover page (dei), by the date stated."""
    f = company_facts(cik, refresh)
    rows = f.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    s = pd.DataFrame(rows)
    if s.empty:
        return pd.Series(dtype=float)
    s["end"] = pd.to_datetime(s["end"])
    # Several share classes in one filing are added; the same date in several filings keeps the latest.
    per_filing = s.groupby(["end", "accn", "filed"], as_index=False)["val"].sum()
    return per_filing.sort_values("filed").groupby("end")["val"].last().sort_index()
