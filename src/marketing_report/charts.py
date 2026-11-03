"""Static PNG charts embedded in the Markdown/PDF report."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib as mpl
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

from marketing_report.analysis import Funnel

if TYPE_CHECKING:
    from matplotlib.typing import RcKeyType

BAR = "#2a78d6"
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
REFERENCE = "#8a8984"

# Applied per chart via rc_context so importing this module never mutates global state.
STYLE: dict[RcKeyType, object] = {
    "font.size": 10,
    "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": TEXT,
    "ytick.major.size": 0,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
}


def funnel_chart(funnel: Funnel, path: Path) -> Path:
    """Cumulative funnel with each stage's conversion from the stage above it.

    "Demo outcome recorded" is drawn as its own stage because the attendance rate is
    measured against it, not against all prospects. The weakest step is named in the title.
    """
    outcome_known = funnel.attended + funnel.no_show
    stages = [
        ("All prospects", funnel.total, None),
        ("Demo outcome recorded", outcome_known, funnel.total),
        ("Attended demo", funnel.attended, outcome_known),
        ("Registered for trial", funnel.registered, funnel.attended),
    ]
    bottleneck = funnel.bottleneck
    labels = [s for s, _, _ in stages][::-1]
    values = [v for _, v, _ in stages][::-1]
    bases = [b for _, _, b in stages][::-1]

    with mpl.rc_context(STYLE):
        fig = Figure(figsize=(7, 2.9))
        ax = fig.subplots()
        ax.barh(labels, values, color=BAR, height=0.6)
        for y, (value, base) in enumerate(zip(values, bases, strict=True)):
            text = f"  {value:,}"
            if base:
                text += f"   {value / base:.1%} of the stage above"
            ax.text(value, y, text, va="center", color=TEXT, fontsize=9)
        ax.set_xlim(0, max(values) * 1.6 if values else 1)
        ax.xaxis.set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.set_title(
            f"Weakest step: {bottleneck.name.split(' (')[0].lower()} "
            f"({bottleneck.rate:.1%}, {bottleneck.numerator:,} of {bottleneck.denominator:,})",
            loc="left",
            color=TEXT,
            fontsize=11,
        )
        fig.savefig(path)
    return path


def rate_chart(table: pd.DataFrame, title: str, overall_rate: float, path: Path) -> Path:
    """Dot-and-interval plot of conversion rates with 95% Wilson intervals.

    Points with interval lines (rather than bars) keep the reader's eye on the range of
    plausible rates, which is what matters for small segments.
    """
    data = table.sort_values("rate")
    labels = [
        f"{idx}  (n={int(n):,})" for idx, n in zip(data.index, data["prospects"], strict=True)
    ]
    rates = data["rate"].to_numpy()
    y = range(len(data))

    with mpl.rc_context(STYLE):
        fig = Figure(figsize=(7, 0.42 * len(data) + 1.3))
        ax = fig.subplots()
        ax.hlines(y, data["ci_low"], data["ci_high"], color=BAR, linewidth=2, clip_on=False)
        ax.plot(
            rates, y, "o", color=BAR, markersize=7, markeredgecolor="white", zorder=3, clip_on=False
        )
        for yi, (rate, high) in enumerate(zip(rates, data["ci_high"], strict=True)):
            ax.text(high, yi, f"  {rate:.1%}", va="center", color=TEXT, fontsize=8.5)
        ax.axvline(
            overall_rate,
            color=REFERENCE,
            linestyle="--",
            linewidth=1,
            label=f"Overall rate ({overall_rate:.1%})",
        )
        ax.set_yticks(list(y), labels)
        ax.set_ylim(-0.6, len(data) - 0.4)
        ax.set_xlim(0, min(1.0, float(data["ci_high"].max()) * 1.15 + 0.02))
        ax.legend(loc="lower right", frameon=False, fontsize=8, labelcolor=MUTED)
        ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.grid(axis="x", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.set_xlabel("Trial registration rate (dot: observed; line: 95% Wilson interval)")
        ax.set_title(title, loc="left", color=TEXT, fontsize=11)
        fig.savefig(path)
    return path
