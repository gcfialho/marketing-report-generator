import pandas as pd
import pytest

from marketing_report import schema
from marketing_report.analysis import (
    DECREASE,
    HOLD,
    INCREASE,
    analyze,
    analyze_funnel,
    analyze_segment,
    recommend_channels,
)
from marketing_report.transform import transform


def _frame(status_by_source: dict[str, list[str]]) -> pd.DataFrame:
    rows = [
        {
            schema.STATUS: status,
            schema.SOURCE: source,
            schema.COUNTRY: "USA",
            schema.JOB_TITLE: "Data Analyst",
        }
        for source, statuses in status_by_source.items()
        for status in statuses
    ]
    return transform(pd.DataFrame(rows))


def test_funnel_rates_follow_stage_definitions():
    df = _frame(
        {
            "Advertisement": ["Responded"] * 10
            + ["No Show"] * 60
            + ["Attended"] * 15
            + ["Registered"] * 15
        }
    )
    funnel = analyze_funnel(df)
    assert funnel.total == 100
    assert funnel.pending == 10
    assert funnel.attended == 30  # Attended + Registered
    attendance, registration = funnel.steps
    assert attendance.rate == pytest.approx(30 / 90)  # excludes the 10 still pending
    assert registration.rate == pytest.approx(15 / 30)
    assert funnel.overall_rate == pytest.approx(0.15)
    assert funnel.bottleneck is attendance


def test_recommendations_require_significance_and_sum_to_100_percent():
    df = _frame(
        {
            "Advertisement": ["Registered"] * 50 + ["No Show"] * 450,  # 10%
            "Referral": ["Registered"] * 40 + ["No Show"] * 60,  # 40%: clearly higher
            "Social Media": ["No Show"] * 14,  # 0 of 14: not enough evidence on its own
        }
    )
    recs = {
        r.channel: r
        for r in recommend_channels(analyze_segment(df, "channel", schema.SOURCE), 0.05)
    }
    assert recs["Referral"].action == INCREASE
    assert recs["Advertisement"].action == DECREASE
    assert recs["Social Media"].action == HOLD
    assert sum(r.scenario_share for r in recs.values()) == pytest.approx(1.0)
    assert sum(r.current_share for r in recs.values()) == pytest.approx(1.0)


def test_analyze_produces_findings_and_model():
    df = _frame(
        {
            "Advertisement": ["Registered"] * 60 + ["No Show"] * 400 + ["Attended"] * 40,
            "Trade Show": ["Registered"] * 15 + ["No Show"] * 70 + ["Attended"] * 15,
            "Referral": ["Registered"] * 20 + ["No Show"] * 25 + ["Attended"] * 5,
        }
    )
    result = analyze(df)
    assert result.findings[0].startswith("95 of 650 prospects registered")
    assert set(result.segments) >= {"channel", "country", "job_category", "region"}
    assert result.model is not None
    assert result.model.n_obs == 650
