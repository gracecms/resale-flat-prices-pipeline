"""Official AWS Architecture Icons: download, cache, and resolve by name.

Shared by `generate_diagram.py` (PNG) and `generate_drawio.py` (editable draw.io source) so
both renderings of the architecture use the same icon set.

The pack is fetched from aws.amazon.com on first use and cached in `.icon-cache/` (gitignored),
the same idempotent download pattern the Part 1 pipeline uses for source data.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import requests

ICON_CACHE = Path(__file__).resolve().parent / ".icon-cache"
ICONS_PAGE = "https://aws.amazon.com/architecture/icons/"

_pack: Path | None = None
_memo: dict[str, Path] = {}


def ensure_icon_pack() -> Path:
    """Download + extract the AWS Architecture Icons pack once; return its root."""
    global _pack
    if _pack is not None:
        return _pack
    if ICON_CACHE.exists() and any(ICON_CACHE.glob("Architecture-Service-Icons*")):
        _pack = ICON_CACHE
        return _pack

    page = requests.get(ICONS_PAGE, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    page.raise_for_status()
    urls = re.findall(r'https://[^"\']*Icon-package[^"\']*\.zip', page.text)
    if not urls:
        raise RuntimeError("Could not find the AWS icon package URL on the AWS icons page.")

    archive = requests.get(urls[0], timeout=600)
    archive.raise_for_status()
    ICON_CACHE.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zf:
        zf.extractall(ICON_CACHE)
    _pack = ICON_CACHE
    return _pack


def ico(pattern: str) -> Path:
    """Resolve an icon file by filename pattern, independent of the pack's version folder."""
    if pattern not in _memo:
        hits = [p for p in ensure_icon_pack().rglob(pattern) if "__MACOSX" not in str(p)]
        if not hits:
            raise FileNotFoundError(f"icon not found in pack: {pattern}")
        _memo[pattern] = sorted(hits)[0]
    return _memo[pattern]


# Service icons ship a 5x (320px) raster; resource/general icons are 48px native.
_SVC = "Arch_{}_64@5x.png"
S3 = _SVC.format("Amazon-Simple-Storage-Service")
GLUE = _SVC.format("AWS-Glue")
ATHENA = _SVC.format("Amazon-Athena")
LAKEFORM = _SVC.format("AWS-Lake-Formation")
SFN = _SVC.format("AWS-Step-Functions")
EVENTBRIDGE = _SVC.format("Amazon-EventBridge")
SNS = _SVC.format("Amazon-Simple-Notification-Service")
SECRETS = _SVC.format("AWS-Secrets-Manager")
KMS = _SVC.format("AWS-Key-Management-Service")
NETFW = _SVC.format("AWS-Network-Firewall")
CLOUDTRAIL = _SVC.format("AWS-CloudTrail")
GUARDDUTY = _SVC.format("Amazon-GuardDuty")
EC2 = _SVC.format("Amazon-EC2")

NAT_GW = "Res_Amazon-VPC_NAT-Gateway_48.png"
IGW = "Res_Amazon-VPC_Internet-Gateway_48.png"
VPC_EP = "Res_Amazon-VPC_Endpoints_48.png"
GLUE_CATALOG = "Res_AWS-Glue_Data-Catalog_48.png"
GLUE_CRAWLER = "Res_AWS-Glue_Crawler_48.png"
GLUE_DQ = "Res_AWS-Glue_Data-Quality_48.png"
BUCKET = "Res_Amazon-Simple-Storage-Service_Bucket_48.png"
INTERNET = "Res_Internet_48_Light.png"
VPC_GROUP = "Virtual-private-cloud-VPC_32.png"
PUB_SUBNET = "Public-subnet_32.png"
PRIV_SUBNET = "Private-subnet_32.png"
REGION_G = "Region_32.png"
