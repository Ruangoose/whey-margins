"""Rerun the whole study: download (or read the cache), compute, and write output/.

    python run.py            # uses data/raw/ when it's there
    python run.py --refresh  # downloads everything again

Share prices end on END; filings and USDA data are as published when downloaded. The study describes the
past: it fits nothing forward and makes no recommendation. Share prices (Alpaca, personal use only) feed a
few summary statistics; no price or return series is written to output/.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))
from protein import analysis, charts, edgar, prices, releases, usda  # noqa: E402

ROOT = Path(__file__).parent
OUT = ROOT / "output"
SITE = OUT / "site"
END = "2026-10-20"
BUYERS = ["BRBR", "SMPL"]
MAX_LAG = 6


def day(ts) -> str:
    return str(pd.Timestamp(ts).date())


def num(v, d: int = 4):
    """A float rounded for JSON, or None for a gap."""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), d)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, default=str, allow_nan=False) + "\n", newline="\n")


def main(refresh: bool = False) -> None:
    (OUT / "charts").mkdir(parents=True, exist_ok=True)
    SITE.mkdir(parents=True, exist_ok=True)
    results: dict = {"end": END}

    # 1. Protein prices
    ndm = usda.nonfat_dry_milk_weekly(refresh)
    dw = usda.dry_whey_weekly(refresh)
    wpc34, wpc_check = usda.wpc34_monthly(refresh)
    monthly = pd.concat({"wpc34": wpc34, "nonfat_dry_milk": ndm.resample("MS").mean(),
                         "dry_whey": dw.resample("MS").mean()}, axis=1, sort=True).loc["2016-01-01":]
    monthly.round(4).to_csv(OUT / "protein-prices-monthly.csv")
    wpc_check.round(4).to_csv(OUT / "wpc34-check.csv")
    quotes = pd.read_csv(ROOT / "data" / "dmn-wpc80-isolate-2026.csv", parse_dates=["report_date"],
                         index_col="report_date")
    charts.protein_prices(monthly, quotes, OUT / "charts" / "1-protein-prices.png")
    before_2026 = wpc34.loc[:"2025-12"]
    results["prices"] = {
        "wpc34_first_month": day(wpc34.index[0]),
        "wpc34_latest_month": [day(wpc34.index[-1]), num(wpc34.iloc[-1])],
        "wpc34_max_before_2026": [day(before_2026.idxmax()), num(before_2026.max())],
        "ndm_first_week": day(ndm.index[0]),
        "ndm_latest_week": [day(ndm.index[-1]), num(ndm.iloc[-1])],
        "ndm_max": [day(ndm.idxmax()), num(ndm.max())],
        "ndm_2026_low": [day(ndm.loc["2026-06":].idxmin()), num(ndm.loc["2026-06":].min())],
        "dry_whey_latest_week": [day(dw.index[-1]), num(dw.iloc[-1])],
        "dry_whey_max": [day(dw.idxmax()), num(dw.max())],
        "wpc34_weekly_vs_table_mean_abs_diff": num((wpc_check.diff(axis=1).iloc[:, 1]).abs().mean()),
        "quotes": {"first": day(quotes.index[0]), "last": day(quotes.index[-1]),
                   "wpc80_first": [num(quotes["wpc80_lo"].iloc[0], 2), num(quotes["wpc80_hi"].iloc[0], 2)],
                   "wpc80_last": [num(quotes["wpc80_lo"].iloc[-1], 2), num(quotes["wpc80_hi"].iloc[-1], 2)],
                   "wpc80_top": num(quotes["wpc80_hi"].max(), 2),
                   "isolate_last": [num(quotes["wpi_lo"].iloc[-1], 2), num(quotes["wpi_hi"].iloc[-1], 2)]},
    }

    # 2. Supply: ERS production, stocks and exports
    ers = usda.ers_supply_use(refresh)
    wpc = "Whey protein concentrate (WPC)"
    supply = {
        "WPC ending stocks, human use": usda.ers_series(ers, wpc, "Ending manufacturers' stocks, for human use"),
        "WPC exports, 12-month total": usda.ers_series(ers, wpc, "Exports").rolling(12).sum(),
        "Dry whey ending stocks, human use": usda.ers_series(ers, "Dry whey", "Ending manufacturers' stocks, for human use"),
    }
    pd.DataFrame(supply).round(3).to_csv(OUT / "whey-supply-monthly.csv")
    charts.stocks(supply, OUT / "charts" / "2-whey-stocks.png")
    results["supply"] = {k: {"latest": [day(s.dropna().index[-1]), num(s.dropna().iloc[-1], 1)],
                             "year_earlier": num(s.dropna().iloc[-13], 1)} for k, s in supply.items()}

    # 3. Margins against lagged input prices
    ciks = edgar.ticker_ciks(refresh)
    margins = {t: edgar.margins(t, ciks[t], refresh) for t in BUYERS}
    pd.concat(margins.values()).round(4).to_csv(OUT / "buyer-margins-quarterly.csv")
    inputs = {"WPC 34%": wpc34, "nonfat dry milk": ndm.resample("MS").mean(), "dry whey": dw.resample("MS").mean()}
    profiles = {}
    for t in BUYERS:
        gm = analysis.contiguous(margins[t]["gross_margin"])  # SMPL's first filings skip quarters
        for name, px in inputs.items():
            lp = analysis.lag_profile(gm, analysis.over_quarters(px, gm.index), MAX_LAG)
            lp.insert(0, "input", name)
            lp.insert(0, "ticker", t)
            profiles[(t, name)] = lp
    lags = pd.concat(profiles.values(), ignore_index=True)
    lags.round(3).to_csv(OUT / "margin-lag-profiles.csv", index=False)
    # For each price, the lag at which it and the margin move most closely together (the most negative
    # correlation of year-on-year changes); then, for each company, the price that fits best.
    by_input = lags.loc[lags.groupby(["ticker", "input"], sort=False)["corr"].idxmin()]
    best = by_input.loc[by_input.groupby("ticker", sort=False)["corr"].idxmin()]
    panels, fits = [], {}
    for row in best.itertuples():
        gm = analysis.contiguous(margins[row.ticker]["gross_margin"])
        actual, fitted, (slope, _) = analysis.lag_fit(gm, inputs[row.input], int(row.lag))
        panels.append((f"{row.ticker} gross margin vs {row.input}\nlagged {row.lag} quarters "
                       f"(R² {row.r2:.2f}, t {row.t:.1f})", actual, fitted))
        fits[row.ticker] = {"input": row.input, "lag": int(row.lag), "n": int(row.n), "r2": num(row.r2, 3),
                            "t": num(row.t, 2), "points_per_10pct": num(slope * 10, 3),
                            "quarters": [day(q) for q in actual.index],
                            "actual": [num(v, 3) for v in actual], "fitted": [num(v, 3) for v in fitted]}
    charts.margin_fit(panels, OUT / "charts" / "3-margins-vs-inputs.png")
    results["lags"] = by_input.round(3).to_dict("records")
    results["best_fit"] = {t: {k: v for k, v in f.items() if k not in ("quarters", "actual", "fitted")}
                           for t, f in fits.items()}
    margin_summary = {}
    for t in BUYERS:
        g = margins[t]["gross_margin"].loc["2019-01-01":]
        recent = g.loc["2023-01-01":]
        margin_summary[t] = {"last": [day(g.index[-1]), num(g.iloc[-1])],
                             "year_earlier": [day(g.index[-5]), num(g.iloc[-5])],
                             "high_since_2023": [day(recent.idxmax()), num(recent.max())],
                             "low_since_2023": [day(recent.idxmin()), num(recent.min())]}
    results["margins"] = margin_summary

    # 4. The shares: summary statistics only. Alpaca's terms allow personal use, so no price or return
    # series, and no per-day or per-quarter table, leaves this function.
    px = prices.closes(BUYERS + ["XLP"], "2016-01-01", END, refresh)
    shares = {}
    for t in BUYERS:
        s = px[t].dropna()
        rel = s / px["XLP"].reindex(s.index)
        peak = s.idxmax()
        f = edgar.fundamentals(ciks[t], refresh)
        so = edgar.shares_outstanding(ciks[t], refresh)
        f["ebitda_ttm"] = (f["op_income"] + f["da"].fillna(f["da"].median()) + f["impairments"]).rolling(4).sum()
        # BellRing was an Up-C until its spin-off from Post in March 2022: cover-page shares then counted only
        # Class A, so market value before 2022 is understated. Its valuation starts in 2022.
        start = "2022-03-31" if t == "BRBR" else "2019-01-01"
        ev = {}
        for qe in f.index[f.index >= start]:
            sh = so.loc[:qe + pd.Timedelta(days=60)]
            p = s.loc[:qe]
            if len(sh) and len(p) and f.loc[qe, "ebitda_ttm"] > 0:
                ev[qe] = (p.iloc[-1] * sh.iloc[-1] + f.loc[qe, "debt"] - f.loc[qe, "cash"]) / f.loc[qe, "ebitda_ttm"]
        last = f.index[-1]
        ev_now = (s.iloc[-1] * so.iloc[-1] + f.loc[last, "debt"] - f.loc[last, "cash"]) / f.loc[last, "ebitda_ttm"]
        ev = pd.Series(ev)
        events = analysis.event_returns(s, px["XLP"], releases.scan(t, ciks[t]), window=(0, 1))
        protein = events["n_hits"] > 0
        shares[t] = {
            "peak": day(peak),
            "from_peak_pct": num((s.iloc[-1] / s.max() - 1) * 100, 1),
            "vs_staples_from_peak_pct": num((rel.iloc[-1] / rel.loc[peak] - 1) * 100, 1),
            "ev_ebitda_now": num(ev_now, 1),
            "ev_ebitda_mean_2023_24": num(ev.loc["2023-01-01":"2024-12-31"].mean(), 1),
            "ev_ebitda_quarters_2023_24": int(ev.loc["2023-01-01":"2024-12-31"].count()),
            "results_days": {
                "n": len(events), "first": day(events["reaction_day"].min()), "last": day(events["reaction_day"].max()),
                "mean_move_pct": num(events["raw"].mean() * 100, 1),
                "rms_move_pct": num(np.sqrt((events["raw"] ** 2).mean()) * 100, 1),
                "protein_cost": {"n": int(protein.sum()), "mean_vs_staples_pct": num(events.loc[protein, "car"].mean() * 100, 1)},
                "other": {"n": int((~protein).sum()), "mean_vs_staples_pct": num(events.loc[~protein, "car"].mean() * 100, 1)},
            },
        }
    results["shares"] = shares

    write_json(OUT / "results.json", results)

    # 5. What the web page (ruangoosen.co.za/projects/protein-squeeze/) is built from: the figures above, the
    # price and margin series, and the lag profiles.
    lag_table = {t: {name: [{"lag": int(r.lag), "n": int(r.n), "r2": num(r.r2, 3), "corr": num(r.corr, 3),
                             "points_per_10pct": num(r.beta_per_10pct, 3), "t": num(r.t, 2)}
                            for r in profiles[(t, name)].itertuples()] for name in inputs} for t in BUYERS}
    write_json(SITE / "summary.json", {**results, "lag_profiles": lag_table})
    m = monthly.loc[:END]
    write_json(SITE / "prices.json", {
        "months": [str(d)[:7] for d in m.index],
        **{c: [num(v) for v in m[c]] for c in m.columns},
        "quotes": [{"date": day(d), "wpc80": [num(q.wpc80_lo, 2), num(q.wpc80_hi, 2)],
                    "isolate": [num(q.wpi_lo, 2), num(q.wpi_hi, 2)]} for d, q in quotes.iterrows()],
    })
    write_json(SITE / "margins.json", {
        **{t: {"quarters": [day(q) for q in margins[t].loc["2019-01-01":].index],
               "gross_margin": [num(v) for v in margins[t].loc["2019-01-01":, "gross_margin"]]} for t in BUYERS},
        "fits": fits,
    })
    # Unix line endings everywhere, so a rerun on Windows shows no changes in git.
    for p in OUT.glob("*.csv"):
        p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n"))
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
