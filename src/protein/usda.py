"""USDA whey prices, production, stocks and trade.

- Dry whey: the National Dairy Products Sales Report (AMS), weekly from March 2012, from
  the keyless MPR Datamart. Each report repeats about five weeks; the latest report wins.
- WPC 34%: Dairy Market News (DMN) weekly "mostly" price range for the Central and
  West US. Monthly averages for 2022 on come from DMN's own table (dymawpc.pdf); earlier
  months are averaged from the weekly reports archived on ESMIS (November 2018 to
  September 2025), and checked against DMN's table where they overlap.
- WPC 80% and isolate have no USDA price series: DMN quotes them only in words, from
  May 2026 (see data/dmn-wpc80-isolate-2026.csv).
- Production, stocks, trade and domestic use: ERS "Supply and utilization of dairy
  product categories", monthly from January 2011.
"""
from __future__ import annotations

import io
import json
import re

import numpy as np
import pandas as pd
from pypdf import PdfReader

from .fetch import get

UA = {"User-Agent": "Mozilla/5.0 (research script)"}


NDPSR = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2993/"


def ndpsr_weekly(section: str, field: str, name: str, start: str = "03/01/2012", end: str = "10/17/2026",
                 refresh: bool = False) -> pd.Series:
    """One price from the National Dairy Products Sales Report, by the week it covers."""
    url = NDPSR + section.replace(" ", "%20") + f"?q=week_ending_date={start}:{end}"
    rows = json.loads(get(url, "usda", suffix=".json", headers=UA, refresh=refresh))["results"]
    df = pd.DataFrame(rows)
    df["report"] = pd.to_datetime(df["week_ending_date"], format="%m/%d/%Y")
    df["week"] = pd.to_datetime(df["Week Ending Date"], format="%m/%d/%Y")
    df["price"] = pd.to_numeric(df[field], errors="coerce")
    df = df.dropna(subset=["price"]).sort_values(["week", "report"]).drop_duplicates("week", keep="last")
    return df.set_index("week")["price"].rename(name)


def dry_whey_weekly(refresh: bool = False) -> pd.Series:
    return ndpsr_weekly("Dry Whey Prices and Sales", "whey_Price", "dry_whey", refresh=refresh)


def nonfat_dry_milk_weekly(refresh: bool = False) -> pd.Series:
    """Nonfat dry milk: the price that milk protein concentrate (in ready-to-drink shakes) tracks."""
    return ndpsr_weekly("Nonfat Dry Milk Prices and Sales", "nonfat_milk_Price", "nonfat_dry_milk", refresh=refresh)


def _pdf_text(body: bytes) -> str:
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(body)).pages)


def wpc34_monthly_dmn(refresh: bool = False) -> pd.Series:
    """DMN's table of monthly average 'mostly' prices for WPC 34%, 2022 to date."""
    text = _pdf_text(get("https://www.ams.usda.gov/mnreports/dymawpc.pdf", "usda", suffix=".pdf",
                         headers=UA, refresh=refresh))
    out = {}
    for line in text.splitlines():
        m = re.match(r"^(20\d\d)\s+(.*)$", line.strip())
        if not m:
            continue
        vals = m.group(2).split()
        for i, v in enumerate(vals[:12]):
            if re.match(r"^\d+\.\d+$", v):
                out[pd.Timestamp(int(m.group(1)), i + 1, 1)] = float(v)
    return pd.Series(out, name="wpc34").sort_index()


ESMIS = "https://esmis.nal.usda.gov"
ESMIS_WPC = ESMIS + "/publication/whey-protein-concentrate-central-and-western-us"


def _esmis_files(refresh: bool = False, max_pages: int = 60) -> list[str]:
    """Every weekly WPC report file on ESMIS (text where there is one, otherwise PDF)."""
    files, seen_pages = [], set()
    for page in range(max_pages):
        body = get(ESMIS_WPC, "usda-esmis", suffix=f"-p{page}.html", headers=UA,
                   params={"page": page}, refresh=refresh).decode("utf-8", errors="ignore")
        links = re.findall(r'href="(/sites/default/release-files/[^"]+\.(?:txt|pdf))"', body, re.I)
        # Each release folder holds one report, sometimes as both text and PDF.
        by_folder = {}
        for l in links:
            folder = l.rsplit("/", 1)[0]
            if l.lower().endswith(".txt") or folder not in by_folder:
                by_folder[folder] = l
        new = [l for f, l in by_folder.items() if f not in seen_pages]
        if not new:
            break
        seen_pages.update(by_folder)
        files += new
    return files


PERIOD = re.compile(r"period\s+([A-Z][a-z]+)\s+(\d{1,2})\s*-\s*(?:([A-Z][a-z]+)\s+)?(\d{1,2}),\s*(\d{4})")
MOSTLY = re.compile(r"Mostly Range\s*-\s*34% Protein;\s*\$/LB:\s*([\d.]+)\s*-\s*([\d.]+)", re.I)
RANGE = re.compile(r"Price Range\s*-\s*34% Protein;\s*\$/LB:\s*([\d.]+)\s*-\s*([\d.]+)", re.I)


def parse_wpc_report(text: str) -> dict | None:
    t = re.sub(r"\s+", " ", text)
    p, m = PERIOD.search(t), MOSTLY.search(t)
    if not p or not m:
        return None
    end_month = p.group(3) or p.group(1)
    week_end = pd.to_datetime(f"{end_month} {p.group(4)} {p.group(5)}", format="%B %d %Y", errors="coerce")
    if pd.isna(week_end):
        return None
    r = RANGE.search(t)
    return {"week_end": week_end, "mostly_lo": float(m.group(1)), "mostly_hi": float(m.group(2)),
            "range_lo": float(r.group(1)) if r else np.nan, "range_hi": float(r.group(2)) if r else np.nan}


def wpc34_weekly_esmis(refresh: bool = False) -> pd.DataFrame:
    rows = []
    for path in _esmis_files(refresh):
        try:
            body = get(ESMIS + path, "usda-esmis", suffix="." + path.rsplit(".", 1)[1].lower(), headers=UA,
                       refresh=refresh, pause=0.2)
        except RuntimeError:  # the listing carries a few dead links (the 'latest report' file)
            continue
        text = body.decode("latin-1") if path.lower().endswith(".txt") else _pdf_text(body)
        row = parse_wpc_report(text)
        if row:
            row["file"] = path
            rows.append(row)
    df = pd.DataFrame(rows).drop_duplicates("week_end").sort_values("week_end").set_index("week_end")
    df["mostly_mid"] = (df["mostly_lo"] + df["mostly_hi"]) / 2
    return df


def wpc34_monthly(refresh: bool = False) -> tuple[pd.Series, pd.DataFrame]:
    """Monthly WPC 34% 'mostly' price: DMN's table from 2022, weekly-report averages before.

    Returns the joined series and the overlap check (both sources, 2022 on).
    """
    dmn = wpc34_monthly_dmn(refresh)
    weekly = wpc34_weekly_esmis(refresh)
    # DMN averages the daily mostly range over the month; weeks are assigned by their last day.
    from_weekly = weekly["mostly_mid"].groupby(weekly.index.to_period("M")).mean()
    from_weekly.index = from_weekly.index.to_timestamp()
    check = pd.concat([dmn, from_weekly], axis=1, keys=["dmn_table", "weekly_avg"]).dropna()
    joined = dmn.combine_first(from_weekly[from_weekly.index < dmn.index.min()])
    return joined.rename("wpc34"), check


def ers_supply_use(refresh: bool = False) -> pd.DataFrame:
    url = ("https://www.ers.usda.gov/media/5505/"
           "supply-and-utilization-of-dairy-product-categories-monthly-and-annual.csv")
    df = pd.read_csv(io.BytesIO(get(url, "usda", suffix=".csv", headers=UA, refresh=refresh)))
    df = df[df["Frequency"] == "Monthly"].copy()
    df["date"] = pd.to_datetime(df["Year"].astype(str) + "-" + df["Period"], format="%Y-%B")
    return df


def ers_series(df: pd.DataFrame, product: str, item: str) -> pd.Series:
    s = df[(df["Product"] == product) & (df["Data_item"] == item)].set_index("date")["Quantity"]
    return s.sort_index().rename(f"{product}: {item}")
