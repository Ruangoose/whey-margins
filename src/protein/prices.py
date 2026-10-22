"""Daily share prices from Alpaca's market data API, for a few summary statistics and the web page's charts.

Needs a free Alpaca key pair in APCA_API_KEY_ID and APCA_API_SECRET_KEY (Windows:
set with `setx`; they are also read from the user environment here). The free
plan gives consolidated (SIP) daily bars since 2016 when the request ends at least
15 minutes ago. Alpaca's terms allow personal use only. Alpaca agreed on 22 October
2026 to the web page charting them, with no raw prices and no data to download, so
raw prices stay in data/raw/ and the charts' series in output/site/shares.json, both
git-ignored.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from .fetch import get

DATA = "https://data.alpaca.markets"


def _env(name: str) -> str | None:
    v = os.environ.get(name)
    if not v and os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = winreg.QueryValueEx(k, name)[0]
        except OSError:
            v = None
    return v


def headers() -> dict:
    key, secret = _env("APCA_API_KEY_ID"), _env("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY (a free Alpaca key pair) to download prices.")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def daily(ticker: str, start: str, end: str, refresh: bool = False) -> pd.DataFrame:
    """Daily bars adjusted for splits, dividends and spin-offs (adjustment=all), all pages."""
    url = f"{DATA}/v2/stocks/{ticker.upper()}/bars"
    params = {"timeframe": "1Day", "start": start, "end": end, "adjustment": "all",
              "feed": "sip", "limit": 10000}
    bars, token = [], None
    while True:
        p = dict(params, **({"page_token": token} if token else {}))
        body = json.loads(get(url, "alpaca", suffix=".json", headers=headers(), params=p,
                              refresh=refresh, pause=0.35))
        bars += body.get("bars") or []
        token = body.get("next_page_token")
        if not token:
            break
    if not bars:
        raise RuntimeError(f"no bars for {ticker}")
    df = pd.DataFrame(bars).rename(columns={"t": "date", "o": "open", "h": "high", "l": "low",
                                            "c": "close", "v": "volume", "vw": "vwap", "n": "trades"})
    # Daily bars are stamped at midnight New York time, given in UTC.
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    return df.set_index("date")


def closes(tickers: list[str], start: str, end: str, refresh: bool = False) -> pd.DataFrame:
    return pd.DataFrame({t: daily(t, start, end, refresh)["close"] for t in tickers})


def weekly_index(closes: pd.DataFrame, start: str) -> pd.DataFrame:
    """Each column indexed to 100 at the first session from `start`, then at the last close of each week.

    One point a week is what the web page's share chart draws, so no daily price leaves the study.
    """
    span = closes.loc[start:].dropna()
    weekly = span.groupby(span.index.to_period("W-FRI")).tail(1)
    out = pd.concat([span.iloc[[0]], weekly[weekly.index > span.index[0]]])
    return out / span.iloc[0] * 100
