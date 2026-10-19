"""Feature engineering: job categories, seniority, regions, channel groups and funnel flags."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

import pandas as pd

from marketing_report import schema

logger = logging.getLogger(__name__)

EXECUTIVE = "Executive"
DECISION_MAKER = "Decision Maker"
PRACTITIONER = "Practitioner"
OTHER = "Other"
UNKNOWN = "Unknown"

EXECUTIVE_KEYWORDS = (
    "president", "vice president", "vp", "ceo", "cto", "cmo", "cfo", "coo", "cso", "cro", "cio",
    "chief", "founder", "co-founder", "owner", "partner", "board", "chairman", "chairwoman",
)  # fmt: skip
DECISION_MAKER_KEYWORDS = ("manager", "director", "head", "lead", "supervisor")
PRACTITIONER_KEYWORDS = (
    "analyst", "specialist", "engineer", "coordinator", "associate", "junior", "assistant",
    "intern", "trainee", "consultant", "developer", "designer", "researcher", "administrator",
    "scientist", "programmer",
)  # fmt: skip

SENIOR_KEYWORDS = ("senior", "sr", "lead", "principal", "chief")
JUNIOR_KEYWORDS = ("junior", "jr", "associate", "intern", "trainee")

REGIONS: dict[str, tuple[str, ...]] = {
    "North America": ("USA", "CAN", "MEX"),
    "Europe": ("GBR", "DEU", "FRA", "ITA", "ESP", "NLD"),
    "Asia Pacific": ("CHN", "JPN", "IND", "AUS", "SGP"),
    "Latin America": ("BRA", "ARG", "CHL", "COL"),
}
COUNTRY_TO_REGION = {code: region for region, codes in REGIONS.items() for code in codes}

CHANNEL_GROUP_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Paid Media": ("advertisement", "ad", "ads", "paid", "ppc", "adwords"),
    "Social Media": ("social", "facebook", "linkedin", "twitter"),
    "Referral": ("referral", "word of mouth", "recommendation"),
    "Events": ("trade show", "event", "conference", "webinar"),
    "Content Marketing": ("content", "blog", "seo", "organic"),
    "Email Marketing": ("email", "newsletter"),
}


def _keyword_pattern(keywords: Iterable[str]) -> re.Pattern[str]:
    """Whole-word, case-insensitive matcher (so 'cto' does not match 'director')."""
    alternatives = "|".join(re.escape(k) for k in sorted(keywords, key=len, reverse=True))
    return re.compile(rf"(?<![a-z])(?:{alternatives})(?![a-z])", re.IGNORECASE)


_EXECUTIVE_RE = _keyword_pattern(EXECUTIVE_KEYWORDS)
_DECISION_MAKER_RE = _keyword_pattern(DECISION_MAKER_KEYWORDS)
_PRACTITIONER_RE = _keyword_pattern(PRACTITIONER_KEYWORDS)
_SENIOR_RE = _keyword_pattern(SENIOR_KEYWORDS)
_JUNIOR_RE = _keyword_pattern(JUNIOR_KEYWORDS)
_CHANNEL_RES = {group: _keyword_pattern(words) for group, words in CHANNEL_GROUP_KEYWORDS.items()}


def categorize_job_title(title: object) -> str:
    """Executive > Decision Maker > Practitioner, by highest-authority keyword found."""
    if not isinstance(title, str) or not title.strip():
        return OTHER
    if _EXECUTIVE_RE.search(title):
        return EXECUTIVE
    if _DECISION_MAKER_RE.search(title):
        return DECISION_MAKER
    if _PRACTITIONER_RE.search(title):
        return PRACTITIONER
    return OTHER


def seniority_level(title: object) -> str:
    if not isinstance(title, str) or not title.strip():
        return UNKNOWN
    if _SENIOR_RE.search(title):
        return "Senior"
    if _JUNIOR_RE.search(title):
        return "Junior"
    return "Mid-Level"


def region_for_country(iso3: object) -> str:
    if not isinstance(iso3, str):
        return UNKNOWN
    return COUNTRY_TO_REGION.get(iso3.upper(), "Other Regions")


def channel_group(channel: object) -> str:
    if not isinstance(channel, str):
        return UNKNOWN
    for group, pattern in _CHANNEL_RES.items():
        if pattern.search(channel):
            return group
    return OTHER


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features. Expects the output of :func:`marketing_report.cleaning.clean`."""
    out = df.copy()
    status = out[schema.STATUS]

    # Status is the furthest stage reached, so attendance is cumulative:
    # a registered prospect necessarily attended the demo first.
    out[schema.IS_ATTENDED] = status.isin([schema.ATTENDED, schema.REGISTERED]).astype(int)
    out[schema.IS_NO_SHOW] = (status == schema.NO_SHOW).astype(int)
    out[schema.IS_REGISTERED] = (status == schema.REGISTERED).astype(int)

    out[schema.JOB_CATEGORY] = out[schema.JOB_TITLE].map(categorize_job_title)
    out[schema.SENIORITY] = out[schema.JOB_TITLE].map(seniority_level)
    out[schema.REGION] = out[schema.COUNTRY].map(region_for_country)
    out[schema.CHANNEL_GROUP] = out[schema.SOURCE].map(channel_group)

    logger.info("Added %d derived columns", out.shape[1] - df.shape[1])
    return out
