"""Remaining lease calculation as of a fixed reference date (Req: Data Quality Requirement 4).

Assumption: HDB lease is 99 years from `lease_commence_date` (a year only, per the source
data), so the lease start is taken as 1 Jan of that year. Remaining lease is computed as of
2027-01-01, floored down to whole years and whole months (no partial month/day rounding up).

Side effect of this assumption worth flagging explicitly: since lease start (and therefore
lease expiry) always falls on 1 January, `remaining_lease_months` is always 0 for every row -
that is correct given year-only source data, not a bug in the calculation.
"""
from __future__ import annotations

import pandas as pd

from .schema import ASSUMED_LEASE_YEARS, REMAINING_LEASE_REFERENCE_DATE


def add_remaining_lease(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    lease_commence_year = pd.to_numeric(df["lease_commence_date"], errors="raise").astype(int)
    lease_start = pd.to_datetime(lease_commence_year.astype(str) + "-01-01")
    lease_expiry = lease_start + pd.DateOffset(years=ASSUMED_LEASE_YEARS)
    reference_date = pd.Timestamp(REMAINING_LEASE_REFERENCE_DATE)

    total_months = (
        (lease_expiry.dt.year - reference_date.year) * 12
        + (lease_expiry.dt.month - reference_date.month)
    )
    # If expiry's day-of-month hasn't been reached yet relative to the reference day, that
    # partial month doesn't count yet - floor it off (lease commence/expiry is always the
    # 1st, and the reference date 2027-01-01 is also the 1st, so this is a no-op here, but
    # kept explicit in case the reference date ever changes to a non-1st-of-month date).
    partial_month_not_reached = lease_expiry.dt.day < reference_date.day
    total_months = total_months - partial_month_not_reached.astype(int)
    total_months = total_months.clip(lower=0)

    df["remaining_lease_years"] = total_months // 12
    df["remaining_lease_months"] = total_months % 12
    df["remaining_lease_display"] = (
        df["remaining_lease_years"].astype(str) + " years " + df["remaining_lease_months"].astype(str) + " months"
    )
    return df
