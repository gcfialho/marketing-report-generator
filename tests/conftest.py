from __future__ import annotations

import pandas as pd
import pytest

from marketing_report import schema


def make_raw(rows: list[dict]) -> pd.DataFrame:
    """Build a raw frame with the full schema; unspecified columns are missing."""
    return pd.DataFrame(rows, columns=list(schema.ALL_COLUMNS))


@pytest.fixture
def raw_small() -> pd.DataFrame:
    return make_raw(
        [
            {
                schema.PROSPECT_ID: "P1",
                schema.STATUS: "Registered",
                schema.SOURCE: "Referral",
                schema.COUNTRY: "United States",
                schema.JOB_TITLE: "Senior Data Analyst",
                schema.OPT_IN_TS: "2023-03-01",
            },
            {
                schema.PROSPECT_ID: "P2",
                schema.STATUS: " no-show ",
                schema.SOURCE: "Advertisement",
                schema.COUNTRY: "  usa ",
                schema.JOB_TITLE: "IT   Director",
                schema.OPT_IN_TS: "2023-03-02",
            },
            {
                schema.PROSPECT_ID: "P3",
                schema.STATUS: "Attended",
                schema.SOURCE: "Trade Show",
                schema.COUNTRY: "Argentina",
                schema.JOB_TITLE: "VP, Data Analytics",
                schema.OPT_IN_TS: "2023-03-03",
            },
            # Duplicate of P2 that progressed further in the funnel but opted in earlier.
            {
                schema.PROSPECT_ID: "P2",
                schema.STATUS: "Attended",
                schema.SOURCE: "Advertisement",
                schema.COUNTRY: "USA",
                schema.JOB_TITLE: "IT Director",
                schema.OPT_IN_TS: "2023-01-01",
            },
            {
                schema.PROSPECT_ID: "P4",
                schema.STATUS: "Bogus",
                schema.SOURCE: "Advertisement",
                schema.COUNTRY: "Canada",
                schema.JOB_TITLE: "Analyst",
            },
            {},  # completely empty row
        ]
    )
