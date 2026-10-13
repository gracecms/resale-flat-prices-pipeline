# HDB Resale Flat Prices - Data Profiling & Insights Report

Pipeline scope: **2012-01 to 2017-12**. Authoritative month for schema and domain validation: **2012-01**.

## Dataset Overview

- Combined master dataset (pre-validation): **113,053** rows
- Cleaned: **104,783** rows
- Quarantined: **8,270** rows (7.32% of combined)
- Transformed / Hashed: **104,783** rows each (all Cleaned rows carry a unique identifier)


> **Known gap - read before using the cleaned data:** 3 in-scope month(s) retain under half their rows after validation: **2012-03** (0% retained), **2012-04** (0% retained), **2012-05** (0% retained). Any time series built from `cleaned/` will show a hole there. It is an upstream reporting-convention change, not a fall in transactions - see *Quarantine Bucket Analysis* below.

## Pipeline Lifecycle

Every row, from the files as published to each output group. The notebook asserts that each stage reconciles with the one before it.

| stage              | rows     | detail                                                            |
|:-------------------|:---------|:------------------------------------------------------------------|
| Raw (as published) | 701,039  | 4 files discovered in collection 189; stored unmodified           |
| out of scope       | -587,986 | months outside 2012-01 to 2017-12; removed in memory only         |
| Combined           | 113,053  | master dataset on the Jan 2012 schema                             |
| quarantined        | -8,270   | failed validation or duplicate; kept with reasons in quarantined/ |
| Cleaned            | 104,783  | + remaining lease, price_per_sqm, anomaly flags                   |
| Transformed        | 104,783  | + resale_identifier (12,952 rows needed a collision suffix)       |
| Hashed             | 104,783  | resale_identifier replaced by hashed_identifier                   |

### Stage 1 - Raw: the source files

Discovered from collection 189 by each dataset's published coverage; stored byte-for-byte and verified against the checksums in `data/raw/manifest.json` on every run.

| dataset                                                                    |   raw_rows | raw_months         |   in_scope_rows |   out_of_scope_rows |   raw_columns | columns_not_carried   |
|:---------------------------------------------------------------------------|-----------:|:-------------------|----------------:|--------------------:|--------------:|:----------------------|
| Resale Flat Prices (Based on Approval Date), 2000 - Feb 2012               |     369651 | 2000-01 to 2012-02 |            3188 |              366463 |            10 | -                     |
| Resale Flat Prices (Based on Registration Date), From Mar 2012 to Dec 2014 |      52203 | 2012-03 to 2014-12 |           52203 |                   0 |            10 | -                     |
| Resale Flat Prices (Based on Registration Date), From Jan 2015 to Dec 2016 |      37153 | 2015-01 to 2016-12 |           37153 |                   0 |            11 | remaining_lease       |
| Resale flat prices based on registration date from Jan-2017 onwards        |     242032 | 2017-01 to 2026-10 |           20509 |              221523 |            11 | remaining_lease       |

- 587,986 of 701,039 published rows (84%) are out of scope: the 2000-2011 history in the first file, and post-2017 rows in the open-ended last file. They are removed in memory; the files themselves are untouched.
- Files disagree on schema: two carry a `remaining_lease` column the Jan 2012 file lacks. It is excluded from the master dataset, but used as an independent reference in the lease validation below - where it also turns out to be formatted differently between files.
- Upstream naming isn't stable either: data.gov.sg has changed the casing of one published filename, which the ingestion step handles so the manifest stays valid on case-sensitive filesystems.

### Stages 2-4 - Combined, Cleaned, Quarantined

### Combined master dataset profile

- Rows: **113,053** | Columns: **10**
- Month range: **2012-01 to 2017-12**
- Exact duplicate rows (both/all copies counted): **902**

| Column | dtype | % missing | # unique | notes |
|---|---|---|---|---|
| month | object | 0.0% | 72 |  |
| town | object | 0.0% | 26 | JURONG WEST=9193, WOODLANDS=8930, TAMPINES=8027 |
| flat_type | object | 0.0% | 7 | 4 ROOM=45139, 3 ROOM=31354, 5 ROOM=26370 |
| block | object | 0.0% | 2193 |  |
| street_name | object | 0.0% | 526 |  |
| storey_range | object | 0.0% | 25 | 04 TO 06=25934, 07 TO 09=23193, 01 TO 03=21036 |
| floor_area_sqm | float64 | 0.0% | 169 | min=31.0, max=280.0, mean=96.8 |
| flat_model | object | 0.0% | 20 | Model A=32702, Improved=29175, New Generation=19497 |
| lease_commence_date | int64 | 0.0% | 50 | min=1966.0, max=2015.0, mean=1990.6 |
| resale_price | float64 | 0.0% | 2865 | min=175000.0, max=1180000.0, mean=449659.9 |

### Cleaned dataset profile

- Rows: **104,783** | Columns: **16**
- Month range: **2012-01 to 2017-12**
- Exact duplicate rows (both/all copies counted): **0**

| Column | dtype | % missing | # unique | notes |
|---|---|---|---|---|
| month | object | 0.0% | 69 |  |
| town | object | 0.0% | 26 | JURONG WEST=8632, WOODLANDS=8248, TAMPINES=7292 |
| flat_type | object | 0.0% | 7 | 4 ROOM=41868, 3 ROOM=29292, 5 ROOM=24113 |
| block | object | 0.0% | 2170 |  |
| street_name | object | 0.0% | 522 |  |
| storey_range | object | 0.0% | 12 | 04 TO 06=25719, 07 TO 09=22983, 01 TO 03=20918 |
| floor_area_sqm | float64 | 0.0% | 167 | min=31.0, max=280.0, mean=96.7 |
| flat_model | object | 0.0% | 13 | Model A=30623, Improved=27237, New Generation=18167 |
| lease_commence_date | int64 | 0.0% | 50 | min=1966.0, max=2015.0, mean=1990.4 |
| resale_price | float64 | 0.0% | 2707 | min=175000.0, max=1160000.0, mean=446029.4 |
| remaining_lease_years | int64 | 0.0% | 50 |  |
| remaining_lease_months | int64 | 0.0% | 1 |  |
| remaining_lease_display | object | 0.0% | 50 |  |
| price_per_sqm | float64 | 0.0% | 19057 |  |
| is_price_anomalous | bool | 0.0% | 2 |  |
| price_anomaly_reason | object | 0.0% | 4 |  |

### Quarantined dataset profile

- Rows: **8,270** | Columns: **11**
- Month range: **2012-02 to 2017-12**
- Exact duplicate rows (both/all copies counted): **0**

| Column | dtype | % missing | # unique | notes |
|---|---|---|---|---|
| month | object | 0.0% | 69 |  |
| town | object | 0.0% | 26 | TAMPINES=735, WOODLANDS=682, JURONG WEST=561 |
| flat_type | object | 0.0% | 6 | 4 ROOM=3271, 5 ROOM=2257, 3 ROOM=2062 |
| block | object | 0.0% | 1606 |  |
| street_name | object | 0.0% | 491 |  |
| storey_range | object | 0.0% | 25 | 01 TO 05=2700, 06 TO 10=2474, 11 TO 15=1259 |
| floor_area_sqm | float64 | 0.0% | 138 | min=34.0, max=243.0, mean=97.7 |
| flat_model | object | 0.0% | 20 | Model A=2079, Improved=1938, New Generation=1330 |
| lease_commence_date | int64 | 0.0% | 49 | min=1967.0, max=2015.0, mean=1992.2 |
| resale_price | float64 | 0.0% | 1053 | min=240000.0, max=1180000.0, mean=495660.0 |
| quarantine_reason | object | 0.0% | 6 |  |

### Stages 5-6 - Transformed and Hashed

- **Transformed**: 104,783 rows, one new column `resale_identifier`. 91,831 distinct base identifiers; 12,952 rows (12.4%) needed a collision suffix. The most shared base identifier covers 14 rows, so suffixes never exceed two digits.
- **Hashed**: 104,783 rows. `resale_identifier` is removed and replaced by a 64-character `hashed_identifier`, unique across every row (asserted in the notebook).

## Quarantine Bucket Analysis

| Quarantine reason combination | Row count |
|---|---|
| invalid_storey_range | 6,952 |
| invalid_flat_model | 775 |
| duplicate_record | 442 |
| invalid_flat_model;invalid_storey_range | 92 |
| invalid_storey_range;duplicate_record | 6 |
| invalid_flat_model;duplicate_record | 3 |


**Key finding - most of the quarantine bucket is one upstream reporting change, not dirty data.** 6,838 of 8,270 quarantined rows (83%) fail `invalid_storey_range` inside just 2012-03, 2012-04, 2012-05. In those months HDB published storey ranges in **5-storey bands** (`01 TO 05`, `06 TO 10`, ...) instead of the 3-storey bands it used in Jan 2012 and again from mid-2012 onward.

The strict rule is kept as the spec requires, and deliberately not 'repaired': a 5-storey band cannot be mapped losslessly onto 3-storey bands (`01 TO 05` straddles `01 TO 03` and `04 TO 06`), so any mapping would invent precision the source never had.

The remaining failures are genuine values absent from Jan 2012:
- storey_range outside those months (212 rows): `37 TO 39` (125), `40 TO 42` (60), `46 TO 48` (11), `43 TO 45` (11), `49 TO 51` (5) - floors above Jan 2012's highest band (`34 TO 36`).
- flat_model (870 rows): `DBSS` (583), `Type S1` (179), `Type S2` (78), `Improved-Maisonette` (15), `Premium Maisonette` (8), `Premium Apartment Loft` (6), `2-room` (1).

Quarantine rate by year (% of that year's combined rows):

| Year | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 |
|---|---|---|---|---|---|---|
| Quarantined % | 29.6 | 0.2 | 2 | 1.1 | 1.5 | 2.9 |

**Consequence for consumers:** those months are missing from the cleaned dataset entirely (see *Known gap* above). The rows are preserved in `quarantined/` with their reason, so a consumer who accepts the coarser 5-storey band can reinstate them deliberately. The per-month completeness check (`src/completeness.py`) makes this visible automatically, rather than relying on someone noticing the month count drop from 72 to 69.

## Are the quarantined duplicates errors, or real repeat transactions?

451 rows were quarantined as `duplicate_record`. This is a judgment call worth stating plainly: the dataset carries **no transaction identifier**, and its granularity is coarse (month, not date; a 3-storey band, not a unit number). Two genuinely different flats in the same block and storey band, of the same size, sold in the same month at the same price would be indistinguishable from one record written twice.

The pipeline keeps the first occurrence and quarantines the rest, so the cleaned dataset never double-counts. Because quarantine preserves the rows rather than discarding them, the Data Science Team can reinstate them if they judge repeats to be genuine - the decision is reversible, which is why quarantining was preferred to dropping.

## Validating the 99-year lease assumption

The brief states the 99-year lease as an assumption; the 2015-onwards source files let us test it against HDB's own published `remaining_lease` (a column deliberately excluded from the master dataset, since the authoritative Jan-2012 schema predates it).

| source                                                                     |   rows_compared | published_format   |   exact_match_pct |   within_12_months_pct |   median_abs_diff_months |   max_abs_diff_months |
|:---------------------------------------------------------------------------|----------------:|:-------------------|------------------:|-----------------------:|-------------------------:|----------------------:|
| Resale Flat Prices (Based on Registration Date), From Jan 2015 to Dec 2016 |           37153 | 70                 |               6.8 |                  100   |                        4 |                    13 |
| Resale flat prices based on registration date from Jan-2017 onwards        |           20509 | 61 years 04 months |              11.1 |                   99.9 |                        6 |                    14 |

**Finding**: agreement is effectively total at whole-year resolution, so the 99-year assumption holds. The residual sub-year spread is not an error - it is the precision limit of a `lease_commence_date` given as a *year*, so the true lease start can sit anywhere in that year. **`remaining_lease_years` should be read as +/- 1 year**, and that is also why `remaining_lease_months` is always 0.

A secondary observation: the published column is not consistently formatted across vintages - whole years as a bare integer in the 2015-2016 file, free text (`61 years 04 months`) from 2017 onward. That inconsistency is a further argument for deriving the value ourselves rather than depending on the source column.

## Anomalous Resale Price Findings

- 1,047 of 104,783 cleaned rows (1.00%) flagged as potentially anomalous via Tukey's IQR fences (1.5x IQR), computed per (town, flat_type, flat_model) group on both resale_price and price_per_sqm. Flagged, not quarantined - see `src/anomaly.py` for the full rationale.

## Resale Identifier & De-identification

- 12,952 rows required a collision-resolution suffix on the base 12-character identifier (see `src/identifier.py`). Suffixes are deterministic and assigned in original row order - no rows were dropped to achieve uniqueness.
- The identifier is de-identified via HMAC-SHA256 keyed with a secret from `.env` (`HASH_SECRET_KEY`), not a plain or publicly-salted hash, specifically because the identifier's construction rule is simple/enumerable - full rationale in `src/deidentify.py`.

## Data dictionary — columns added by this pipeline

The ten source columns are carried through unchanged. The columns below are derived, and are what the Data Science Team is actually being handed.

| Column | Type | Present in | Meaning |
|---|---|---|---|
| `remaining_lease_years` | int | cleaned, transformed, hashed | Whole years of lease left at 2027-01-01, floored. Read as +/- 1 year (see lease validation above). |
| `remaining_lease_months` | int | cleaned, transformed, hashed | Month component; always 0, because `lease_commence_date` is a year only. |
| `remaining_lease_display` | str | cleaned, transformed, hashed | Human-readable form, e.g. `51 years 0 months`. |
| `price_per_sqm` | float | cleaned, transformed, hashed | `resale_price / floor_area_sqm`. Size-normalised price, used by the anomaly rule and useful for modelling. |
| `is_price_anomalous` | bool | cleaned, transformed, hashed | True if the row is a price outlier **within its own (town, flat_type, flat_model) group**. A flag for review, not a quality failure — these rows are valid. |
| `price_anomaly_reason` | str | cleaned, transformed, hashed | Which test fired: `resale_price_outlier_in_group`, `price_per_sqm_outlier_in_group`, or both. |
| `resale_identifier` | str | transformed only | The 12-character business identifier, with a `_NN` suffix where the base code collided. |
| `hashed_identifier` | str | hashed only | HMAC-SHA256 of `resale_identifier`. Replaces the plaintext identifier — de-identification would be pointless if both appeared together. |
| `quarantine_reason` | str | quarantined only | Semicolon-joined list of every rule the row failed. |

**Which output should the Data Science Team use?** `hashed/` for general analysis — it is the full cleaned dataset with a non-reversible key. Use `transformed/` only if the plaintext identifier is genuinely needed. `quarantined/` is a data-engineering triage surface, not an analysis input.

## Assumptions

1. **Two distinct uses of "Jan 2012 as strict authoritative set"**: schema authority (Req 1, master dataset columns = Jan 2012's columns) is treated separately from domain-value authority (Req 3, valid Town/Flat Type/Flat Model/storey_range values = those observed in Jan 2012). See notebook Section 2.
2. **Source file selection**: no single published dataset covers Jan 2012-Dec 2017, so the pipeline discovers collection 189's datasets at run time, uses every one whose published coverage overlaps the scope, and keeps rows by their own `month`. It fails rather than combine two files that overlap in time, because that would double-count. Raw files are pinned by checksum, so re-runs reproduce this exact snapshot rather than silently picking up data.gov.sg's daily republication of the 2017-onwards file.
3. **Remaining lease**: lease start = 1 Jan of `lease_commence_date`'s year; lease term = 99 years; reference date = 1 Jan 2027; result floored to whole years+months (Req 4). Side effect worth flagging explicitly: because lease start/expiry always fall on 1 January, `remaining_lease_months` is always 0 for every row - that's correct given year-only source data, not a calculation bug.
4. **Duplicate handling**: exact full-row duplicates keep their first occurrence as a valid Cleaned row; subsequent copies are quarantined as `duplicate_record`.
5. **Anomaly detection is a flag, not a quarantine rule**: "potentially anomalous" (Req 5) is treated as weaker than "invalid" (Req 3) - anomalous rows stay in Cleaned/Transformed/Hashed with a flag for the Data Science Team to decide on.
6. **Sanity bounds**: floor_area_sqm accepted in [20, 500] sqm; resale_price must be > 0; chosen generously from the observed data range so they catch only clearly implausible values, not legitimate edge cases.
