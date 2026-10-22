"""Downloads with a local cache.

Every raw file lands in data/raw/ (git-ignored). A rerun reads the cache unless
refresh=True, so the study reruns offline and a refresh redownloads everything.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

# The SEC asks every script to name itself with a contact address: set SEC_USER_AGENT to your name and
# email ("Jane Doe jane@example.com") before downloading. Cached files don't need it.
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "")


def cache_path(url: str, subdir: str, suffix: str = "") -> Path:
    name = hashlib.sha1(url.encode()).hexdigest()[:16] + suffix
    return RAW / subdir / name


def get(url: str, subdir: str, *, suffix: str = "", headers: dict | None = None,
        params: dict | None = None, refresh: bool = False, tries: int = 3,
        pause: float = 0.0) -> bytes:
    """Return the body of url, from the cache when there is one."""
    key = url if not params else url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items())
                                                    if "token" not in k.lower() and "key" not in k.lower())
    path = cache_path(key, subdir, suffix)
    if path.exists() and not refresh:
        return path.read_bytes()
    if headers is not None and not all(headers.values()):
        raise RuntimeError(f"set SEC_USER_AGENT to your name and email to download {url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=60)
            if r.status_code == 200:
                path.write_bytes(r.content)
                if pause:
                    time.sleep(pause)
                return r.content
            last = f"HTTP {r.status_code}"
            if r.status_code in (403, 404):
                break
        except requests.RequestException as e:  # network hiccup: retry
            last = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed ({last}): {url}")


def sec_get(url: str, refresh: bool = False) -> bytes:
    # The SEC allows 10 requests a second; a short pause keeps well inside it.
    return get(url, "sec", suffix=".json", headers={"User-Agent": SEC_USER_AGENT},
               refresh=refresh, pause=0.15)
