import pandas as pd
import pytest

from marketing_report import schema
from marketing_report.cleaning import clean
from marketing_report.transform import (
    categorize_job_title,
    channel_group,
    region_for_country,
    seniority_level,
    transform,
)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Data Analyst", "Practitioner"),
        ("IT Director", "Decision Maker"),  # 'director' contains 'cto' as a substring
        ("Director of Sales", "Decision Maker"),
        ("CTO", "Executive"),
        ("VP, Data Analytics", "Executive"),
        ("Head of Analytics", "Decision Maker"),
        ("Social Media", "Other"),
        (None, "Other"),
    ],
)
def test_categorize_job_title(title, expected):
    assert categorize_job_title(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Sr. Data Analyst", "Senior"),
        ("Junior Analyst", "Junior"),
        ("Data Analyst", "Mid-Level"),
        ("Strategist", "Mid-Level"),  # contains 'sr'-like letters but not the word 'sr'
    ],
)
def test_seniority_level(title, expected):
    assert seniority_level(title) == expected


def test_region_uses_iso3_codes():
    # Regression: regions used to be looked up by country *name* after cleaning had
    # already converted names to ISO-3 codes, so every row fell into "Other Regions".
    assert region_for_country("USA") == "North America"
    assert region_for_country("ARG") == "Latin America"
    assert region_for_country("GBR") == "Europe"
    assert region_for_country("ZZZ") == "Other Regions"


def test_channel_group_uses_whole_words():
    # Regression: 'trade show' contains the substring 'ad' and was grouped as Paid Media.
    assert channel_group("Trade Show") == "Events"
    assert channel_group("Advertisement") == "Paid Media"
    assert channel_group("Referral") == "Referral"


def test_funnel_flags_are_cumulative():
    df = pd.DataFrame(
        {
            schema.STATUS: ["Responded", "No Show", "Attended", "Registered"],
            schema.SOURCE: ["Advertisement"] * 4,
            schema.COUNTRY: ["USA"] * 4,
            schema.JOB_TITLE: ["Analyst"] * 4,
        }
    )
    out = transform(df)
    assert out[schema.IS_ATTENDED].tolist() == [0, 0, 1, 1]
    assert out[schema.IS_NO_SHOW].tolist() == [0, 1, 0, 0]
    assert out[schema.IS_REGISTERED].tolist() == [0, 0, 0, 1]


def test_transform_adds_expected_columns(raw_small):
    cleaned, _ = clean(raw_small)
    out = transform(cleaned)
    for column in (schema.JOB_CATEGORY, schema.SENIORITY, schema.REGION, schema.CHANNEL_GROUP):
        assert column in out.columns
    assert len(out) == len(cleaned)
