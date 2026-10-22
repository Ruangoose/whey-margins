"""Daily share prices from Alpaca's market data API, for a few summary statistics.

Needs a free Alpaca key pair in APCA_API_KEY_ID and APCA_API_SECRET_KEY (Windows:
set with `setx`; they are also read from the user environment here). The free
plan gives consolidated (SIP) daily bars since 2016 when the request ends at least
15 minutes ago. Alpaca's terms allow personal use only, so raw prices stay in
data/raw/ (git-ignored), and no price or return series is written to output/.
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
