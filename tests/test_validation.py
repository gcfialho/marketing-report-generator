import pandas as pd
import pytest

from marketing_report import schema
from marketing_report.validation import SchemaError, load_data, validate, validate_or_raise


def test_validate_reports_quality(raw_small):
    report = validate(raw_small)
    assert report.is_valid
    assert report.n_rows == 6
    assert report.duplicate_prospect_ids == 1
    assert report.unknown_statuses == {"Bogus": 1}
    assert 0 < report.completeness_pct < 100


def test_missing_required_column_raises():
    df = pd.DataFrame({schema.STATUS: ["Registered"], schema.SOURCE: ["Referral"]})
    with pytest.raises(SchemaError, match="Country"):
        validate_or_raise(df)


def test_load_data_csv_and_excel_round_trip(tmp_path, raw_small):
    raw_small = raw_small.dropna(how="all")  # Excel drops trailing empty rows on write
    csv_path = tmp_path / "data.csv"
    xlsx_path = tmp_path / "data.xlsx"
    raw_small.to_csv(csv_path, index=False)
    raw_small.to_excel(xlsx_path, index=False)

    from_csv = load_data(csv_path)
    from_xlsx = load_data(xlsx_path)
    assert len(from_csv) == len(from_xlsx) == len(raw_small)
    assert list(from_csv.columns) == list(schema.ALL_COLUMNS)


def test_load_data_rejects_unknown_extension(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="Unsupported"):
        load_data(path)


def test_load_data_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_data(tmp_path / "nope.csv")
