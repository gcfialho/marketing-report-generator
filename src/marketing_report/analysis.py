"""Funnel, segment and statistical analysis that feeds the report."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from marketing_report import schema
from marketing_report.stats import (
    IndependenceTest,
    LogitResult,
    chi_square_independence,
    holm_adjust,
    logistic_regression,
    rate_table,
    segment_vs_rest,
)

logger = logging.getLogger(__name__)

SEGMENTS: dict[str, str] = {
    "channel": schema.SOURCE,
    "country": schema.COUNTRY,
    "region": schema.REGION,
    "job_category": schema.JOB_CATEGORY,
    "seniority": schema.SENIORITY,
}
MODEL_PREDICTORS = (schema.SOURCE, schema.REGION, schema.JOB_CATEGORY)
# Segment tests summarised in the executive summary. They are Holm-corrected as one family.
SUMMARY_SEGMENTS: dict[str, str] = {
    "channel": "channel",
    "job_category": "job category",
    "region": "region",
}

INCREASE, DECREASE, HOLD = "Increase", "Decrease", "Hold"
SCENARIO_MULTIPLIERS = {INCREASE: 1.25, DECREASE: 0.75, HOLD: 1.0}


@dataclass(frozen=True)
class FunnelStep:
    name: str
    numerator: int
    denominator: int

    @property
    def rate(self) -> float:
        return self.numerator / self.denominator if self.denominator else float("nan")


@dataclass
class Funnel:
    total: int
    status_counts: dict[str, int]
    attended: int
    no_show: int
    registered: int
    pending: int
    steps: list[FunnelStep]

    @property
    def overall_rate(self) -> float:
        return self.registered / self.total if self.total else float("nan")

    @property
    def bottleneck(self) -> FunnelStep:
        return min(self.steps, key=lambda s: s.rate)


@dataclass
class SegmentAnalysis:
    name: str
    column: str
    table: pd.DataFrame
    test: IndependenceTest
    vs_rest: pd.DataFrame
    # Holm-adjusted p-value across the executive-summary family (None if not in the family).
    summary_p_adjusted: float | None = None


@dataclass
class ChannelRecommendation:
    channel: str
    action: str
    rationale: str
    current_share: float
    scenario_share: float


@dataclass
class AnalysisResult:
    funnel: Funnel
    segments: dict[str, SegmentAnalysis]
    model: LogitResult | None
    recommendations: list[ChannelRecommendation]
    findings: list[str]
    alpha: float
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None = None


def analyze_funnel(df: pd.DataFrame) -> Funnel:
    """Status is the furthest stage reached: Responded -> (No Show | Attended) -> Registered."""
    counts = df[schema.STATUS].value_counts()
    status_counts = {s: int(counts.get(s, 0)) for s in schema.VALID_STATUSES}
    attended = int(df[schema.IS_ATTENDED].sum())
    no_show = int(df[schema.IS_NO_SHOW].sum())
    registered = int(df[schema.IS_REGISTERED].sum())
    steps = [
        FunnelStep("Demo attendance (attended / demo outcome known)", attended, attended + no_show),
        FunnelStep("Trial registration (registered / attended)", registered, attended),
    ]
    return Funnel(
        total=len(df),
        status_counts=status_counts,
        attended=attended,
        no_show=no_show,
        registered=registered,
        pending=status_counts[schema.RESPONDED],
        steps=steps,
    )


def analyze_segment(df: pd.DataFrame, name: str, column: str) -> SegmentAnalysis:
    return SegmentAnalysis(
        name=name,
        column=column,
        table=rate_table(df, column, schema.IS_REGISTERED),
        test=chi_square_independence(df, column, schema.IS_REGISTERED),
        vs_rest=segment_vs_rest(df, column, schema.IS_REGISTERED),
    )


def recommend_channels(segment: SegmentAnalysis, alpha: float) -> list[ChannelRecommendation]:
    """Evidence-based channel actions plus an illustrative volume-mix scenario.

    A channel is flagged Increase/Decrease only if its conversion rate differs from the
    rest of the channels with Holm-adjusted Fisher p < ``alpha``; everything else is Hold.
    The scenario shifts prospect volume share by fixed multipliers and renormalises to
    100%. It is a *volume* mix: the dataset has no spend, so it is not a budget split.
    """
    table, vs_rest = segment.table, segment.vs_rest
    actions: dict[str, tuple[str, str]] = {}
    for channel, row in table.iterrows():
        test = vs_rest.loc[channel] if channel in vs_rest.index else None
        if test is None or test["p_adjusted"] >= alpha:
            p_text = f"adj. p = {test['p_adjusted']:.3f}" if test is not None else "not tested"
            actions[channel] = (HOLD, f"No significant difference vs. other channels ({p_text})")
        elif row["rate"] > test["rest_rate"]:
            actions[channel] = (
                INCREASE,
                f"Converts above other channels ({row['rate']:.1%} vs {test['rest_rate']:.1%}, "
                f"adj. p = {test['p_adjusted']:.3f})",
            )
        else:
            actions[channel] = (
                DECREASE,
                f"Converts below other channels ({row['rate']:.1%} vs {test['rest_rate']:.1%}, "
                f"adj. p = {test['p_adjusted']:.3f})",
            )

    weights = {
        c: table.loc[c, "volume_share"] * SCENARIO_MULTIPLIERS[a] for c, (a, _) in actions.items()
    }
    total_weight = sum(weights.values())
    return [
        ChannelRecommendation(
            channel=str(channel),
            action=action,
            rationale=rationale,
            current_share=float(table.loc[channel, "volume_share"]),
            scenario_share=float(weights[channel] / total_weight) if total_weight else 0.0,
        )
        for channel, (action, rationale) in actions.items()
    ]


def _segment_findings(segment: SegmentAnalysis, alpha: float, label: str) -> list[str]:
    findings = []
    test = segment.test
    if test.p_value == test.p_value:  # not NaN
        p_used = test.p_value_used
        p_adj = segment.summary_p_adjusted if segment.summary_p_adjusted is not None else p_used
        verdict = "differ significantly" if p_adj < alpha else "do not differ significantly"
        if test.assumptions_ok:
            p_text = f"chi-square = {test.chi2:.2f}, df = {test.dof}, p = {p_used:.3f}"
        elif test.fisher_p_value is not None:
            p_text = f"Fisher's exact p = {p_used:.3f}; expected counts too small for chi-square"
        else:
            p_text = (
                f"Monte Carlo chi-square p = {p_used:.3f}; expected counts too small for the "
                "asymptotic test"
            )
        adj_text = (
            f", Holm-adjusted p = {p_adj:.3f}" if segment.summary_p_adjusted is not None else ""
        )
        findings.append(
            f"Conversion rates by {label} {verdict} "
            f"({p_text}{adj_text}, Cramér's V = {test.cramers_v:.2f})."
        )
    significant = segment.vs_rest[segment.vs_rest["p_adjusted"] < alpha]
    for level, row in significant.iterrows():
        direction = "above" if row["rate"] > row["rest_rate"] else "below"
        findings.append(
            f"{label.capitalize()} '{level}' converts {direction} the rest "
            f"({row['rate']:.1%} vs {row['rest_rate']:.1%}, "
            f"Holm-adjusted p = {row['p_adjusted']:.3f})."
        )
    return findings


def _adjust_summary_family(segments: dict[str, SegmentAnalysis]) -> None:
    """Holm-correct the omnibus tests reported in the executive summary as one family."""
    names = [
        n
        for n in SUMMARY_SEGMENTS
        if n in segments and segments[n].test.p_value_used == segments[n].test.p_value_used
    ]
    adjusted = holm_adjust([segments[n].test.p_value_used for n in names])
    for name, p_adj in zip(names, adjusted, strict=True):
        segments[name].summary_p_adjusted = p_adj


def analyze(df: pd.DataFrame, alpha: float = 0.05) -> AnalysisResult:
    """Run the full analysis on a transformed prospect-level frame."""
    funnel = analyze_funnel(df)
    segments = {
        name: analyze_segment(df, name, column)
        for name, column in SEGMENTS.items()
        if column in df.columns
    }
    _adjust_summary_family(segments)
    model = logistic_regression(df, schema.IS_REGISTERED, list(MODEL_PREDICTORS))
    recommendations = recommend_channels(segments["channel"], alpha)

    bottleneck = funnel.bottleneck
    findings = [
        f"{funnel.registered:,} of {funnel.total:,} prospects registered for a trial "
        f"({funnel.overall_rate:.1%}).",
        f"Weakest funnel step: {bottleneck.name} at {bottleneck.rate:.1%} "
        f"({bottleneck.numerator:,} of {bottleneck.denominator:,}).",
    ]
    for name, label in SUMMARY_SEGMENTS.items():
        if name in segments:
            findings.extend(_segment_findings(segments[name], alpha, label))

    date_range = None
    if schema.OPT_IN_TS in df.columns and df[schema.OPT_IN_TS].notna().any():
        date_range = (df[schema.OPT_IN_TS].min(), df[schema.OPT_IN_TS].max())

    logger.info(
        "Analysis complete: %d findings, %d channel actions", len(findings), len(recommendations)
    )
    return AnalysisResult(
        funnel=funnel,
        segments=segments,
        model=model,
        recommendations=recommendations,
        findings=findings,
        alpha=alpha,
        date_range=date_range,
    )
