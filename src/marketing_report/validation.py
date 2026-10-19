"""Input loading and structural/quality validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from marketing_report import schema
from marketing_report.cleaning import standardise_status

logger = logging.getLogger(__name__)

EXCEL_SUFFIXES = {".xlsx", ".xls"}
CSV_SUFFIXES = {".csv"}


class SchemaError(ValueError):
    """Raised when the input is missing columns required by the analysis."""


@dataclass(frozen=True)
class ValidationReport:
    n_rows: int
    n_columns: int
    missing_required: list[str]
    missing_optional: list[str]
    extra_columns: list[str]
    missing_by_column: dict[str, int]
    completeness_pct: float
    duplicate_prospect_ids: int
    unknown_statuses: dict[str, int] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not self.missing_required


def load_data(path: str | Path) -> pd.DataFrame:
    """Load a prospect export from CSV or Excel, keeping IDs as strings."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    id_dtypes = {schema.PROSPECT_ID: str, schema.ACCOUNT_ID: str, schema.CAMPAIGN_ID: str}
    if suffix in EXCEL_SUFFIXES:
        df = pd.read_excel(path, dtype=id_dtypes)
    elif suffix in CSV_SUFFIXES:
        df = pd.read_csv(path, dtype=id_dtypes)
    else:
        raise ValueError(f"Unsupported file type '{suffix}'. Use .csv, .xlsx or .xls.")

    logger.info("Loaded %s rows x %s columns from %s", len(df), df.shape[1], path)
    return df


def validate(df: pd.DataFrame) -> ValidationReport:
    """Check required columns and summarise data quality.

    Validation never mutates the frame; cleaning decisions belong to the cleaning step.
    """
    columns = set(df.columns)
    missing_by_column = {c: int(n) for c, n in df.isna().sum().items() if n > 0}
    total_cells = df.size
    completeness = 100.0 * (1 - sum(missing_by_column.values()) / total_cells) if total_cells else 0

    duplicates = 0
    if schema.PROSPECT_ID in columns:
        duplicates = int(df[schema.PROSPECT_ID].dropna().duplicated().sum())

    unknown_statuses: dict[str, int] = {}
    if schema.STATUS in columns:
        normalised = standardise_status(df[schema.STATUS].dropna().astype(str))
        unknown = normalised[~normalised.isin(schema.VALID_STATUSES)]
        unknown_statuses = {str(k): int(v) for k, v in unknown.value_counts().items()}

    return ValidationReport(
        n_rows=len(df),
        n_columns=df.shape[1],
        missing_required=[c for c in schema.REQUIRED_COLUMNS if c not in columns],
        missing_optional=[c for c in schema.OPTIONAL_COLUMNS if c not in columns],
        extra_columns=[c for c in df.columns if c not in schema.ALL_COLUMNS],
        missing_by_column=missing_by_column,
        completeness_pct=round(completeness, 1),
        duplicate_prospect_ids=duplicates,
        unknown_statuses=unknown_statuses,
    )


def validate_or_raise(df: pd.DataFrame) -> ValidationReport:
    report = validate(df)
    if not report.is_valid:
        raise SchemaError(f"Missing required columns: {', '.join(report.missing_required)}")
    if report.missing_optional:
        logger.warning("Optional columns not present: %s", ", ".join(report.missing_optional))
    logger.info(
        "Validation passed: completeness %.1f%%, %d duplicate prospect IDs",
        report.completeness_pct,
        report.duplicate_prospect_ids,
    )
    return report
