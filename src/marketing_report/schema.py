"""Column names and domain constants shared across the pipeline."""

from typing import Final

# Raw input columns (prospect-level marketing export).
CAMPAIGN_ID: Final = "Campaign ID"
CAMPAIGN_NAME: Final = "Campaign Name"
STATUS: Final = "Prospect Status"
ACCOUNT_ID: Final = "Account ID"
ACCOUNT_NAME: Final = "Account Name"
DOMAIN: Final = "domain"
COUNTRY: Final = "Country"
PROSPECT_ID: Final = "Prospect ID"
OPT_IN: Final = "Opt-In"
OPT_IN_SOURCE: Final = "Opt-In Source"
OPT_IN_TS: Final = "Opt-In Timestamp"
OPT_OUT_TS: Final = "Opt-Out Timestamp"
JOB_TITLE: Final = "Job Title"
SOURCE: Final = "Prospect Source"

REQUIRED_COLUMNS: Final = (STATUS, SOURCE, COUNTRY, JOB_TITLE)
OPTIONAL_COLUMNS: Final = (
    CAMPAIGN_ID,
    CAMPAIGN_NAME,
    ACCOUNT_ID,
    ACCOUNT_NAME,
    DOMAIN,
    PROSPECT_ID,
    OPT_IN,
    OPT_IN_SOURCE,
    OPT_IN_TS,
    OPT_OUT_TS,
)
ALL_COLUMNS: Final = (
    CAMPAIGN_ID,
    CAMPAIGN_NAME,
    STATUS,
    ACCOUNT_ID,
    ACCOUNT_NAME,
    DOMAIN,
    COUNTRY,
    PROSPECT_ID,
    OPT_IN,
    OPT_IN_SOURCE,
    OPT_IN_TS,
    OPT_OUT_TS,
    JOB_TITLE,
    SOURCE,
)

# Prospect Status is the *furthest* stage a prospect reached in the demo funnel:
#   Responded -> (No Show | Attended) -> Registered (free trial after the demo)
# "No Show" is a terminal drop-off after responding, so it is not a stage on the
# happy path; it shares rank 1 with "Attended" only for "furthest stage" ordering
# purposes and is never counted as having attended.
RESPONDED: Final = "Responded"
NO_SHOW: Final = "No Show"
ATTENDED: Final = "Attended"
REGISTERED: Final = "Registered"
VALID_STATUSES: Final = (RESPONDED, NO_SHOW, ATTENDED, REGISTERED)
STATUS_RANK: Final = {RESPONDED: 0, NO_SHOW: 1, ATTENDED: 2, REGISTERED: 3}

# Derived columns created by the transform step.
JOB_CATEGORY: Final = "Job Category"
SENIORITY: Final = "Seniority Level"
REGION: Final = "Geographic Region"
CHANNEL_GROUP: Final = "Channel Group"
IS_ATTENDED: Final = "is_attended"
IS_NO_SHOW: Final = "is_no_show"
IS_REGISTERED: Final = "is_registered"
