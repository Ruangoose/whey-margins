"""Checks on the study's arithmetic and parsing, on synthetic data (no downloads)."""
import numpy as np
import pandas as pd
import pytest

from protein import analysis, edgar, usda


def _durations(rows):
    df = pd.DataFrame(rows, columns=["start", "end", "val"])
    df["start"], df["end"] = pd.to_datetime(df["start"]), pd.to_datetime(df["end"])
    df["days"] = (df["end"] - df["start"]).dt.days + 1
    return df


def test_fourth_quarter_from_year_less_nine_months():
    d = _durations([("2024-10-01", "2024-12-31", 10), ("2025-01-01", "2025-03-31", 11),
                    ("2025-04-01", "2025-06-30", 12), ("2024-10-01", "2025-06-30", 33),
                    ("2024-10-01", "2025-09-30", 50)])
    q = edgar.quarterly(d)
    assert q[pd.Timestamp("2025-09-30")] == 17


def test_quarters_from_year_to_date_totals():
    # Cash-flow style: only 3, 6 and 9 months to date
    d = _durations([("2024-10-01", "2024-12-31", 4), ("2024-10-01", "2025-03-31", 9),
                    ("2024-10-01", "2025-06-30", 15)])
    q = edgar.quarterly(d)
    assert list(q.values) == [4, 5, 6]


def test_wpc_report_parsing_text_and_pdf_styles():
    old = ("Information for the period November 18 - 22, 2019, issued weekly "
           "Price Range - 34% Protein; $/LB:  .7500 - 1.1100  Mostly Range - 34% Protein; $/LB: .8800 - 1.0500")
    new = ("Information for the period April 7 - 11, 2025, issued weekly\nPrice Range - 34% Protein; $/LB: \n"
           "1.7000 - 1.8600 \nMostly Range - 34% Protein; $/LB: \n1.8000 - 1.8575")
    a, b = usda.parse_wpc_report(old), usda.parse_wpc_report(new)
    assert a["week_end"] == pd.Timestamp("2019-11-22") and (a["mostly_lo"], a["mostly_hi"]) == (0.88, 1.05)
    assert b["week_end"] == pd.Timestamp("2025-04-11") and b["range_hi"] == 1.86
    span = "Information for the period March 30 - April 3, 2020 Mostly Range - 34% Protein; $/LB: 1.0 - 1.1"
    assert usda.parse_wpc_report(span)["week_end"] == pd.Timestamp("2020-04-03")


def test_quarter_months_for_13_week_quarters():
    monthly = pd.Series(range(1, 13), index=pd.date_range("2025-01-01", periods=12, freq="MS"), dtype=float)
    # A quarter ending 1 March covers December to February: only Jan and Feb are in the data
    q = analysis.over_quarters(monthly, pd.DatetimeIndex(["2025-03-01", "2025-05-31"]))
    assert q.iloc[0] == pytest.approx(1.5) and q.iloc[1] == pytest.approx(4.0)


def test_lag_profile_recovers_a_known_lag():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2015-03-31", periods=40, freq="QE")
    price = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.1, 40))), index=idx)
    dp = np.log(price).diff(4) * 100
    dgm = -0.05 * dp.shift(2) + rng.normal(0, 0.05, 40)
    gm = pd.Series(0.35, index=idx)
    # Build a margin whose year-on-year change is dgm (in points)
    for i in range(4, 40):
        gm.iloc[i] = gm.iloc[i - 4] + (dgm.iloc[i] if not np.isnan(dgm.iloc[i]) else 0) / 100
    prof = analysis.lag_profile(gm, price, 4)
    assert int(prof.loc[prof["t"].idxmin(), "lag"]) == 2
    assert int(prof.loc[prof["corr"].idxmin(), "lag"]) == 2


def test_lag_fit_matches_the_lag_profile_and_stays_in_the_past():
    rng = np.random.default_rng(1)
    idx = pd.date_range("2015-03-31", periods=40, freq="QE")
    monthly = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.05, 120))),
                        index=pd.date_range("2015-01-01", periods=120, freq="MS"))
    gm = pd.Series(0.35 + rng.normal(0, 0.01, 40), index=idx)
    actual, fitted, (slope, _) = analysis.lag_fit(gm, monthly, 3)
    prof = analysis.lag_profile(gm, analysis.over_quarters(monthly, idx), 3)
    assert slope * 10 == pytest.approx(prof.set_index("lag").loc[3, "beta_per_10pct"])
    assert fitted.index.max() <= idx.max() and fitted.index.equals(actual.index)


def test_contiguous_drops_early_gaps():
    s = pd.Series(1.0, index=pd.DatetimeIndex(["2017-02-25", "2017-11-25", "2018-02-24", "2018-05-26"]))
    assert analysis.contiguous(s).index[0] == pd.Timestamp("2017-11-25")


def test_reaction_day_after_close_is_next_session():
    sessions = pd.DatetimeIndex(["2026-08-04", "2026-08-05"])
    assert analysis.reaction_day(pd.Timestamp("2026-08-04 07:02"), False, sessions) == sessions[0]
    assert analysis.reaction_day(pd.Timestamp("2026-08-04 17:10"), True, sessions) == sessions[1]
