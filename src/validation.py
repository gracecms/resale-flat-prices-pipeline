"""Data validation rules + quarantine splitting (Req: Data Quality Requirements 3 and 6).

Town / Flat Type / Flat Model / storey_range are validated against domains observed in the
Jan-2012 slice (the "strict authoritative set" per the spec). A handful of additional sanity
rules are bundled in since the spec explicitly invites "any additional rules deemed
appropriate". Every failing row is tagged with a semicolon-joined `quarantine_reason` rather
than just dropped, so the quarantine bucket stays auditable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DOMAIN_COLUMNS = ["town", "flat_type", "flat_model", "storey_range"]
REQUIRED_COLUMNS = [
    "month", "town", "flat_type", "block", "street_name",
    "storey_range", "floor_area_sqm", "flat_model", "lease_commence_date", "resale_price",
]

# Generous but non-trivial sanity bounds, based on inspecting the actual raw files
# (observed floor_area_sqm ranges ~28-367 sqm, resale_price always > 0).
MIN_FLOOR_AREA_SQM = 20
MAX_FLOOR_AREA_SQM = 500


def build_authoritative_domains(jan_2012_df: pd.DataFrame) -> dict[str, set]:
    """Build the allowed value sets from the authoritative month's slice.

    Guarded because this is the pipeline's one dependency on an external file still having the
    shape we expect: if the authoritative slice ever came back empty (a renamed column, a
    changed date range upstream), every domain would be empty and *every* row in the dataset
    would be silently quarantined rather than the pipeline failing.
    """
    if jan_2012_df.empty:
        raise ValueError(
            "Authoritative slice is empty - no rows found for the authoritative month. "
            "Every row would be quarantined; check the source files still cover it."
        )
    domains = {col: set(jan_2012_df[col].dropna().unique()) for col in DOMAIN_COLUMNS}
    empty = sorted(col for col, values in domains.items() if not values)
    if empty:
        raise ValueError(f"Authoritative domains came back empty for: {empty}")
    return domains


def validate(df: pd.DataFrame, domains: dict[str, set], *, scope_start: str, scope_end: str) -> pd.DataFrame:
    """Return a copy of df with a `quarantine_reason` column: empty string if the row passes,
    otherwise a semicolon-joined list of failed rule names."""
    df = df.copy()
    flags: dict[str, pd.Series] = {}

    # Required fields present.
    for col in REQUIRED_COLUMNS:
        flags[f"missing_{col}"] = df[col].isna()

    # Domain membership (Town / Flat Type / Flat Model / storey_range vs Jan-2012 authority).
    for col, allowed in domains.items():
        flags[f"invalid_{col}"] = ~df[col].isin(allowed) & df[col].notna()

    # Month in scope and well-formed.
    month_ok = df["month"].between(scope_start, scope_end)
    flags["month_out_of_scope"] = ~month_ok & df["month"].notna()

    # Numeric sanity.
    price_numeric = pd.to_numeric(df["resale_price"], errors="coerce")
    flags["invalid_resale_price"] = (price_numeric <= 0) | price_numeric.isna()

    area_numeric = pd.to_numeric(df["floor_area_sqm"], errors="coerce")
    flags["implausible_floor_area_sqm"] = (
        area_numeric.isna() | (area_numeric < MIN_FLOOR_AREA_SQM) | (area_numeric > MAX_FLOOR_AREA_SQM)
    )

    # Exact full-row duplicates: keep the first occurrence as a legitimate record, quarantine
    # the rest as duplicates (Output group table explicitly calls out duplicates).
    flags["duplicate_record"] = df.duplicated(keep="first")

    flag_df = pd.DataFrame(flags)
    flag_names = np.array(flag_df.columns)
    flag_matrix = flag_df.to_numpy()
    df["quarantine_reason"] = [";".join(flag_names[row]) for row in flag_matrix]
    return df


def split_validated(validated_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into (cleaned, quarantined) based on quarantine_reason."""
    is_clean = validated_df["quarantine_reason"] == ""
    cleaned = validated_df[is_clean].drop(columns=["quarantine_reason"]).reset_index(drop=True)
    quarantined = validated_df[~is_clean].reset_index(drop=True)
    return cleaned, quarantined
