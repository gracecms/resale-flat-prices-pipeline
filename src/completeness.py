"""Per-month completeness check on the cleaned output.

Row-count reconciliation (cleaned + quarantined == combined) proves nothing was *lost*, but it
cannot tell you whether what survived is still usable. A validation rule that rejects most of a
single month leaves a hole in the time series that reconciles perfectly and is invisible in the
totals - which is exactly what happened here: HDB published Mar-May 2012 in 5-storey bands, the
strict Jan-2012 storey_range domain rejects them, and three months all but vanish from the
cleaned data.

This check measures retention month by month and flags any month that is missing outright or
retains less than a threshold share of its rows. The same logic is intended to run as the
publish gate in the operationalised pipeline (see architecture/README.md), where a flagged month
should stop publication rather than just be reported.
"""
from __future__ import annotations

import pandas as pd

DEFAULT_MIN_RETENTION_PCT = 50.0


def expected_months(scope_start: str, scope_end: str) -> list[str]:
    return [str(p) for p in pd.period_range(scope_start, scope_end, freq="M")]


def monthly_completeness(combined: pd.DataFrame, cleaned: pd.DataFrame, *, scope_start: str,
                         scope_end: str, min_retention_pct: float = DEFAULT_MIN_RETENTION_PCT
                         ) -> pd.DataFrame:
    """One row per in-scope month: source rows, cleaned rows, retention %, and a flag."""
    months = pd.Index(expected_months(scope_start, scope_end), name="month")
    source = combined.groupby("month").size().reindex(months, fill_value=0)
    kept = cleaned.groupby("month").size().reindex(months, fill_value=0)

    retention = (100 * kept / source.where(source > 0)).round(1)
    table = pd.DataFrame({"source_rows": source, "cleaned_rows": kept, "retention_pct": retention})
    table["flag"] = ""
    table.loc[table["source_rows"] == 0, "flag"] = "missing_from_source"
    low = (table["source_rows"] > 0) & (table["retention_pct"] < min_retention_pct)
    table.loc[low, "flag"] = f"retention_below_{min_retention_pct:g}pct"
    return table.reset_index()


def flagged_months(completeness: pd.DataFrame) -> pd.DataFrame:
    return completeness[completeness["flag"] != ""].reset_index(drop=True)
