"""Margins against lagged dairy protein prices, and share moves on results days."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm


def over_quarters(monthly: pd.Series, quarter_ends: pd.DatetimeIndex) -> pd.Series:
    """Average a monthly price (indexed by month) over the three months of each company quarter.

    Fiscal quarters of 13 weeks can end a day or two into a month (2025-03-01), so the
    last month is the one containing the date 15 days before the quarter end.
    """
    m = monthly.copy()
    m.index = m.index.to_period("M")
    out = {}
    for end in quarter_ends:
        last = (end - pd.Timedelta(days=15)).to_period("M")
        months = pd.period_range(last - 2, last, freq="M")
        vals = m.reindex(months)
        out[end] = vals.mean() if vals.notna().sum() >= 2 else np.nan
    return pd.Series(out)


def contiguous(s: pd.Series, max_gap_days: int = 100) -> pd.Series:
    """The last unbroken run of quarters, so that shifting by four rows means a year."""
    gaps = s.index.to_series().diff().dt.days
    breaks = gaps[gaps > max_gap_days]
    return s.loc[breaks.index[-1]:] if len(breaks) else s


def lag_profile(gm: pd.Series, price: pd.Series, max_lag: int = 6) -> pd.DataFrame:
    """Year-on-year change in gross margin (points) on the year-on-year change in log price, lagged k quarters.

    Year-on-year changes take out seasonality. Standard errors are Newey-West with
    four lags, since overlapping annual changes are autocorrelated.
    """
    dgm = (gm - gm.shift(4)) * 100
    dp = np.log(price).diff(4) * 100
    rows = []
    for k in range(max_lag + 1):
        df = pd.concat([dgm, dp.shift(k)], axis=1, keys=["dgm", "dp"]).dropna()
        if len(df) < 8:
            continue
        fit = sm.OLS(df["dgm"], sm.add_constant(df["dp"])).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
        rows.append({"lag": k, "n": len(df), "beta_per_10pct": fit.params["dp"] * 10,
                     "t": fit.tvalues["dp"], "r2": fit.rsquared, "corr": df.corr().iloc[0, 1]})
    return pd.DataFrame(rows)


def lag_fit(gm: pd.Series, monthly: pd.Series, k: int) -> tuple[pd.Series, pd.Series, tuple[float, float]]:
    """Year-on-year margin change, and the change fitted from the input price k quarters earlier.

    Reported quarters only: this is a description of the past, not a projection.
    Returns (actual, fitted, (slope, intercept)).
    """
    gaps = gm.index.to_series().diff().dt.days.dropna()
    if (gaps > 100).any():
        raise ValueError("quarters are missing: year-on-year changes would misalign")
    q = over_quarters(monthly, gm.index)
    dp = (np.log(q).diff(4) * 100).shift(k)
    dgm = (gm - gm.shift(4)) * 100
    df = pd.concat([dgm, dp], axis=1, keys=["dgm", "dp"]).dropna()
    slope, intercept = np.polyfit(df["dp"], df["dgm"], 1)
    return df["dgm"], intercept + slope * df["dp"], (float(slope), float(intercept))


def reaction_day(release: pd.Timestamp, after_close: bool, sessions: pd.DatetimeIndex) -> pd.Timestamp | None:
    """The first session that could trade on a release."""
    day = release.normalize()
    if after_close or release.hour >= 16:
        later = sessions[sessions > day]
    else:
        later = sessions[sessions >= day]
    return later[0] if len(later) else None


def event_returns(prices: pd.Series, bench: pd.Series, events: pd.DataFrame, window: tuple[int, int] = (0, 1),
                  est: tuple[int, int] = (-260, -21)) -> pd.DataFrame:
    """Market-model abnormal returns around results days.

    Beta comes from the estimation window before each event; the abnormal return
    is summed over the event window (sessions relative to the reaction day).
    """
    r = np.log(prices).diff()
    m = np.log(bench).diff()
    data = pd.concat([r, m], axis=1, keys=["r", "m"]).dropna()
    sessions = data.index
    rows = []
    for e in events.itertuples():
        d0 = reaction_day(e.accepted, e.after_close, sessions)
        if d0 is None:
            continue
        i0 = sessions.get_loc(d0)
        if i0 + est[0] < 0 or i0 + window[1] >= len(sessions):
            continue
        est_df = data.iloc[i0 + est[0]: i0 + est[1]]
        fit = sm.OLS(est_df["r"], sm.add_constant(est_df["m"])).fit()
        win = data.iloc[i0 + window[0]: i0 + window[1] + 1]
        ar = win["r"] - (fit.params["const"] + fit.params["m"] * win["m"])
        rows.append({"accepted": e.accepted, "reaction_day": d0, "car": float(ar.sum()),
                     "raw": float(win["r"].sum()), "beta": float(fit.params["m"]),
                     "resid_sd": float(fit.resid.std()), **{k: getattr(e, k) for k in ("n_hits",) if hasattr(e, k)}})
    return pd.DataFrame(rows)
