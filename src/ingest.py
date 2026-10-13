"""Discover and download the source datasets from data.gov.sg (Req: Dataset Extraction).

Nothing about the source files is hardcoded. The pipeline:

1. lists the child datasets of collection 189 via the data.gov.sg metadata API;
2. keeps those whose published coverage overlaps the pipeline scope (so the 1990-1999
   dataset is never downloaded);
3. downloads each through the official poll-download API, **streaming** the file to disk in
   chunks so file size is never bounded by memory (the brief cites files > 100 MB), under the
   filename data.gov.sg itself publishes;
4. records each file's SHA-256 in `data/raw/manifest.json`.

The manifest makes runs reproducible and auditable. A file already listed is reused rather
than re-fetched, and must still match its recorded checksum, because the brief requires raw
files to be processed as-is. That matters because the Jan-2017-onwards dataset is republished
daily, so a fresh download is a different file. To pull the latest upstream data deliberately,
pass `refresh=True`. If the API is unreachable, the run falls back to the manifest, so a
reviewer can execute the pipeline offline from the committed raw files.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from .schema import SourceDataset

log = logging.getLogger(__name__)

METADATA_API = "https://api-production.data.gov.sg/v2/public/api"
DOWNLOAD_API = "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
MANIFEST_NAME = "manifest.json"
CHUNK_BYTES = 1 << 20


def _get_with_retry(url: str, *, timeout: int, stream: bool = False,
                    max_attempts: int = 5) -> requests.Response:
    """GET with backoff on 429s — data.gov.sg rate-limits its public APIs."""
    delay = 5
    for attempt in range(1, max_attempts + 1):
        resp = requests.get(url, timeout=timeout, stream=stream)
        if resp.status_code != 429 or attempt == max_attempts:
            resp.raise_for_status()
            return resp
        resp.close()
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("unreachable")


def _api_data(url: str) -> dict:
    payload = _get_with_retry(url, timeout=30).json()
    if payload.get("code") not in (0, None) or "data" not in payload:
        raise RuntimeError(f"data.gov.sg API error for {url}: {payload}")
    return payload["data"]


def overlaps_scope(coverage_start: str, coverage_end: str, scope_start: str, scope_end: str) -> bool:
    """Do two "YYYY-MM" ranges overlap? Coverage dates may be full ISO timestamps."""
    return coverage_start[:7] <= scope_end and coverage_end[:7] >= scope_start


def filename_from_download_url(url: str, fallback: str) -> str:
    """The presigned URL carries the publisher's filename in its content-disposition."""
    disposition = parse_qs(urlparse(url).query).get("response-content-disposition", [""])[0]
    match = re.search(r'filename="?([^";]+)"?', disposition)
    return Path(match.group(1)).name if match else fallback


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stream_to_file(url: str, dest: Path) -> None:
    # Write to a temporary name and rename on completion, so an interrupted download can
    # never be mistaken for a complete cached file on the next run.
    partial = dest.with_suffix(dest.suffix + ".part")
    with _get_with_retry(url, timeout=300, stream=True) as resp, partial.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=CHUNK_BYTES):
            fh.write(chunk)
    partial.replace(dest)


def load_manifest(raw_dir: Path) -> dict[str, SourceDataset]:
    path = raw_dir / MANIFEST_NAME
    if not path.exists():
        return {}
    return {entry["dataset_id"]: SourceDataset(**entry)
            for entry in json.loads(path.read_text())["sources"]}


def _write_manifest(raw_dir: Path, collection_id: int, sources: list[SourceDataset]) -> None:
    body = {
        "collection_id": collection_id,
        "note": "Raw files exactly as published by data.gov.sg. Checksums are verified on every run.",
        "sources": [vars(s) for s in sources],
    }
    (raw_dir / MANIFEST_NAME).write_text(json.dumps(body, indent=2) + "\n")


def _verified(source: SourceDataset, raw_dir: Path) -> SourceDataset:
    actual = sha256_of(raw_dir / source.filename)
    if actual != source.sha256:
        raise ValueError(
            f"{source.filename} no longer matches its recorded checksum. Raw files must be "
            "processed as-is; restore the file, or re-run with refresh=True to re-download."
        )
    return source


def resolve_sources(collection_id: int, scope_start: str, scope_end: str, raw_dir: Path,
                    *, refresh: bool = False) -> list[SourceDataset]:
    """Return the in-scope source datasets, downloading any not already cached."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = {} if refresh else load_manifest(raw_dir)

    try:
        collection = _api_data(f"{METADATA_API}/collections/{collection_id}/metadata")
        catalogue = [_api_data(f"{METADATA_API}/datasets/{dataset_id}/metadata")
                     for dataset_id in collection["collectionMetadata"]["childDatasets"]]
    except requests.RequestException:
        if not manifest:
            raise
        log.warning("data.gov.sg unreachable - using the %d sources in the manifest", len(manifest))
        return [_verified(s, raw_dir) for s in sorted(manifest.values(), key=lambda s: s.coverage_start)]

    selected = sorted(
        (meta for meta in catalogue
         if overlaps_scope(meta["coverageStart"], meta["coverageEnd"], scope_start, scope_end)),
        key=lambda meta: meta["coverageStart"],
    )

    sources = []
    for meta in selected:
        cached = manifest.get(meta["datasetId"])
        if cached and (raw_dir / cached.filename).exists():
            sources.append(_verified(cached, raw_dir))
            continue

        download = _api_data(DOWNLOAD_API.format(dataset_id=meta["datasetId"]))
        filename = filename_from_download_url(download["url"], f"{meta['datasetId']}.csv")
        # data.gov.sg has changed the casing of its published filenames over time. Match an
        # existing file case-insensitively and record its *actual* name, so the manifest
        # stays valid on case-sensitive filesystems (Linux), not just on macOS/Windows.
        existing = {p.name.lower(): p for p in raw_dir.iterdir() if p.is_file()}
        dest = existing.get(filename.lower(), raw_dir / filename)
        filename = dest.name
        if refresh or not dest.exists():
            _stream_to_file(download["url"], dest)
        sources.append(SourceDataset(
            dataset_id=meta["datasetId"],
            name=meta["name"],
            filename=filename,
            coverage_start=meta["coverageStart"][:7],
            coverage_end=meta["coverageEnd"][:7],
            sha256=sha256_of(dest),
            size_bytes=dest.stat().st_size,
        ))

    _write_manifest(raw_dir, collection_id, sources)
    return sources
