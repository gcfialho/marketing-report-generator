import pandas as pd

from marketing_report import schema
from marketing_report.cleaning import clean, normalise_strings, standardise_country


def test_clean_end_to_end(raw_small):
    df, report = clean(raw_small)

    assert report.rows_in == 6
    assert report.empty_rows_removed == 1
    assert report.invalid_status_removed == 1
    assert report.duplicates_removed == 1
    assert report.rows_out == len(df) == 3
    assert df[schema.PROSPECT_ID].is_unique


def test_dedup_keeps_furthest_funnel_stage(raw_small):
    df, _ = clean(raw_small)
    p2 = df[df[schema.PROSPECT_ID] == "P2"].iloc[0]
    # The older row reached "Attended"; the newer one is a "No Show". Funnel progress wins.
    assert p2[schema.STATUS] == schema.ATTENDED


def test_dedup_breaks_ties_on_latest_opt_in():
    raw = pd.DataFrame(
        {
            schema.PROSPECT_ID: ["A", "A"],
            schema.STATUS: ["No Show", "No Show"],
            schema.SOURCE: ["Advertisement", "Trade Show"],
            schema.COUNTRY: ["Canada", "Canada"],
            schema.JOB_TITLE: ["Analyst", "Analyst"],
            schema.OPT_IN_TS: ["2023-01-01", "2023-06-01"],
        }
    )
    df, _ = clean(raw)
    assert len(df) == 1
    assert df.iloc[0][schema.SOURCE] == "Trade Show"


def test_countries_mapped_to_iso3(raw_small):
    df, report = clean(raw_small)
    assert set(df[schema.COUNTRY]) == {"USA", "ARG"}
    assert report.unmapped_countries == []


def test_standardise_country_unknown_is_title_cased():
    assert standardise_country(" atlantis ") == "Atlantis"
    assert standardise_country("españa") == "ESP"
    assert pd.isna(standardise_country(None))


def test_normalise_strings_preserves_missing_values():
    df = pd.DataFrame({"a": ["  x   y ", None, "", "nan"]})
    out = normalise_strings(df)
    assert out["a"].iloc[0] == "x y"
    assert pd.isna(out["a"].iloc[1])
    assert pd.isna(out["a"].iloc[2])
    # A literal "nan" string is data, not a missing value.
    assert out["a"].iloc[3] == "nan"


def test_status_variants_are_standardised(raw_small):
    df, _ = clean(raw_small)
    assert set(df[schema.STATUS]) <= set(schema.VALID_STATUSES)
