"""Data cleaning: string normalisation, country/status standardisation, deduplication."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from marketing_report import schema

logger = logging.getLogger(__name__)

# Aliases (lower-case) -> ISO 3166-1 alpha-3.
COUNTRY_ALIASES: dict[str, str] = {
    "united states": "USA",
    "united states of america": "USA",
    "usa": "USA",
    "us": "USA",
    "u.s.": "USA",
    "u.s.a.": "USA",
    "america": "USA",
    "canada": "CAN",
    "can": "CAN",
    "mexico": "MEX",
    "méxico": "MEX",
    "mex": "MEX",
    "united kingdom": "GBR",
    "uk": "GBR",
    "u.k.": "GBR",
    "great britain": "GBR",
    "britain": "GBR",
    "england": "GBR",
    "gbr": "GBR",
    "germany": "DEU",
    "deutschland": "DEU",
    "deu": "DEU",
    "france": "FRA",
    "fra": "FRA",
    "italy": "ITA",
    "italia": "ITA",
    "ita": "ITA",
    "spain": "ESP",
    "españa": "ESP",
    "espana": "ESP",
    "esp": "ESP",
    "netherlands": "NLD",
    "holland": "NLD",
    "nld": "NLD",
    "china": "CHN",
    "prc": "CHN",
    "chn": "CHN",
    "japan": "JPN",
    "jpn": "JPN",
    "india": "IND",
    "ind": "IND",
    "australia": "AUS",
    "aus": "AUS",
    "singapore": "SGP",
    "sgp": "SGP",
    "brazil": "BRA",
    "brasil": "BRA",
    "bra": "BRA",
    "argentina": "ARG",
    "arg": "ARG",
    "chile": "CHL",
    "chl": "CHL",
    "colombia": "COL",
    "col": "COL",
}

# Title-cased variants -> canonical status.
STATUS_ALIASES: dict[str, str] = {
    "No-Show": schema.NO_SHOW,
    "Noshow": schema.NO_SHOW,
    "No_Show": schema.NO_SHOW,
    "Did Not Show": schema.NO_SHOW,
    "Absent": schema.NO_SHOW,
    "Reg": schema.REGISTERED,
    "Registration": schema.REGISTERED,
    "Sign Up": schema.REGISTERED,
    "Signup": schema.REGISTERED,
    "Attend": schema.ATTENDED,
    "Present": schema.ATTENDED,
    "Showed Up": schema.ATTENDED,
    "Response": schema.RESPONDED,
    "Reply": schema.RESPONDED,
    "Answered": schema.RESPONDED,
}


@dataclass
class CleaningReport:
    rows_in: int = 0
    rows_out: int = 0
    empty_rows_removed: int = 0
    invalid_status_removed: int = 0
    duplicates_removed: int = 0
    unmapped_countries: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.steps.append(message)
        logger.info(message)


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Return a cleaned copy of ``raw`` and a report of what was changed."""
    report = CleaningReport(rows_in=len(raw))
    df = raw.copy()

    df = _drop_empty_rows(df, report)
    df = normalise_strings(df)
    report.log("Trimmed and collapsed whitespace in text columns; blank strings set to missing")
    df = _standardise_countries(df, report)
    df = _standardise_status(df, report)
    df = _parse_timestamps(df, report)
    df = _deduplicate(df, report)

    report.rows_out = len(df)
    return df.reset_index(drop=True), report


def normalise_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Strip/collapse whitespace in text columns without turning missing values into text."""
    df = df.copy()
    text_columns = df.select_dtypes(include=["object", "string"]).columns
    for column in text_columns:
        values = df[column]
        is_text = values.map(lambda v: isinstance(v, str))
        cleaned = values[is_text].str.strip().str.replace(r"\s+", " ", regex=True)
        df[column] = values.where(~is_text, cleaned).replace("", pd.NA)
    return df


def standardise_country(value: object) -> object:
    """Map a free-text country to an ISO-3 code; unknown values are returned title-cased."""
    if not isinstance(value, str):
        return value
    return COUNTRY_ALIASES.get(value.strip().lower(), value.strip().title())


def standardise_status(values: pd.Series) -> pd.Series:
    """Title-case statuses and map known spelling variants to the canonical values."""
    return values.str.strip().str.title().replace(STATUS_ALIASES)


def _drop_empty_rows(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    before = len(df)
    df = df.dropna(how="all")
    report.empty_rows_removed = before - len(df)
    if report.empty_rows_removed:
        report.log(f"Removed {report.empty_rows_removed} completely empty rows")
    return df


def _standardise_countries(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    if schema.COUNTRY not in df.columns:
        return df
    original = df[schema.COUNTRY]
    df[schema.COUNTRY] = original.map(standardise_country)
    known = original.dropna().str.lower().isin(COUNTRY_ALIASES.keys())
    report.unmapped_countries = sorted(original.dropna()[~known].str.title().unique().tolist())
    if report.unmapped_countries:
        logger.warning("Countries without an ISO-3 mapping: %s", report.unmapped_countries)
    report.log("Standardised country names to ISO 3166-1 alpha-3 codes")
    return df


def _standardise_status(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    df[schema.STATUS] = standardise_status(df[schema.STATUS])
    before = len(df)
    df = df[df[schema.STATUS].isin(schema.VALID_STATUSES)]
    report.invalid_status_removed = before - len(df)
    if report.invalid_status_removed:
        report.log(f"Removed {report.invalid_status_removed} rows with unrecognised status values")
    report.log("Standardised Prospect Status values")
    return df


def _parse_timestamps(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    for column in (schema.OPT_IN_TS, schema.OPT_OUT_TS):
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")
    report.log("Parsed opt-in/opt-out timestamps (unparseable values set to missing)")
    return df


def _deduplicate(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    """Keep one row per prospect: the furthest funnel stage, then the latest opt-in."""
    if schema.PROSPECT_ID not in df.columns:
        return df
    df = df.assign(_rank=df[schema.STATUS].map(schema.STATUS_RANK))
    sort_by = ["_rank"]
    if schema.OPT_IN_TS in df.columns:
        sort_by.append(schema.OPT_IN_TS)
    df = df.sort_values(sort_by, ascending=False, na_position="last", kind="stable")

    has_id = df[schema.PROSPECT_ID].notna()
    deduped = pd.concat(
        [df[has_id].drop_duplicates(subset=[schema.PROSPECT_ID], keep="first"), df[~has_id]]
    ).sort_index()
    report.duplicates_removed = len(df) - len(deduped)
    if report.duplicates_removed:
        report.log(
            f"Removed {report.duplicates_removed} duplicate prospect rows "
            "(kept furthest funnel stage, then most recent opt-in)"
        )
    return deduped.drop(columns="_rank")
