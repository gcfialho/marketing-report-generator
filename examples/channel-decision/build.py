"""Worked example: should more prospects go through Referral?

Builds ``README.md``, two charts and ``simulation.csv`` in this folder. The data is
synthetic, so the true registration rate of every channel is known and the report's
estimates, intervals and channel actions can be checked against it.

    uv run python examples/channel-decision/build.py            # about 4 minutes
    uv run python examples/channel-decision/build.py --runs 20  # quick check

Every number in the generated README comes from this script.
"""

from __future__ import annotations

import argparse
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

from marketing_report import schema, synthetic
from marketing_report.analysis import (
    DECREASE,
    INCREASE,
    ChannelRecommendation,
    SegmentAnalysis,
    analyze,
    analyze_segment,
    funnel_steps_by,
    recommend_channels,
)
from marketing_report.charts import BAR, GRID, MUTED, REFERENCE, STYLE, TEXT
from marketing_report.cleaning import clean
from marketing_report.transform import transform

HERE = Path(__file__).resolve().parent
FOCUS = "Referral"
ALPHA = 0.05
SEED = 42  # the seed of the default example report
SIZES = (1000, 2000, 3000, 5000, 10000)
SIM_HEADER = (
    "| Prospects | Referral prospects (median) | Observed ranking does not put Referral first "
    "| Report flags Referral as *Increase* | Report flags a channel in the wrong direction "
    "| Wilson interval coverage (target 95%) |\n|---:|---:|---:|---:|---:|---|"
)
SECOND = "#eb6834"  # categorical slot 2 (orange), validated next to slot 1 (blue)


@dataclass
class Snapshot:
    n: int
    data: pd.DataFrame
    segment: SegmentAnalysis
    recs: dict[str, ChannelRecommendation]


def snapshot(n: int, seed: int) -> Snapshot:
    data = transform(clean(synthetic.generate(n, seed=seed))[0])
    segment = analyze_segment(data, "channel", schema.SOURCE)
    recs = {r.channel: r for r in recommend_channels(segment, ALPHA)}
    return Snapshot(n, data, segment, recs)


def wrong_direction(recs: dict[str, ChannelRecommendation], truth: dict[str, float]) -> bool:
    """An Increase on a channel that truly converts below the rest, or the reverse."""
    for channel, rec in recs.items():
        rest = synthetic.true_rest_rate(channel)
        if rec.action == INCREASE and truth[channel] <= rest:
            return True
        if rec.action == DECREASE and truth[channel] >= rest:
            return True
    return False


def simulate(runs: int) -> pd.DataFrame:
    truth = synthetic.true_registration_rates()
    rows = []
    for n in SIZES:
        for seed in range(1, runs + 1):
            snap = snapshot(n, seed)
            table = snap.segment.table
            row = {
                "prospects": n,
                "seed": seed,
                "focus_prospects": int(table.loc[FOCUS, "prospects"]),
                "naive_pick": str(table["rate"].idxmax()),
                "focus_flagged": snap.recs[FOCUS].action == INCREASE,
                "wrong_direction": wrong_direction(snap.recs, truth),
            }
            for channel in table.index:
                lo, hi = table.loc[channel, ["ci_low", "ci_high"]]
                row[f"covered:{channel}"] = bool(lo <= truth[channel] <= hi)
            rows.append(row)
        print(f"simulated {runs} datasets of {n:,} prospects")
    return pd.DataFrame(rows)


def summarise(sim: pd.DataFrame) -> pd.DataFrame:
    covered = [c for c in sim.columns if c.startswith("covered:")]
    out = sim.groupby("prospects").agg(
        runs=("seed", "size"),
        focus_prospects=("focus_prospects", "median"),
        naive_wrong=("naive_pick", lambda s: float((s != FOCUS).mean())),
        focus_flagged=("focus_flagged", "mean"),
        wrong_direction=("wrong_direction", "mean"),
    )
    coverage = sim.groupby("prospects")[covered].mean()
    out["coverage_min"] = coverage.min(axis=1)
    out["coverage_mean"] = coverage.mean(axis=1)
    return out


def estimates_chart(snaps: list[Snapshot], truth: dict[str, float], path: Path) -> None:
    order = sorted(truth, key=truth.get)  # same channel order in both panels
    with mpl.rc_context(STYLE):
        fig = Figure(figsize=(8.6, 3.4))
        axes = fig.subplots(1, len(snaps), sharex=True)
        for ax, snap in zip(axes, snaps, strict=True):
            table = snap.segment.table.reindex(order)
            y = np.arange(len(order))
            ax.hlines(y, table["ci_low"], table["ci_high"], color=BAR, linewidth=2, clip_on=False)
            ax.plot(table["rate"], y, "o", color=BAR, markersize=7, markeredgecolor="white",
                    zorder=3, clip_on=False)  # fmt: skip
            ax.plot([truth[c] for c in order], y, "D", markersize=7, markerfacecolor="none",
                    markeredgecolor=TEXT, markeredgewidth=1.4, zorder=4, clip_on=False)  # fmt: skip
            labels = [
                f"{c} (n={int(table.loc[c, 'prospects']):,})\n{snap.recs[c].action}" for c in order
            ]
            ax.set_yticks(y, labels, fontsize=8.5)
            ax.set_ylim(-0.6, len(order) - 0.4)
            ax.set_xlim(0, 0.42)
            ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
            ax.grid(axis="x", color=GRID, linewidth=0.6)
            ax.set_axisbelow(True)
            ax.set_title(f"{snap.n:,} prospects", loc="left", color=TEXT, fontsize=10)
        handles = [
            Line2D([], [], color=BAR, marker="o", markeredgecolor="white", linewidth=2,
                   label="Observed rate and 95% Wilson interval"),
            Line2D([], [], color=TEXT, marker="D", markerfacecolor="none", linestyle="none",
                   label="True rate (known from the generator)"),
        ]  # fmt: skip
        fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, fontsize=8.5,
                   labelcolor=MUTED, bbox_to_anchor=(0.5, -0.02))  # fmt: skip
        fig.suptitle(
            "Registration rate by channel: estimates against the true rates",
            x=0.01, ha="left", color=TEXT, fontsize=11,
        )  # fmt: skip
        fig.subplots_adjust(bottom=0.2, top=0.8, wspace=0.75)
        fig.savefig(path)


def detection_chart(summary: pd.DataFrame, path: Path) -> None:
    x = summary.index.to_numpy()
    series = [
        ("Ranking by observed rate does not put Referral first", summary["naive_wrong"], SECOND,
         "-"),
        ("Report flags Referral as Increase (the right call)", summary["focus_flagged"], BAR,
         "-"),
        ("Report flags any channel in the wrong direction", summary["wrong_direction"], REFERENCE,
         "--"),
    ]  # fmt: skip
    with mpl.rc_context(STYLE):
        fig = Figure(figsize=(7.4, 3.6))
        ax = fig.subplots()
        labelled: list[float] = []
        for label, values, color, style in series:
            ax.plot(x, values, style, color=color, linewidth=2, marker="o", markersize=5,
                    label=label, clip_on=False)  # fmt: skip
            end = float(values.iloc[-1])
            if all(abs(end - other) > 0.05 for other in labelled):  # skip colliding labels
                ax.text(x[-1], end, f"  {end:.0%}", va="center", color=TEXT, fontsize=8.5)
                labelled.append(end)
        ax.set_xscale("log")
        ax.set_xticks(x, [f"{v:,}" for v in x])
        ax.minorticks_off()
        ax.set_ylim(0, 1)
        ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.set_xlabel("Prospects in the export (Referral is about 4% of them)")
        ax.set_ylabel("Share of simulated exports")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), frameon=False, fontsize=8.5,
                  labelcolor=MUTED)  # fmt: skip
        ax.set_title(
            f"How often each rule reaches each outcome ({int(summary['runs'].iloc[0])} "
            "simulated exports per size)",
            loc="left", color=TEXT, fontsize=11,
        )  # fmt: skip
        fig.savefig(path)


def pvalue(v: float) -> str:
    return "< 0.001" if v < 0.001 else f"= {v:.3f}"


def reflow(markdown: str, width: int = 100) -> str:
    """Re-wrap prose paragraphs and list items; leave tables, headings, images and code alone."""
    out, in_code = [], False
    for block in markdown.split("\n\n"):
        stripped = block.lstrip()
        if stripped.startswith("```") or in_code:
            in_code = in_code != (block.count("```") % 2 == 1)
            out.append(block)
        elif stripped.startswith(("|", "#", "![")):
            out.append(block)
        elif stripped.startswith(("- ", "1. ")):
            items = re.split(r"\n(?=- |\d+\. )", block)
            wrapped = []
            for item in items:
                marker = re.match(r"(- |\d+\. )", item).group(1)
                body = " ".join(item[len(marker) :].split())
                wrapped.append(
                    textwrap.fill(
                        body, width, initial_indent=marker, subsequent_indent=" " * len(marker)
                    )
                )
            out.append("\n".join(wrapped))
        else:
            out.append(textwrap.fill(" ".join(block.split()), width))
    return "\n\n".join(out)


def pct(v: float) -> str:
    return f"{v:.1%}"


def interval(lo: float, hi: float) -> str:
    return f"{lo:.1%} to {hi:.1%}"


def detectable(rec: ChannelRecommendation) -> str:
    high = f"above {rec.detectable_high:.1%}"
    return high if rec.detectable_low <= 0 else f"below {rec.detectable_low:.1%} or {high}"


def channel_table(snap: Snapshot, truth: dict[str, float]) -> str:
    lines = [
        "| Channel | Prospects | Observed rate | 95% interval | True rate | Action "
        "| Flagged only if true rate is |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for channel, row in snap.segment.table.iterrows():
        rec = snap.recs[channel]
        lines.append(
            f"| {channel} | {int(row['prospects']):,} | {pct(row['rate'])} | "
            f"{interval(row['ci_low'], row['ci_high'])} | {pct(truth[channel])} | "
            f"{rec.action} | {detectable(rec)} |"
        )
    return "\n".join(lines)


def steps_line(snap: Snapshot, channel: str) -> str:
    s = funnel_steps_by(snap.data, schema.SOURCE).loc[channel]
    return (
        f"attendance {pct(s['attendance_rate'])} "
        f"({interval(s['attendance_ci_low'], s['attendance_ci_high'])}), "
        f"registration after attending {pct(s['registration_rate'])} "
        f"({interval(s['registration_ci_low'], s['registration_ci_high'])})"
    )


def write_readme(small: Snapshot, large: Snapshot, summary: pd.DataFrame) -> str:
    truth = synthetic.true_registration_rates()
    rest = synthetic.true_rest_rate(FOCUS)
    small_table = small.segment.table
    naive_small = str(small_table["rate"].idxmax())
    covered_small = all(
        small_table.loc[c, "ci_low"] <= truth[c] <= small_table.loc[c, "ci_high"]
        for c in small_table.index
    )
    covered_large = all(
        large.segment.table.loc[c, "ci_low"] <= truth[c] <= large.segment.table.loc[c, "ci_high"]
        for c in large.segment.table.index
    )
    reaching = summary[summary["focus_flagged"] >= 0.8]
    if reaching.empty:
        needed_total = f"more than {SIZES[-1]:,} prospects"
        needed = needed_total
    else:
        needed_total = f"about {int(reaching.index[0]):,} prospects"
        needed = (
            f"{needed_total} (a median of {int(reaching['focus_prospects'].iloc[0]):,} "
            "from Referral)"
        )
    worst_wrong = float(summary["wrong_direction"].max())
    wrong_text = (
        "and it never flagged a channel in the wrong direction"
        if worst_wrong == 0
        else "and it flagged a channel in the wrong direction in at most "
        f"{worst_wrong:.0%} of exports"
    )
    runs = int(summary["runs"].iloc[0])
    sim_rows = "\n".join(
        f"| {n:,} | {int(r.focus_prospects):,} | {r.naive_wrong:.0%} | {r.focus_flagged:.0%} "
        f"| {r.wrong_direction:.0%} | {r.coverage_mean:.1%} (lowest channel {r.coverage_min:.1%}) |"
        for n, r in summary.iterrows()
    )

    # The one "significant" omnibus result in the default report, and what drives it.
    full = analyze(small.data, alpha=ALPHA)
    jobs = full.segments["job_category"]
    other = jobs.table.loc["Other"]
    other_vs_rest = jobs.vs_rest.loc["Other", "p_adjusted"]

    ref_small, ref_large = small.recs[FOCUS], large.recs[FOCUS]
    large_table = large.segment.table

    return f"""# Worked example: should more prospects go through Referral?

This example takes one business question through the pipeline and checks the answer against
the truth. The data is synthetic, so the true registration rate of every channel is known from
the generator's parameters (`synthetic.true_registration_rates()`). Nothing here describes a
real company.

## The question

The [default example report](../synthetic/example-co-marketing-report.md) covers
{small.n:,} prospects. Ranked by observed registration rate,
{naive_small} comes first at {pct(small_table.loc[naive_small, "rate"])}, Referral is close
behind at {pct(small_table.loc[FOCUS, "rate"])}, and Advertisement, which brings
{pct(small_table.loc["Advertisement", "volume_share"])} of prospects, converts at
{pct(small_table.loc["Advertisement", "rate"])}. Should the team send more prospects through
{naive_small} or Referral?

## Short answer

**Not on {small.n:,} prospects.** The report marks every channel *Hold*. Referral has only
{int(small_table.loc[FOCUS, "prospects"])} prospects, so the test would flag it only if its true
rate were {detectable(ref_small)}. Picking the channel with the highest observed rate would have
chosen {naive_small}, whose true rate ({pct(truth[naive_small])}) is close to Advertisement's.
The channel that really converts better is Referral ({pct(truth[FOCUS])} against
{pct(rest)} for all other prospects). With {needed}, the same rule flags it in at least 80% of
simulated exports, {wrong_text}.

## 1. What the {small.n:,}-prospect report says

{channel_table(small, truth)}

Every 95% interval {"contains" if covered_small else "does not always contain"} the true rate.
The intervals are wide where the data is thin: Referral's runs from
{interval(small_table.loc[FOCUS, "ci_low"], small_table.loc[FOCUS, "ci_high"])}.

![Estimates against the true rates at {small.n:,} and {large.n:,} prospects](estimates_vs_truth.png)

## 2. The same question with {large.n:,} prospects

{channel_table(large, truth)}

Referral is now flagged *{ref_large.action}*
({pct(large_table.loc[FOCUS, "rate"])} against
{pct(large.segment.vs_rest.loc[FOCUS, "rest_rate"])} for the rest, Holm-adjusted
p {pvalue(large.segment.vs_rest.loc[FOCUS, "p_adjusted"])}). Every interval
{"still contains" if covered_large else "does not always contain"} the true rate.

The per-channel funnel table in the report shows where the gap comes from. At
{large.n:,} prospects, Referral: {steps_line(large, FOCUS)}. Advertisement:
{steps_line(large, "Advertisement")}. Most of Referral's advantage is at demo attendance (the
generator uses {synthetic.P_ATTEND[FOCUS]:.0%} against {synthetic.P_ATTEND["Advertisement"]:.0%}),
so a reminder or scheduling change for demo invitees is a cheaper first test than moving
volume.

## 3. How often each rule gets it right

One dataset can be lucky. The script repeats the analysis on {runs} independently generated
exports at each size and counts outcomes.

{SIM_HEADER}
{sim_rows}

![How often each rule reaches each outcome](detection_by_sample_size.png)

- Ranking channels by observed rate always gives an answer. Because Referral's true advantage
  is large, the ranking is usually right, but at {SIZES[0]:,} prospects it puts another channel
  first in {summary.loc[SIZES[0], "naive_wrong"]:.0%} of exports, and nothing in a ranking says
  which exports those are.
- The report's rule (Fisher's exact test against the other channels, Holm-corrected) is
  conservative. At {SIZES[0]:,} prospects it flags Referral in only
  {summary.loc[SIZES[0], "focus_flagged"]:.0%} of exports and otherwise says *Hold*. That is the
  price of not acting on noise: across all sizes it {wrong_text.removeprefix("and it ")}. The
  *Flagged only if true rate is* column tells the reader when a *Hold* means "not enough data".
- The Wilson intervals cover the true rate close to the 95% they promise, including for the
  small Social Media and Referral segments.

## 4. A false positive in the default report

The default report says conversion by job category differs significantly (Holm-adjusted
p = {jobs.summary_p_adjusted:.3f}). That result is driven by *Other* at
{pct(other["rate"])} ({int(other["conversions"])} of {int(other["prospects"])}), but the
generator gives *Other* the same registration probability as *Practitioner*. Job category
only multiplies the registration step, by
{synthetic.JOB_REGISTER_LIFT["executive"]} for executives and
{synthetic.JOB_REGISTER_LIFT["decision_maker"]} for decision makers. At a 5% significance
level some results like this are expected. The safeguards hold: no single category passes
its own corrected test (*Other* against the rest: Holm-adjusted
p = {other_vs_rest:.3f}), and the report recommends no
action on job category.

## What the team should do

1. Keep the current channel mix for now. The data does not yet support moving volume.
2. Keep collecting: at the current mix, {needed_total} are needed before a real
   Referral advantage of this size is detected reliably.
3. Test a demo-attendance intervention, since attendance is the weakest step overall and where
   most of the Referral gap sits.
4. Add spend per channel before any budget decision. Without it the report can only talk about
   prospect volume, not cost per registration.

## Reproduce

```bash
uv run python examples/channel-decision/build.py           # {runs} runs per size, a few minutes
uv run python examples/channel-decision/build.py --runs 20 # quick check
uv run python examples/channel-decision/build.py --reuse   # rebuild text and charts only
```

The script writes this README, both charts and `simulation.csv` (one row per simulated export).
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=200, help="simulated exports per size")
    parser.add_argument("--out", type=Path, default=HERE, help="output folder")
    parser.add_argument(
        "--reuse", action="store_true", help="rebuild from an existing simulation.csv"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    truth = synthetic.true_registration_rates()
    small, large = snapshot(1000, SEED), snapshot(5000, SEED)
    estimates_chart([small, large], truth, args.out / "estimates_vs_truth.png")

    sim_path = args.out / "simulation.csv"
    if args.reuse and sim_path.exists():
        sim = pd.read_csv(sim_path)
    else:
        sim = simulate(args.runs)
        sim.to_csv(sim_path, index=False)
    summary = summarise(sim)
    detection_chart(summary, args.out / "detection_by_sample_size.png")

    readme = reflow(write_readme(small, large, summary))
    (args.out / "README.md").write_text(readme, encoding="utf-8")
    print(f"wrote {args.out / 'README.md'}")


if __name__ == "__main__":
    main()
