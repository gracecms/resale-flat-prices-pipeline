"""Lightweight, dependency-free data profiling (Req: Data profiling).

Produces a plain dict of profiling facts per dataframe rather than pulling in a heavy
profiling framework - keeps the pipeline's only dependencies pandas/numpy, and keeps the
profiling logic auditable in a handful of lines instead of an opaque HTML report.
"""
from __future__ import annotations

import pandas as pd

CATEGORICAL_COLUMNS = ["town", "flat_type", "flat_model", "storey_range"]
NUMERIC_COLUMNS = ["floor_area_sqm", "resale_price", "lease_commence_date"]


def profile_dataframe(df: pd.DataFrame, *, top_n: int = 15) -> dict:
    """Return a structured profiling summary: shape, per-column missingness/cardinality,
    numeric stats, and top value counts for categorical columns."""
    n_rows = len(df)
    columns = []
    for col in df.columns:
        series = df[col]
        n_missing = int(series.isna().sum())
        entry = {
            "column": col,
            "dtype": str(series.dtype),
            "n_missing": n_missing,
            "pct_missing": round(100 * n_missing / n_rows, 3) if n_rows else 0.0,
            "n_unique": int(series.nunique(dropna=True)),
        }
        if col in NUMERIC_COLUMNS:
            numeric = pd.to_numeric(series, errors="coerce")
            entry["numeric_stats"] = {
                "min": _safe_float(numeric.min()),
                "max": _safe_float(numeric.max()),
                "mean": _safe_float(numeric.mean()),
                "median": _safe_float(numeric.median()),
                "std": _safe_float(numeric.std()),
            }
        if col in CATEGORICAL_COLUMNS:
            entry["top_values"] = series.value_counts(dropna=True).head(top_n).to_dict()
        columns.append(entry)

    n_exact_duplicates = int(df.duplicated(keep=False).sum())

    return {
        "n_rows": n_rows,
        "n_columns": len(df.columns),
        "n_exact_duplicate_rows": n_exact_duplicates,
        "month_range": (str(df["month"].min()), str(df["month"].max())) if "month" in df.columns else None,
        "columns": columns,
    }


def _safe_float(value) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def profile_to_markdown(profile: dict, title: str) -> str:
    lines = [f"### {title}", ""]
    lines.append(f"- Rows: **{profile['n_rows']:,}** | Columns: **{profile['n_columns']}**")
    if profile.get("month_range"):
        lines.append(f"- Month range: **{profile['month_range'][0]} to {profile['month_range'][1]}**")
    lines.append(f"- Exact duplicate rows (both/all copies counted): **{profile['n_exact_duplicate_rows']:,}**")
    lines.append("")
    lines.append("| Column | dtype | % missing | # unique | notes |")
    lines.append("|---|---|---|---|---|")
    for col in profile["columns"]:
        notes = ""
        if "numeric_stats" in col:
            s = col["numeric_stats"]
            notes = f"min={s['min']}, max={s['max']}, mean={s['mean']:.1f}" if s["mean"] is not None else ""
        elif "top_values" in col:
            top = list(col["top_values"].items())[:3]
            notes = ", ".join(f"{k}={v}" for k, v in top)
        lines.append(f"| {col['column']} | {col['dtype']} | {col['pct_missing']}% | {col['n_unique']} | {notes} |")
    lines.append("")
    return "\n".join(lines)
