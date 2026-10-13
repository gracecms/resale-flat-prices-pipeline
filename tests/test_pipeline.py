"""Unit tests for the pipeline's business rules.

These cover the pure, rule-bearing functions - identifier construction, remaining lease,
validation, de-identification - because those are where a silent error would propagate into
every downstream output without the row counts ever looking wrong. Run with `pytest` from the
repository root.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.anomaly import add_anomaly_flags
from src.combine import combine_sources
from src.completeness import flagged_months, monthly_completeness
from src.ingest import filename_from_download_url, overlaps_scope, resolve_sources, sha256_of
from src.schema import SourceDataset
from src.deidentify import PLACEHOLDER_KEY, ensure_secret_key, hash_identifier
from src.identifier import _block_prefix, _month_to_yymm, build_resale_identifier
from src.lease import add_remaining_lease
from src.lease_check import parse_published_remaining_lease
from src.validation import build_authoritative_domains, split_validated, validate

SCOPE = {"scope_start": "2012-01", "scope_end": "2017-12"}


def make_row(**overrides) -> dict:
    row = {
        "month": "2012-01",
        "town": "ANG MO KIO",
        "flat_type": "3 ROOM",
        "block": "406",
        "street_name": "ANG MO KIO AVE 10",
        "storey_range": "01 TO 03",
        "floor_area_sqm": 68.0,
        "flat_model": "Improved",
        "lease_commence_date": 1979,
        "resale_price": 300000.0,
    }
    row.update(overrides)
    return row


def make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


@pytest.fixture
def domains() -> dict[str, set]:
    return build_authoritative_domains(make_df([make_row()]))


# --------------------------------------------------------------------- identifier components
@pytest.mark.parametrize(
    "block, expected",
    [
        ("19", "019"),       # spec's own worked example
        ("1", "001"),        # pad to three
        ("406", "406"),      # already three
        ("406A", "406"),     # non-numeric characters stripped
        ("1023", "102"),     # more than three digits -> first three, not rounded
        ("B12", "012"),      # letters anywhere
    ],
)
def test_block_prefix(block, expected):
    assert _block_prefix(block) == expected


@pytest.mark.parametrize("month, expected", [("2012-01", "1201"), ("2017-12", "1712")])
def test_month_code_is_year_then_month(month, expected):
    """The spec's prose is self-contradictory ("last four"/"last two" digits), so its worked
    example governs: 2012-01 -> 1201, i.e. two-digit year followed by two-digit month."""
    assert _month_to_yymm(month) == expected


# --------------------------------------------------------------------- identifier assembly
def test_identifier_uses_group_average_not_row_price():
    """The price digits come from the (month, town, flat_type) group mean, not the row."""
    df = make_df([
        make_row(block="406", resale_price=200_000.0),
        make_row(block="407", resale_price=300_000.0),
    ])
    out = build_resale_identifier(df)
    # mean of 200k and 300k is 250000 -> "250" for both rows
    assert out.loc[0, "resale_identifier"] == "S406250" + "1201" + "A"
    assert out.loc[1, "resale_identifier"] == "S407250" + "1201" + "A"


def test_identifier_layout_is_12_characters():
    out = build_resale_identifier(make_df([make_row()]))
    identifier = out.loc[0, "resale_identifier"]
    assert len(identifier) == 12
    assert identifier.startswith("S")
    assert identifier.endswith("A")  # ANG MO KIO


def test_collisions_get_deterministic_suffixes_and_keep_every_row():
    """Identical component values must still yield unique ids, without dropping records."""
    df = make_df([make_row(resale_price=300_000.0) for _ in range(3)])
    out = build_resale_identifier(df)

    assert len(out) == 3, "no record may be dropped to achieve uniqueness"
    assert out["resale_identifier"].is_unique
    base = out.loc[0, "resale_identifier"]
    assert list(out["resale_identifier"]) == [base, f"{base}_01", f"{base}_02"]


def test_identifier_generation_is_reproducible():
    df = make_df([make_row(block=b) for b in ("406", "406", "407")])
    assert list(build_resale_identifier(df)["resale_identifier"]) == \
           list(build_resale_identifier(df)["resale_identifier"])


# --------------------------------------------------------------------- remaining lease
def test_remaining_lease_as_of_2027():
    """1979 + 99 = 2078 expiry; measured at 2027-01-01 that is 51 whole years."""
    out = add_remaining_lease(make_df([make_row(lease_commence_date=1979)]))
    assert out.loc[0, "remaining_lease_years"] == 51
    assert out.loc[0, "remaining_lease_months"] == 0
    assert out.loc[0, "remaining_lease_display"] == "51 years 0 months"


def test_remaining_lease_months_are_always_zero_for_year_only_input():
    """Documents a real consequence: the source gives a commencement *year*, so both lease
    start and expiry fall on 1 January and the month component can never be non-zero."""
    out = add_remaining_lease(make_df([make_row(lease_commence_date=y) for y in (1966, 1990, 2015)]))
    assert set(out["remaining_lease_months"]) == {0}


def test_remaining_lease_never_negative():
    """A lease that expired before the reference date floors at zero rather than going negative."""
    out = add_remaining_lease(make_df([make_row(lease_commence_date=1900)]))
    assert out.loc[0, "remaining_lease_years"] >= 0


# --------------------------------------------------------------------- validation
def test_valid_row_passes(domains):
    result = validate(make_df([make_row()]), domains, **SCOPE)
    assert result.loc[0, "quarantine_reason"] == ""


@pytest.mark.parametrize(
    "override, expected_reason",
    [
        ({"town": "PUNGGOL WEST"}, "invalid_town"),
        ({"flat_model": "DBSS"}, "invalid_flat_model"),
        ({"storey_range": "49 TO 51"}, "invalid_storey_range"),
        ({"flat_type": "3Gen"}, "invalid_flat_type"),
        ({"resale_price": -1.0}, "invalid_resale_price"),
        ({"floor_area_sqm": 5000.0}, "implausible_floor_area_sqm"),
        ({"month": "2019-05"}, "month_out_of_scope"),
    ],
)
def test_rows_outside_the_authoritative_domains_are_quarantined(domains, override, expected_reason):
    result = validate(make_df([make_row(**override)]), domains, **SCOPE)
    assert expected_reason in result.loc[0, "quarantine_reason"]


def test_multiple_failures_are_all_reported(domains):
    """The quarantine bucket has to stay diagnosable, so reasons accumulate."""
    result = validate(make_df([make_row(town="ATLANTIS", resale_price=0.0)]), domains, **SCOPE)
    reasons = result.loc[0, "quarantine_reason"].split(";")
    assert "invalid_town" in reasons and "invalid_resale_price" in reasons


def test_first_copy_of_a_duplicate_is_kept_and_the_rest_quarantined(domains):
    result = validate(make_df([make_row(), make_row()]), domains, **SCOPE)
    assert result.loc[0, "quarantine_reason"] == ""
    assert result.loc[1, "quarantine_reason"] == "duplicate_record"


def test_split_conserves_every_row(domains):
    """The pipeline's core invariant: cleaned + quarantined == input, nothing silently lost."""
    df = make_df([make_row(), make_row(town="ATLANTIS"), make_row(block="123")])
    cleaned, quarantined = split_validated(validate(df, domains, **SCOPE))
    assert len(cleaned) + len(quarantined) == len(df)
    assert "quarantine_reason" not in cleaned.columns


def test_empty_authoritative_slice_fails_loudly():
    """An empty slice would otherwise quarantine 100% of rows with no error."""
    with pytest.raises(ValueError, match="Authoritative slice is empty"):
        build_authoritative_domains(make_df([]).reindex(columns=list(make_row())))


# --------------------------------------------------------------------- anomaly detection
def test_price_outlier_is_flagged_within_its_own_group():
    rows = [make_row(resale_price=p, block=str(300 + i)) for i, p in enumerate([300_000.0] * 10)]
    rows.append(make_row(resale_price=5_000_000.0, block="999"))
    out = add_anomaly_flags(make_df(rows))
    assert bool(out.iloc[-1]["is_price_anomalous"])
    assert not out.iloc[:-1]["is_price_anomalous"].any()


def test_small_groups_are_not_flagged():
    """Too few observations to define a quartile - stay silent rather than guess."""
    out = add_anomaly_flags(make_df([make_row(resale_price=p) for p in (200_000.0, 900_000.0)]))
    assert not out["is_price_anomalous"].any()


# --------------------------------------------------------------------- de-identification
def test_hash_is_deterministic_for_a_given_key():
    assert hash_identifier("S4062561201A", b"key") == hash_identifier("S4062561201A", b"key")


def test_hash_depends_on_the_secret_key():
    """The whole point of HMAC over a plain hash: without the key the mapping is unreproducible."""
    assert hash_identifier("S4062561201A", b"key-a") != hash_identifier("S4062561201A", b"key-b")


def test_hash_preserves_uniqueness_and_hides_structure():
    ids = [f"S406256120{i}A" for i in range(50)]
    hashes = [hash_identifier(i, b"key") for i in ids]
    assert len(set(hashes)) == len(ids)
    assert all(len(h) == 64 for h in hashes)
    # near-identical inputs must not produce near-identical outputs
    assert hashes[0][:8] != hashes[1][:8]


# --------------------------------------------------------------------- published-lease parsing
@pytest.mark.parametrize(
    "raw, expected_months",
    [
        ("70", 840),                  # 2015-2016 files: bare integer years
        ("61 years 04 months", 736),  # 2017+ files: free text
        ("61 years", 732),
        ("", None),
        ("not a lease", None),
    ],
)
def test_published_remaining_lease_parsing(raw, expected_months):
    assert parse_published_remaining_lease(raw) == expected_months


# --------------------------------------------------------------------- monthly completeness
def test_completeness_flags_a_month_hollowed_out_by_validation():
    """Reconciliation passes even when a month is almost entirely quarantined; this must not."""
    combined = make_df([make_row(month="2012-01")] * 10 + [make_row(month="2012-02")] * 10)
    cleaned = make_df([make_row(month="2012-01")] * 10 + [make_row(month="2012-02")] * 1)
    table = monthly_completeness(combined, cleaned, scope_start="2012-01", scope_end="2012-02")

    flagged = flagged_months(table)
    assert list(flagged["month"]) == ["2012-02"]
    assert flagged.loc[0, "retention_pct"] == 10.0


def test_completeness_flags_a_month_absent_from_the_source():
    combined = make_df([make_row(month="2012-01")])
    table = monthly_completeness(combined, combined, scope_start="2012-01", scope_end="2012-03")
    assert set(flagged_months(table)["month"]) == {"2012-02", "2012-03"}
    assert set(flagged_months(table)["flag"]) == {"missing_from_source"}


def test_complete_months_are_not_flagged():
    df = make_df([make_row(month="2012-01")] * 4)
    assert flagged_months(
        monthly_completeness(df, df, scope_start="2012-01", scope_end="2012-01")
    ).empty


# --------------------------------------------------------------------- source discovery
@pytest.mark.parametrize(
    "coverage, expected",
    [
        (("1990-01-01T08:00:00+08:00", "1999-12-01T08:00:00+08:00"), False),  # never downloaded
        (("2000-01-01T08:00:00+08:00", "2012-02-01T08:00:00+08:00"), True),   # holds Jan-Feb 2012
        (("2017-01-01T08:00:00+08:00", "2026-10-01T08:00:00+08:00"), True),   # open-ended, still in
        (("2018-01-01T08:00:00+08:00", "2026-10-01T08:00:00+08:00"), False),
    ],
)
def test_datasets_are_selected_by_published_coverage(coverage, expected):
    assert overlaps_scope(*coverage, "2012-01", "2017-12") is expected


def test_filename_comes_from_the_publishers_presigned_url():
    url = ("https://s3.ap-southeast-1.amazonaws.com/bucket/d_x/abc.csv?X-Amz-Expires=3600"
           "&response-content-disposition=attachment%3B%20filename%3D%22ResaleFlatPrices2015.csv%22")
    assert filename_from_download_url(url, "fallback.csv") == "ResaleFlatPrices2015.csv"
    assert filename_from_download_url("https://example.com/x.csv", "fallback.csv") == "fallback.csv"


def test_offline_run_refuses_a_modified_raw_file(tmp_path, monkeypatch):
    """Raw files must be processed as-is: an edited cached file fails, it is not used."""
    import json
    import requests

    raw = tmp_path / "a.csv"
    raw.write_text("month,town\n2012-01,X\n")
    source = SourceDataset("d_a", "A", "a.csv", "2012-01", "2012-12", sha256_of(raw), raw.stat().st_size)
    (tmp_path / "manifest.json").write_text(json.dumps({"sources": [vars(source)]}))

    def offline(*_, **__):
        raise requests.ConnectionError("no network")
    monkeypatch.setattr("src.ingest.requests.get", offline)

    assert resolve_sources(189, "2012-01", "2017-12", tmp_path) == [source]
    raw.write_text("month,town\n2012-01,TAMPERED\n")
    with pytest.raises(ValueError, match="checksum"):
        resolve_sources(189, "2012-01", "2017-12", tmp_path)


# --------------------------------------------------------------------- combine
def _write_source(tmp_path, name, rows, extra_cols=()):
    df = pd.DataFrame(rows)
    for col in extra_cols:
        df[col] = "70"
    df.to_csv(tmp_path / f"{name}.csv", index=False)
    return SourceDataset(name, name, f"{name}.csv", "", "", "", 0)


def test_combine_scopes_by_month_and_uses_the_authoritative_schema(tmp_path):
    early = _write_source(tmp_path, "early", [make_row(month="2011-12"), make_row(month="2012-01")])
    later = _write_source(tmp_path, "later", [make_row(month="2015-03"), make_row(month="2019-01")],
                          extra_cols=["remaining_lease"])
    combined, stats, authoritative = combine_sources(
        [early, later], tmp_path, scope_start="2012-01", scope_end="2017-12", authoritative_month="2012-01")

    assert sorted(combined["month"]) == ["2012-01", "2015-03"]        # out-of-scope rows dropped
    assert authoritative == early
    assert "remaining_lease" not in combined.columns                   # not in the Jan-2012 schema
    assert list(stats["out_of_scope_rows"]) == [1, 1]
    assert stats.loc[1, "columns_not_carried"] == "remaining_lease"


def test_combine_refuses_sources_that_overlap_in_time(tmp_path):
    """Without per-file windows, an overlap would double-count - so it must fail instead."""
    a = _write_source(tmp_path, "a", [make_row(month="2012-01"), make_row(month="2012-02")])
    b = _write_source(tmp_path, "b", [make_row(month="2012-02")])
    with pytest.raises(ValueError, match="double-count"):
        combine_sources([a, b], tmp_path, scope_start="2012-01", scope_end="2017-12",
                        authoritative_month="2012-01")


# --------------------------------------------------------------------- secret key setup
def test_missing_key_is_generated_and_saved(tmp_path, monkeypatch):
    # setenv first so pytest restores the variable afterwards; ensure_secret_key sets it directly.
    monkeypatch.setenv("HASH_SECRET_KEY", "placeholder-for-restore")
    monkeypatch.delenv("HASH_SECRET_KEY")
    env = tmp_path / ".env"
    assert ensure_secret_key(env) is True
    saved = env.read_text().strip().split("=", 1)[1]
    assert len(saved) == 64 and saved != PLACEHOLDER_KEY


def test_published_placeholder_key_is_replaced_not_used(tmp_path, monkeypatch):
    """A key anyone can read from .env.example would defeat the dictionary-attack protection."""
    # setenv first so pytest restores the variable afterwards; ensure_secret_key sets it directly.
    monkeypatch.setenv("HASH_SECRET_KEY", "placeholder-for-restore")
    monkeypatch.delenv("HASH_SECRET_KEY")
    env = tmp_path / ".env"
    env.write_text(f"OTHER_SETTING=1\nHASH_SECRET_KEY={PLACEHOLDER_KEY}\n")
    assert ensure_secret_key(env) is True
    text = env.read_text()
    assert PLACEHOLDER_KEY not in text
    assert "OTHER_SETTING=1" in text and text.count("HASH_SECRET_KEY=") == 1


def test_existing_key_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("HASH_SECRET_KEY", "an-existing-secret")
    env = tmp_path / ".env"
    assert ensure_secret_key(env) is False
    assert not env.exists()
