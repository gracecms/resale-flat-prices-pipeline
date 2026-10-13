"""Resale Identifier construction + uniqueness resolution (Req: Data Transformation 8).

Format (12 characters), per the spec:
  [0]      'S'
  [1:4]    first 3 digits of `block` after stripping non-numeric characters, left-padded
           with zeros to 3 digits (truncated to the first 3 if there are more than 3)
  [4:7]    first 3 digits of the mean resale_price for this row's (month, town, flat_type)
           group, floored to an integer
  [7:11]   the entry's year-month as YYMM (2012-01 -> "1201"), taken from the spec's own
           worked example; its surrounding prose is inconsistent about "last two" vs "last
           four" digits, so the example governs
  [11]     first character of town, uppercased

Base IDs are expected to collide (e.g. many transactions can share the same month/town/
flat_type/block-prefix). Collisions are resolved by appending a deterministic zero-padded
sequence suffix ("_01", "_02", ...) to every row beyond the first within an identical-base-ID
group, preserving original row order - no rows are ever dropped.
"""
from __future__ import annotations

import re

import pandas as pd


def _block_prefix(block: str) -> str:
    digits = re.sub(r"\D", "", str(block))
    digits = digits[:3] if len(digits) >= 3 else digits
    return digits.zfill(3)


def _month_to_yymm(month: str) -> str:
    year, mm = month.split("-")
    return f"{year[-2:]}{mm}"


def build_resale_identifier(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    group_avg_price = df.groupby(["month", "town", "flat_type"])["resale_price"].transform("mean")
    avg_price_prefix = group_avg_price.apply(lambda avg: str(int(avg)).zfill(3)[:3])

    block_prefix = df["block"].apply(_block_prefix)
    month_code = df["month"].apply(_month_to_yymm)
    town_initial = df["town"].str[0].str.upper()

    base_id = "S" + block_prefix + avg_price_prefix + month_code + town_initial
    df["resale_identifier_base"] = base_id

    # Deterministic collision resolution: rank duplicates of the same base_id in original
    # row order, then suffix the 2nd/3rd/... occurrence.
    occurrence = df.groupby("resale_identifier_base").cumcount()
    suffix = occurrence.apply(lambda n: "" if n == 0 else f"_{n:02d}")
    df["resale_identifier"] = base_id + suffix
    df = df.drop(columns=["resale_identifier_base"])

    assert df["resale_identifier"].is_unique, "Resale Identifier collision resolution failed"
    return df
