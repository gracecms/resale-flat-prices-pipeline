"""Load, scope, and combine the source files into one master dataset (Req: Data Quality 1).

Rows are kept by their own `month` value falling inside the scope, so no per-file date
windows are needed. Two guards replace what hardcoded windows used to guarantee implicitly:

- **No month may come from two files.** Upstream periods are contiguous today; if
  data.gov.sg ever republished overlapping files, combining them would silently double-count
  every transaction in the overlap. The combine step fails instead.
- **Exactly one file must contain the authoritative month.** That file's columns become the
  master schema (the Jan-2012 file has no `remaining_lease` column, so later files' copy of it
  is not carried forward - the pipeline derives its own in `lease.py`).

Raw files on disk are never modified; all trimming happens on in-memory dataframes.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import SourceDataset


def combine_sources(sources: list[SourceDataset], raw_dir: Path, *, scope_start: str,
                    scope_end: str, authoritative_month: str
                    ) -> tuple[pd.DataFrame, pd.DataFrame, SourceDataset]:
    """Return (combined master dataset, per-source raw-stage statistics, authoritative source)."""
    scoped: dict[SourceDataset, pd.DataFrame] = {}
    stats = []
    for source in sources:
        raw = pd.read_csv(raw_dir / source.filename, dtype=str)
        in_scope = raw[raw["month"].between(scope_start, scope_end)]
        scoped[source] = in_scope
        stats.append({
            "dataset": source.name,
            "raw_rows": len(raw),
            "raw_months": f"{raw['month'].min()} to {raw['month'].max()}",
            "in_scope_rows": len(in_scope),
            "out_of_scope_rows": len(raw) - len(in_scope),
            "raw_columns": len(raw.columns),
        })

    seen: dict[str, str] = {}
    for source, frame in scoped.items():
        for month in frame["month"].unique():
            if month in seen:
                raise ValueError(
                    f"Month {month} appears in both '{seen[month]}' and '{source.name}'; "
                    "combining them would double-count every transaction in that month."
                )
            seen[month] = source.name

    authoritative = [s for s, frame in scoped.items() if (frame["month"] == authoritative_month).any()]
    if len(authoritative) != 1:
        raise ValueError(
            f"Expected exactly one source containing {authoritative_month}, found {len(authoritative)}."
        )
    master_columns = list(scoped[authoritative[0]].columns)

    for source, frame in scoped.items():
        missing = set(master_columns) - set(frame.columns)
        if missing:
            raise ValueError(f"'{source.name}' lacks master-schema columns: {sorted(missing)}")

    for row, (source, frame) in zip(stats, scoped.items()):
        row["columns_not_carried"] = ", ".join(c for c in frame.columns if c not in master_columns) or "-"

    combined = pd.concat([frame[master_columns] for frame in scoped.values()], ignore_index=True)
    for col in ("floor_area_sqm", "resale_price", "lease_commence_date"):
        combined[col] = pd.to_numeric(combined[col], errors="coerce")
    return combined, pd.DataFrame(stats), authoritative[0]
