"""Static PNG charts embedded in the Markdown/PDF report."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

from marketing_report.analysis import Funnel

BAR = "#2a78d6"
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
REFERENCE = "#8a8984"

# Applied per chart via rc_context so importing this module never mutates global state.
STYLE = {
    "font.size": 10,
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": TEXT,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
}


def funnel_chart(funnel: Funnel, path: Path) -> Path:
    stages = [
        ("Responded (all prospects)", funnel.total),
        ("Attended demo", funnel.attended),
        ("Registered for trial", funnel.registered),
    ]
    labels = [s for s, _ in stages][::-1]
    values = [v for _, v in stages][::-1]

    with mpl.rc_context(STYLE):
        fig = Figure(figsize=(7, 2.4))
        ax = fig.subplots()
        ax.barh(labels, values, color=BAR, height=0.55)
        for y, value in enumerate(values):
            share = value / funnel.total if funnel.total else 0
            ax.text(value, y, f"  {value:,} ({share:.1%})", va="center", color=TEXT)
        ax.set_xlim(0, max(values) * 1.3 if values else 1)
        ax.xaxis.set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_title("Prospect funnel (cumulative stages)", loc="left", color=TEXT, fontsize=11)
        fig.savefig(path)
    return path


def rate_chart(table: pd.DataFrame, title: str, overall_rate: float, path: Path) -> Path:
    """Horizontal conversion-rate bars with 95% Wilson intervals and an overall reference."""
    data = table.sort_values("rate")
    labels = [
        f"{idx}  (n={int(n):,})" for idx, n in zip(data.index, data["prospects"], strict=True)
    ]
    rates = data["rate"].to_numpy()
    err = [rates - data["ci_low"].to_numpy(), data["ci_high"].to_numpy() - rates]

    with mpl.rc_context(STYLE):
        fig = Figure(figsize=(7, 0.45 * len(data) + 1.2))
        ax = fig.subplots()
        ax.barh(labels, rates, color=BAR, height=0.55)
        ax.errorbar(
            rates, range(len(data)), xerr=err, fmt="none", ecolor=TEXT, elinewidth=1, capsize=3
        )
        ax.axvline(overall_rate, color=REFERENCE, linestyle="--", linewidth=1)
        ax.text(
            overall_rate, len(data) - 0.4, f" overall {overall_rate:.1%}", color=MUTED, fontsize=8
        )
        ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.grid(axis="x", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.set_xlabel("Trial registration rate (bars: 95% Wilson CI)")
        ax.set_title(title, loc="left", color=TEXT, fontsize=11)
        fig.savefig(path)
    return path
