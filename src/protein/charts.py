"""Rough charts for review (PNG). One y-axis per panel; series are labelled at their ends."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

# Validated categorical order (dataviz default palette, light): blue, orange, aqua, yellow.
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"

plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold", "lines.linewidth": 1.8,
})


def _end_label(ax, s: pd.Series, text: str, color: str, dy: float = 0) -> None:
    s = s.dropna()
    ax.annotate(text, (s.index[-1], s.iloc[-1]), xytext=(4, dy), textcoords="offset points",
                color=INK, fontsize=8, va="center")
    ax.plot(s.index[-1], s.iloc[-1], "o", ms=4, color=color)


def _years(ax, step: int = 1) -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator(step))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def _source(fig, text: str) -> None:
    fig.text(0.01, 0.005, text, fontsize=7, color=MUTED, ha="left", va="bottom")


def protein_prices(monthly: pd.DataFrame, narrative: pd.DataFrame, path: Path) -> None:
    """Panel 1: WPC 34%, nonfat dry milk and dry whey, monthly. Panel 2: WPC 80% and isolate quotes in 2026."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [2.2, 1]})
    for i, (col, label) in enumerate([("wpc34", "WPC 34%"), ("nonfat_dry_milk", "Nonfat dry milk"),
                                      ("dry_whey", "Dry whey")]):
        s = monthly[col].dropna()
        a.plot(s.index, s, color=C[i])
        _end_label(a, s, f"{label} {s.iloc[-1]:.2f}", C[i])
    a.set_title("US dairy protein prices, monthly average ($/lb)")
    a.set_xlim(monthly.index.min(), monthly.index.max() + pd.Timedelta(days=420))
    _years(a, 2)
    for i, (lo, hi, label) in enumerate([("wpc80_lo", "wpc80_hi", "WPC 80%"), ("wpi_lo", "wpi_hi", "Isolate")]):
        d = narrative.dropna(subset=[lo, hi])
        b.vlines(d.index, d[lo], d[hi], color=C[i], lw=6, alpha=0.85)
        mid = (d[lo] + d[hi]) / 2
        b.plot(d.index, mid, color=C[i], lw=1, alpha=0.6)
        _end_label(b, mid, label, C[i])
    b.set_title("WPC 80% and isolate, 2026 ($/lb)\nranges as quoted in words")
    b.set_ylim(8, 16)
    b.set_xlim(narrative.index.min() - pd.Timedelta(days=7), narrative.index.max() + pd.Timedelta(days=40))
    b.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    _source(fig, "Sources: USDA AMS Dairy Market News (WPC 34% mostly price; weekly WPC report text for WPC 80% and "
                 "isolate) and National Dairy Products Sales Report (nonfat dry milk, dry whey).")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def stocks(ers: dict[str, pd.Series], path: Path) -> None:
    fig, axes = plt.subplots(1, len(ers), figsize=(11, 3.6))
    for ax, (title, s) in zip(axes, ers.items()):
        s = s.dropna()
        ax.plot(s.index, s, color=C[0])
        _end_label(ax, s, f"{s.iloc[-1]:.0f}", C[0])
        ax.set_title(title)
        _years(ax, 3)
        ax.set_xlim(s.index.min(), s.index.max() + pd.Timedelta(days=500))
    _source(fig, "Source: USDA ERS, supply and utilization of dairy product categories (million lb).")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def margin_fit(panels: list[tuple[str, pd.Series, pd.Series]], path: Path) -> None:
    """Actual year-on-year change in gross margin against the change fitted from a lagged input price.

    Reported quarters only.
    """
    fig, axes = plt.subplots(1, len(panels), figsize=(12, 4.2), sharey=True)
    for ax, (title, actual, fitted) in zip(axes, panels):
        ax.axhline(0, color="#c3c2b7", lw=0.8)
        ax.plot(actual.index, actual, color=C[0], marker="o", ms=3)
        ax.plot(fitted.index, fitted, color=C[1], ls="--")
        _end_label(ax, actual, "Actual", C[0], dy=8)
        _end_label(ax, fitted, "Fitted", C[1], dy=-8)
        ax.set_title(title, fontsize=9)
        ax.set_xlim(pd.Timestamp("2020-01-01"), actual.index.max() + pd.Timedelta(days=300))
        _years(ax, 2)
    axes[0].set_ylabel("Gross margin, change on a year earlier (points)")
    _source(fig, "Sources: SEC filings (XBRL); USDA AMS. OLS of the year-on-year margin change on the year-on-year "
                 "log change in the input price, lagged as shown.")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)
