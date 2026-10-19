"""Seeded synthetic prospect data with the same schema as the real marketing export.

The generator exists so the pipeline can be run, tested and demonstrated without any
proprietary data. Distributions are loosely shaped like a B2B demo funnel (most prospects
come from advertising, roughly a quarter of demo invitees attend, about half of attendees
start a trial), and a small amount of realistic mess is injected (inconsistent country and
status spellings, whitespace, duplicate prospects, missing values) so every cleaning step
has something to do. All names, IDs and domains are generated.
"""

from __future__ import annotations

import string
from pathlib import Path

import numpy as np
import pandas as pd

from marketing_report import schema

COUNTRIES = {
    "United States": 0.28, "Canada": 0.10, "United Kingdom": 0.10, "Italy": 0.06,
    "India": 0.06, "Mexico": 0.06, "Spain": 0.06, "Brazil": 0.06, "China": 0.06,
    "Argentina": 0.04, "Japan": 0.04, "Germany": 0.04, "France": 0.04,
}  # fmt: skip
COUNTRY_VARIANTS = {
    "United States": ["USA", "U.S.", "united states", "United States of America"],
    "United Kingdom": ["UK", "Great Britain", "england"],
    "Germany": ["Deutschland"],
    "Brazil": ["Brasil"],
    "Spain": ["España"],
}
SOURCES = {"Advertisement": 0.82, "Trade Show": 0.125, "Referral": 0.04, "Social Media": 0.015}

# Funnel parameters by source: P(attend | demo outcome known), P(register | attended).
P_PENDING = 0.094
P_ATTEND = {"Advertisement": 0.26, "Trade Show": 0.30, "Referral": 0.40, "Social Media": 0.22}
P_REGISTER = {"Advertisement": 0.52, "Trade Show": 0.48, "Referral": 0.62, "Social Media": 0.45}
# Multiplicative tweak on P(register | attended) by job category.
JOB_REGISTER_LIFT = {"practitioner": 1.0, "decision_maker": 1.05, "executive": 0.9, "other": 1.0}

ACCOUNT_PREFIXES = (
    "Acorn", "Basalt", "Cedar", "Delta", "Ember", "Fjord", "Granite", "Harbor", "Iris", "Juniper",
    "Kestrel", "Lumen", "Maple", "Northwind", "Onyx", "Pine", "Quarry", "Ridge", "Summit",
    "Tundra", "Umber", "Vale", "Willow", "Zephyr",
)  # fmt: skip
ACCOUNT_SUFFIXES = ("Analytics", "Systems", "Labs", "Software", "Networks", "Group", "Digital")
TLDS = (".com", ".io", ".net", ".org")

PRACTITIONER_ROLES = (
    "Data Analyst", "Business Analyst", "Systems Analyst", "IT Analyst", "Security Analyst",
    "BI Analyst", "Data Engineer", "Software Engineer", "Analytics Engineer", "Data Scientist",
    "Project Coordinator", "Operations Specialist", "Marketing Analyst",
)  # fmt: skip
PRACTITIONER_PREFIXES = ("", "", "", "Senior ", "Sr. ", "Junior ", "Lead ", "Associate ")
DECISION_MAKER_ROLES = (
    "IT Manager", "Data Manager", "Analytics Manager", "Engineering Manager", "PMO Director",
    "Director of IT", "Director, Data Platforms", "Head of Analytics", "Program Manager",
)  # fmt: skip
EXECUTIVE_ROLES = (
    "VP, Data Analytics", "Vice President of Engineering", "Chief Data Officer", "CTO", "CIO",
    "Chief Technology Officer", "Founder", "Co-Founder & CEO", "SVP Operations",
)  # fmt: skip
OTHER_ROLES = ("Social Media", "Student", "Operations", "Procurement", "Facilities")
JOB_MIX = {"practitioner": 0.70, "decision_maker": 0.13, "executive": 0.12, "other": 0.05}

OPT_IN_SOURCES = (
    "online purchase", "social media campaign", "referral program", "newsletter subscription",
    "online contest entry", "event registration", "email subscription", "website form",
)  # fmt: skip
CAMPAIGN_THEMES = ("spring", "summer", "autumn", "winter", "year_end", "launch", "webinar")
CAMPAIGN_KINDS = ("demo_days", "trial_push", "roadshow", "product_tour", "case_study_series")


def _choice(rng: np.random.Generator, weights: dict[str, float], size: int) -> np.ndarray:
    keys = list(weights)
    probs = np.array([weights[k] for k in keys], dtype=float)
    return rng.choice(keys, size=size, p=probs / probs.sum())


def _salesforce_like_id(rng: np.random.Generator, prefix: str) -> str:
    alphabet = list(string.ascii_letters + string.digits)
    return prefix + "".join(rng.choice(alphabet, size=12))


def _job_title(rng: np.random.Generator, kind: str) -> str:
    if kind == "practitioner":
        return str(rng.choice(PRACTITIONER_PREFIXES)) + str(rng.choice(PRACTITIONER_ROLES))
    if kind == "decision_maker":
        return str(rng.choice(DECISION_MAKER_ROLES))
    if kind == "executive":
        return str(rng.choice(EXECUTIVE_ROLES))
    return str(rng.choice(OTHER_ROLES))


def _messy_text(rng: np.random.Generator, value: str, p: float) -> str:
    """With probability ``p``, change casing or pad with whitespace."""
    if rng.random() >= p:
        return value
    return str(rng.choice([value.upper(), value.lower(), f"  {value} ", value.replace(" ", "  ")]))


def generate(n_rows: int = 1000, seed: int = 42, messy: bool = True) -> pd.DataFrame:
    """Generate ``n_rows`` prospect rows (plus a few injected duplicates when ``messy``)."""
    if n_rows < 1:
        raise ValueError("n_rows must be positive")
    rng = np.random.default_rng(seed)

    # Accounts: each has a country, name and domain; prospects belong to accounts.
    n_accounts = max(1, n_rows // 8)
    account_countries = _choice(rng, COUNTRIES, n_accounts)
    accounts = []
    for i in range(n_accounts):
        name = (
            f"{ACCOUNT_PREFIXES[i % len(ACCOUNT_PREFIXES)]} "
            f"{ACCOUNT_SUFFIXES[(i // len(ACCOUNT_PREFIXES)) % len(ACCOUNT_SUFFIXES)]}"
        )
        domain = name.lower().replace(" ", "") + str(rng.choice(TLDS))
        accounts.append((_salesforce_like_id(rng, "001SY"), name, domain, account_countries[i]))
    account_idx = rng.integers(0, n_accounts, size=n_rows)

    campaigns = [f"{t}_{k}" for t in CAMPAIGN_THEMES for k in CAMPAIGN_KINDS]
    campaign_idx = rng.integers(0, len(campaigns), size=n_rows)

    sources = _choice(rng, SOURCES, n_rows)
    job_kinds = _choice(rng, JOB_MIX, n_rows)

    statuses = []
    for source, kind in zip(sources, job_kinds, strict=True):
        if rng.random() < P_PENDING:
            statuses.append(schema.RESPONDED)
        elif rng.random() >= P_ATTEND[source]:
            statuses.append(schema.NO_SHOW)
        elif rng.random() < min(1.0, P_REGISTER[source] * JOB_REGISTER_LIFT[kind]):
            statuses.append(schema.REGISTERED)
        else:
            statuses.append(schema.ATTENDED)

    start = pd.Timestamp("2023-01-15 06:11")
    opt_in_ts = start + pd.to_timedelta(rng.integers(0, 320, size=n_rows), unit="D")
    opt_in_ts = pd.Series(opt_in_ts).where(rng.random(n_rows) >= 0.046)
    opt_out_mask = rng.random(n_rows) < 0.03
    opt_out_ts = pd.Series(pd.NaT, index=range(n_rows), dtype="datetime64[ns]")
    opt_out_base = opt_in_ts.fillna(start)
    opt_out_ts[opt_out_mask] = opt_out_base[opt_out_mask] + pd.to_timedelta(
        rng.integers(1, 120, size=int(opt_out_mask.sum())), unit="D"
    )

    rows = []
    for i in range(n_rows):
        acc_id, acc_name, domain, country = accounts[account_idx[i]]
        campaign = campaigns[campaign_idx[i]]
        if messy and country in COUNTRY_VARIANTS and rng.random() < 0.08:
            country = str(rng.choice(COUNTRY_VARIANTS[country]))
        status = statuses[i]
        if messy and rng.random() < 0.03:
            status = {schema.NO_SHOW: "no-show", schema.REGISTERED: "registered"}.get(
                status, status.lower()
            )
        rows.append(
            {
                schema.CAMPAIGN_ID: f"FY23-Q{1 + campaign_idx[i] % 4}-global-SYN-{campaign}",
                schema.CAMPAIGN_NAME: campaign.replace("_", " ").title(),
                schema.STATUS: status,
                schema.ACCOUNT_ID: acc_id,
                schema.ACCOUNT_NAME: acc_name,
                schema.DOMAIN: domain,
                schema.COUNTRY: _messy_text(rng, country, 0.03) if messy else country,
                schema.PROSPECT_ID: _salesforce_like_id(rng, "003SY"),
                schema.OPT_IN: str(rng.choice(["Yes", "No", ""], p=[0.956, 0.03, 0.014])),
                schema.OPT_IN_SOURCE: (
                    None if rng.random() < 0.125 else str(rng.choice(OPT_IN_SOURCES))
                ),
                schema.OPT_IN_TS: opt_in_ts[i],
                schema.OPT_OUT_TS: opt_out_ts[i],
                schema.JOB_TITLE: (
                    _messy_text(rng, _job_title(rng, job_kinds[i]), 0.05)
                    if messy
                    else _job_title(rng, job_kinds[i])
                ),
                schema.SOURCE: sources[i],
            }
        )

    df = pd.DataFrame(rows, columns=list(schema.ALL_COLUMNS))
    df[schema.OPT_IN] = df[schema.OPT_IN].replace("", pd.NA)

    if messy:
        # Same prospect touched by a second campaign: duplicate ID, different campaign/date.
        n_dupes = max(1, n_rows // 300)
        dupes = df.sample(n=n_dupes, random_state=seed).copy()
        dupes[schema.CAMPAIGN_NAME] = "Webinar Follow Up"
        dupes[schema.CAMPAIGN_ID] = "FY23-Q4-global-SYN-webinar_follow_up"
        dupes[schema.OPT_IN_TS] = dupes[schema.OPT_IN_TS] + pd.Timedelta(days=14)
        df = pd.concat([df, dupes], ignore_index=True)
    return df


def write(df: pd.DataFrame, path: str | Path) -> Path:
    """Write to CSV or Excel depending on the file extension."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False)
    return path
