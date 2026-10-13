"""Anomalous resale price detection (Req: Data Quality Requirement 5).

Heuristic: Tukey's IQR fences (1.5x IQR beyond Q1/Q3), computed per (town, flat_type,
flat_model) group rather than globally, since resale prices vary enormously by those
dimensions - a globally-defined outlier threshold would just rediscover "which town is
expensive" rather than genuinely anomalous transactions. Checked on both raw resale_price
and price_per_sqm (price normalised for flat size), since a price can be unremarkable in
absolute terms but still anomalous once floor area is accounted for (or vice versa).

Groups too small to form a meaningful quartile estimate (< MIN_GROUP_SIZE rows) are left
unflagged rather than guessing.
"""
from __future__ import annotations

import pandas as pd

MIN_GROUP_SIZE = 5
IQR_MULTIPLIER = 1.5
# Fallback for degenerate groups (see _iqr_outlier_mask): how many times the median a value
# must be before it is called anomalous. Deliberately loose - it only has to catch the
# order-of-magnitude errors that Tukey's fences structurally cannot see here.
DEGENERATE_GROUP_RATIO = 3.0
GROUP_COLUMNS = ["town", "flat_type", "flat_model"]


def _iqr_outlier_mask(values: pd.Series) -> pd.Series:
    if len(values) < MIN_GROUP_SIZE:
        return pd.Series(False, index=values.index)

    q1, q3 = values.quantile(0.25), values.quantile(0.75)
    iqr = q3 - q1

    if iqr == 0:
        # More than half the group shares one value, so the fences collapse onto it and
        # Tukey's rule would report nothing - not even a price 10x the rest. Fall back to a
        # ratio-against-median test so a degenerate group still gets screened.
        median = values.median()
        if median <= 0:
            return pd.Series(False, index=values.index)
        ratio = values / median
        return (ratio > DEGENERATE_GROUP_RATIO) | (ratio < 1 / DEGENERATE_GROUP_RATIO)

    lower, upper = q1 - IQR_MULTIPLIER * iqr, q3 + IQR_MULTIPLIER * iqr
    return (values < lower) | (values > upper)


def add_anomaly_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["price_per_sqm"] = df["resale_price"] / df["floor_area_sqm"]

    price_outlier = df.groupby(GROUP_COLUMNS, group_keys=False)["resale_price"].apply(_iqr_outlier_mask).reindex(df.index)
    psm_outlier = df.groupby(GROUP_COLUMNS, group_keys=False)["price_per_sqm"].apply(_iqr_outlier_mask).reindex(df.index)

    df["is_price_anomalous"] = price_outlier | psm_outlier

    reasons = []
    for is_price, is_psm in zip(price_outlier, psm_outlier):
        parts = []
        if is_price:
            parts.append("resale_price_outlier_in_group")
        if is_psm:
            parts.append("price_per_sqm_outlier_in_group")
        reasons.append(";".join(parts))
    df["price_anomaly_reason"] = reasons
    return df
