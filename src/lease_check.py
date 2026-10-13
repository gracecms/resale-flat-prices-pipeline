"""Cross-check the 99-year lease assumption against HDB's own published remaining_lease.

The brief instructs us to *assume* a 99-year lease and derive remaining lease from
`lease_commence_date`. That assumption is testable: the 2015-onwards source files carry HDB's
own `remaining_lease` column. It is deliberately not part of the master dataset (the Jan-2012
schema is authoritative and does not have it), but it can still be read from the raw files as
an independent reference to answer two questions:

1. Is the 99-year assumption correct?
2. How precise is our derived figure, given `lease_commence_date` is a *year* only?

Question 2 is the one that matters to the Data Science Team: because the source gives only the
commencement year, our computed remaining lease can differ from the true figure by up to
12 months. Measuring that spread turns an unstated limitation into a documented error bar.

Note the source column is not consistently formatted across vintages - whole years as a bare
integer ("70") in the 2015-2016 file, free text ("61 years 04 months") from 2017 - which is a
further reason not to depend on it in the pipeline itself.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .schema import ASSUMED_LEASE_YEARS, SourceDataset


def parse_published_remaining_lease(value: object) -> int | None:
    """Parse HDB's published remaining lease into whole months, across both formats seen."""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if re.fullmatch(r"\d+(\.0+)?", text):  # bare number = whole years
        return int(float(text)) * 12
    years = re.search(r"(\d+)\s*year", text)
    months = re.search(r"(\d+)\s*month", text)
    if not years and not months:
        return None
    return (int(years.group(1)) if years else 0) * 12 + (int(months.group(1)) if months else 0)


def compare_with_published(raw_dir: Path, sources: list[SourceDataset], *, scope_start: str,
                           scope_end: str) -> pd.DataFrame:
    """Compare our derived remaining lease against HDB's published value, per source file.

    Both figures are measured at the transaction month, which is the basis HDB publishes on.
    """
    rows = []
    for source in sources:
        df = pd.read_csv(raw_dir / source.filename, dtype=str)
        if "remaining_lease" not in df.columns:
            continue
        df = df[df["month"].between(scope_start, scope_end)]
        published = df["remaining_lease"].map(parse_published_remaining_lease)
        usable = published.notna()
        if not usable.any():
            continue

        commence_year = pd.to_numeric(df.loc[usable, "lease_commence_date"])
        transaction = pd.PeriodIndex(df.loc[usable, "month"], freq="M")
        derived_months = (commence_year + ASSUMED_LEASE_YEARS) * 12 - (
            transaction.year * 12 + (transaction.month - 1)
        )
        diff = pd.Series(derived_months.values - published[usable].values)

        rows.append({
            "source": source.name,
            "rows_compared": int(usable.sum()),
            "published_format": str(df.loc[usable, "remaining_lease"].iloc[0]),
            "exact_match_pct": round(100 * (diff == 0).mean(), 1),
            "within_12_months_pct": round(100 * (diff.abs() <= 12).mean(), 1),
            "median_abs_diff_months": int(diff.abs().median()),
            "max_abs_diff_months": int(diff.abs().max()),
        })
    return pd.DataFrame(rows)
