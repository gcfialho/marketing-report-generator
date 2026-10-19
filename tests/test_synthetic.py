import pandas as pd
import pytest

from marketing_report import schema, synthetic
from marketing_report.cleaning import clean


def test_schema_matches_real_export():
    df = synthetic.generate(200, seed=1)
    assert list(df.columns) == list(schema.ALL_COLUMNS)


def test_generation_is_deterministic_per_seed():
    pd.testing.assert_frame_equal(synthetic.generate(300, seed=7), synthetic.generate(300, seed=7))
    assert not synthetic.generate(300, seed=7).equals(synthetic.generate(300, seed=8))


def test_distributions_are_plausible():
    df, _ = clean(synthetic.generate(5000, seed=3))
    status_share = df[schema.STATUS].value_counts(normalize=True)
    assert status_share[schema.NO_SHOW] == pytest.approx(0.66, abs=0.05)
    assert status_share[schema.REGISTERED] == pytest.approx(0.13, abs=0.03)
    source_share = df[schema.SOURCE].value_counts(normalize=True)
    assert source_share.index[0] == "Advertisement"


def test_messy_data_exercises_cleaning():
    raw = synthetic.generate(1000, seed=42)
    assert raw[schema.PROSPECT_ID].duplicated().sum() > 0
    _, report = clean(raw)
    assert report.duplicates_removed > 0
    assert report.unmapped_countries == []


def test_tidy_mode_has_no_duplicates():
    raw = synthetic.generate(500, seed=42, messy=False)
    assert not raw[schema.PROSPECT_ID].duplicated().any()
    assert set(raw[schema.STATUS]) <= set(schema.VALID_STATUSES)


def test_write_round_trip(tmp_path):
    df = synthetic.generate(50, seed=0)
    path = synthetic.write(df, tmp_path / "out.csv")
    assert len(pd.read_csv(path)) == len(df)


def test_rejects_non_positive_rows():
    with pytest.raises(ValueError, match="positive"):
        synthetic.generate(0)
