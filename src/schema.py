"""Pipeline scope and the constants the brief itself specifies.

Nothing here names a specific source file. Which datasets to use is discovered at run time
from data.gov.sg collection 189 (see `ingest.py`): any dataset whose published coverage
overlaps the scope is used, and rows are filtered to the scope by their `month` value. If
data.gov.sg republishes or splits the files differently, the pipeline adapts without a code
change.
"""
from __future__ import annotations

from dataclasses import dataclass

# From the brief: https://data.gov.sg/collections/189/view, Jan 2012 - Dec 2017.
COLLECTION_ID = 189
SCOPE_START = "2012-01"
SCOPE_END = "2017-12"

# The "strict authoritative set" for both the combined schema (Req 1) and the validation
# domains for Town / Flat Type / Flat Model / storey_range (Req 3).
AUTHORITATIVE_MONTH = "2012-01"

REMAINING_LEASE_REFERENCE_DATE = "2027-01-01"
ASSUMED_LEASE_YEARS = 99


@dataclass(frozen=True)
class SourceDataset:
    """A data.gov.sg dataset selected for this run, as recorded in the raw-file manifest."""
    dataset_id: str
    name: str
    filename: str
    coverage_start: str  # "YYYY-MM", as published in the dataset's metadata
    coverage_end: str
    sha256: str
    size_bytes: int
