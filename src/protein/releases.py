"""What results releases say about protein costs.

Each 8-K under item 2.02 carries the press release as exhibit 99.1. The text is
split into sentences, and those mentioning protein or whey alongside cost words
are kept, to tag which results days were about protein costs.
"""
from __future__ import annotations

import html
import json
import re

import pandas as pd

from .edgar import earnings_dates
from .fetch import get, SEC_USER_AGENT

COST = re.compile(r"\b(cost|costs|inflation|inflationary|margin|margins|commodit\w*|pricing|price increases?)\b", re.I)
PROTEIN = re.compile(r"\b(protein|whey|dairy|milk|ingredient\w*|raw material\w*)\b", re.I)


def _sec(url: str, suffix: str) -> bytes:
    return get(url, "sec-docs", suffix=suffix, headers={"User-Agent": SEC_USER_AGENT}, pause=0.15)


def exhibit_text(cik: int, accession: str) -> str:
    folder = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
    index = json.loads(_sec(folder + "index.json", ".json"))
    names = [i["name"] for i in index["directory"]["item"]]
    ex = [n for n in names if re.search(r"ex-?99[._-]?1|ex991|exhibit991", n, re.I) and n.lower().endswith((".htm", ".html", ".txt"))]
    if not ex:
        ex = [n for n in names if re.search(r"99", n) and n.lower().endswith((".htm", ".html"))]
    if not ex:
        return ""
    raw = _sec(folder + ex[0], ".htm").decode("utf-8", errors="ignore")
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text))


def protein_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z“\"])", text)
    return [s.strip() for s in sentences if PROTEIN.search(s) and COST.search(s) and len(s) < 1200]


RESULTS = re.compile(r"(first|second|third|fourth)[ -]quarter[^.]{0,120}results|results[^.]{0,80}(first|second|third|fourth)[ -]quarter", re.I)


def scan(ticker: str, cik: int) -> pd.DataFrame:
    """Results releases with their protein-cost sentences.

    8-Ks filed under item 9.01 alone count only when the exhibit announces quarterly results.
    """
    rows = []
    for e in earnings_dates(cik).itertuples():
        text = exhibit_text(cik, e.accessionNumber)
        if not e.item_202 and not RESULTS.search(text[:3000]):
            continue
        hits = protein_sentences(text)
        rows.append({"ticker": ticker, "accepted": e.accepted, "after_close": e.after_close,
                     "accession": e.accessionNumber, "n_hits": len(hits), "sentences": hits})
    return pd.DataFrame(rows)
