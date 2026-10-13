"""Generate the Part 2 architecture diagram using the official AWS Architecture Icons.

The icon pack is downloaded from aws.amazon.com and cached locally (gitignored), the same
idempotent pattern the Part 1 pipeline uses for source data - so the diagram is reproducible
from a fresh clone:

    pip install -r requirements.txt
    python architecture/generate_diagram.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

from aws_icons import (  # noqa: F401 - icon name constants are used throughout the layout
    ATHENA, BUCKET, CLOUDTRAIL, EC2, EVENTBRIDGE, GLUE, GLUE_CATALOG, GLUE_CRAWLER, GLUE_DQ,
    GUARDDUTY, IGW, INTERNET, KMS, LAKEFORM, NAT_GW, NETFW, PRIV_SUBNET, PUB_SUBNET, REGION_G,
    S3, SECRETS, SFN, SNS, VPC_EP, VPC_GROUP, ico,
)

OUT_PATH = Path(__file__).resolve().parent / "data_platform_architecture.png"

FIG_W, FIG_H, DPI = 34, 18, 150
XMIN, XMAX, YMIN, YMAX = 0, 170, -4, 84

# AWS diagram group-border colours, per the AWS architecture icon guidelines.
C_CLOUD = "#242F3E"
C_VPC = "#8C4FFF"
C_PUBLIC = "#7AA116"
C_PRIVATE = "#00A4A6"
C_GOV = "#E7157B"
C_LAKE = "#3B48CC"
C_TEXT = "#16191F"
C_MUTED = "#5A6470"
C_FLOW = "#414D5C"
C_ALERT = "#C7303C"


# --------------------------------------------------------------------------- canvas
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_aspect("equal")
ax.axis("off")


def img(pattern: str, x: float, y: float, size: float, z: int = 5) -> None:
    ax.imshow(mpimg.imread(ico(pattern)),
              extent=(x - size / 2, x + size / 2, y - size / 2, y + size / 2),
              zorder=z, interpolation="antialiased")


def node(pattern: str, x: float, y: float, title: str, detail: str = "",
         size: float = 2.8, ts: float = 9.3, ds: float = 7.5) -> None:
    img(pattern, x, y, size)
    ty = y - size / 2 - 0.65
    ax.text(x, ty, title, ha="center", va="top", fontsize=ts, fontweight="bold",
            color=C_TEXT, linespacing=1.3, zorder=6)
    if detail:
        ax.text(x, ty - 1.35 * (title.count("\n") + 1) - 0.2, detail, ha="center", va="top",
                fontsize=ds, color=C_MUTED, linespacing=1.45, zorder=6)


def group(x: float, y: float, w: float, h: float, label: str, color: str,
          icon: str | None = None, ls: str = "-", lw: float = 1.8, fs: float = 10.5,
          sublabel: str = "", sub_color: str = "") -> None:
    ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=color, linewidth=lw,
                           linestyle=ls, zorder=1))
    tx = x + 1.0
    if icon:
        img(icon, x + 1.9, y + h - 1.9, 2.3, z=4)
        tx = x + 3.5
    ax.text(tx, y + h - 1.9, label, ha="left", va="center", fontsize=fs,
            fontweight="bold", color=color, zorder=4)
    if sublabel:
        ax.text(tx, y + h - 4.0, sublabel, ha="left", va="center", fontsize=8.3,
                color=sub_color or C_MUTED, style="italic", zorder=4)


def badge(x: float, y: float, n: int) -> None:
    ax.add_patch(Circle((x, y), 1.3, facecolor=C_FLOW, edgecolor="white", lw=1.4, zorder=9))
    ax.text(x, y, str(n), ha="center", va="center", fontsize=9.2, fontweight="bold",
            color="white", zorder=10)


def route(points, n: int | None = None, badge_at=None, color: str = C_FLOW,
          lw: float = 1.9, ls: str = "-") -> None:
    """Orthogonal polyline with an arrowhead on the final segment."""
    for a, b in zip(points[:-2], points[1:-1]):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-", linewidth=lw, color=color,
                                     linestyle=ls, shrinkA=0, shrinkB=0, zorder=3))
    ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle="-|>", mutation_scale=17,
                                 linewidth=lw, color=color, linestyle=ls,
                                 shrinkA=0, shrinkB=2, zorder=3))
    if n is not None and badge_at is not None:
        badge(*badge_at, n)


# --------------------------------------------------------------------------- title
ax.text(85, 82.0, "HDB Resale Data Platform — Data Ingestion & Data Exploitation Architecture",
        ha="center", fontsize=23, fontweight="bold", color=C_TEXT)
ax.text(85, 79.2,
        "Scheduled batch ingestion from the public data.gov.sg endpoint into a network-segmented private data lake, "
        "queried by Tableau over PrivateLink with no public internet path",
        ha="center", fontsize=12.5, color=C_MUTED)

# --------------------------------------------------------------------------- public internet
group(1, 38, 14, 16, "Public Internet", "#8A8A8A", ls=":", lw=1.6, fs=10)
node(INTERNET, 8, 47.5, "data.gov.sg", "Public HTTPS API;\nfiles > 100 MB served\nfrom its own S3 bucket", size=3.2)

# --------------------------------------------------------------------------- AWS cloud
group(17, 1.5, 152, 75.5, "AWS Cloud   —   Region: ap-southeast-1 (Singapore)", C_CLOUD,
      icon=REGION_G, lw=2.4, fs=12.5)

# ---- governance band
group(20, 60.5, 146, 13, "Orchestration, Security & Governance   (regional serverless — no VPC footprint)",
      C_GOV, lw=1.6, fs=10.5)
BAND = [
    (EVENTBRIDGE, "Amazon EventBridge", "Monthly batch\nschedule"),
    (SFN, "AWS Step Functions", "Orchestration, retries,\nDQ publish gate"),
    (SNS, "Amazon SNS", "Job + data-quality\nalerts to DE on-call"),
    (SECRETS, "AWS Secrets Manager", "HMAC pepper for\nde-identification"),
    (LAKEFORM, "AWS Lake Formation", "Table/column grants\nover the Glue Catalog"),
    (CLOUDTRAIL, "CloudTrail + CloudWatch", "API audit, job metrics,\nlog retention"),
    (GUARDDUTY, "Amazon GuardDuty", "Threat detection,\nincl. S3 + VPC findings"),
]
for i, (icon_name, title, detail) in enumerate(BAND):
    node(icon_name, 20 + (146 / 7) * (i + 0.5), 68.2, title, detail, size=2.7, ts=8.9, ds=7.3)

# --------------------------------------------------------------------------- 1. Ingestion VPC
group(19, 3.5, 38, 52.5, "Ingestion (Landing) VPC   10.1.0.0/16", C_VPC, icon=VPC_GROUP,
      sublabel="The only VPC with any route to the internet", sub_color=C_ALERT)

group(21, 40, 34, 10, "Public subnets (multi-AZ)   10.1.0.0/24", C_PUBLIC, icon=PUB_SUBNET,
      lw=1.5, fs=9.2)
node(IGW, 30, 44.3, "Internet Gateway", size=2.4, ts=8.8)
node(NAT_GW, 46, 44.3, "NAT Gateway  (per AZ)", size=2.4, ts=8.8)

group(21, 25, 34, 12, "Inspection subnets   10.1.10.0/24", C_PRIVATE, icon=PRIV_SUBNET,
      lw=1.5, fs=9.2)
node(NETFW, 38, 31.8, "AWS Network Firewall",
     "Allow-list: data.gov.sg API hosts only;\nall else dropped + logged · alt: DNS Firewall",
     size=2.6, ts=8.9, ds=7.4)

group(21, 5.5, 34, 17, "Private subnets   10.1.20.0/24", C_PRIVATE, icon=PRIV_SUBNET,
      lw=1.5, fs=9.2)
node(GLUE, 31, 16, "AWS Glue (Python Shell)",
     "Streams source files to S3 by\nmultipart upload — no size ceiling.\n1/16 DPU: right-sized for I/O work",
     size=2.6, ts=8.9, ds=7.4)
node(VPC_EP, 46, 16, "VPC Endpoints",
     "S3 Gateway: file download + raw/ writes\nInterface: Glue · Logs · STS",
     size=2.4, ts=8.9, ds=7.4)
ax.text(38, 7.3, "VPC Flow Logs enabled  ·  SG: egress :443; inbound only Glue's self-referencing rule",
        ha="center", va="center", fontsize=7.8, color=C_MUTED, style="italic", zorder=6)

# --------------------------------------------------------------------------- 2. Processing VPC
group(61, 3.5, 38, 52.5, "Processing VPC   10.2.0.0/16", C_VPC, icon=VPC_GROUP,
      sublabel="No IGW · no NAT · zero internet reachability", sub_color=C_ALERT)

group(63, 5.5, 34, 44.5, "Private subnets (multi-AZ)   10.2.20.0/24", C_PRIVATE,
      icon=PRIV_SUBNET, lw=1.5, fs=9.2)
node(GLUE, 73, 44, "AWS Glue ETL (PySpark)",
     "Part 1 logic at scale: combine,\nlease, anomaly, identifier, HMAC.\nWrites Parquet partitioned by month",
     size=2.8, ts=8.9, ds=7.4)
node(GLUE_DQ, 89, 35, "AWS Glue Data Quality",
     "Jan-2012 domain rules;\nfailures routed to quarantine", size=2.5, ts=8.9, ds=7.4)
node(GLUE_CRAWLER, 73, 25, "AWS Glue Crawler",
     "Registers schema and\nnew month partitions", size=2.5, ts=8.9, ds=7.4)
node(VPC_EP, 80, 14, "VPC Endpoints",
     "S3 (Gateway)  ·  Secrets Manager · KMS · Glue · STS · Logs\n(Interface / PrivateLink) — the HMAC pepper is fetched\nwith no internet egress anywhere in the path",
     size=2.4, ts=8.9, ds=7.4)

# --------------------------------------------------------------------------- 3. Data lake
group(103, 3.5, 34, 52.5, "Data Lake — Amazon S3", C_LAKE, icon=S3,
      sublabel="Regional service; reachable only via VPC endpoints")

node(BUCKET, 120, 47, "raw /   (landing)", "Byte-for-byte; versioned", size=2.5, ts=9.0, ds=7.4)
node(BUCKET, 111, 38.5, "cleaned /", "Validated (Parquet)", size=2.3, ts=8.8, ds=7.4)
node(BUCKET, 129, 38.5, "transformed /", "+ Resale Identifier", size=2.3, ts=8.8, ds=7.4)
node(BUCKET, 111, 30, "quarantined /", "DE triage only", size=2.3, ts=8.8, ds=7.4)
node(BUCKET, 129, 30, "hashed /", "De-identified", size=2.3, ts=8.8, ds=7.4)
node(KMS, 111, 21.5, "AWS KMS (CMK)", "SSE-KMS per zone", size=2.4, ts=8.8, ds=7.4)
node(BUCKET, 129, 21.5, "athena-results /", "7-day lifecycle", size=2.3, ts=8.8, ds=7.4)
node(GLUE_CATALOG, 111, 12, "Glue Data Catalog", "Schema + partitions", size=2.4, ts=8.8, ds=7.4)
node(ATHENA, 129, 12, "Amazon Athena", "Scan cap + reuse", size=2.6, ts=8.8, ds=7.4)
ax.text(120, 4.8, "Block Public Access  ·  bucket policies scoped to the platform VPC endpoints",
        ha="center", va="center", fontsize=7.8, color=C_MUTED, style="italic", zorder=6)

# --------------------------------------------------------------------------- 4. Consumption VPC
group(141, 3.5, 26, 52.5, "Consumption VPC   10.3.0.0/16", C_VPC, icon=VPC_GROUP, fs=10.0,
      sublabel="Data Science Team · no internet route", sub_color=C_ALERT)

group(143, 5.5, 22, 44.5, "Private subnets   10.3.20.0/24", C_PRIVATE, icon=PRIV_SUBNET,
      lw=1.5, fs=9.2)
node(EC2, 154, 41, "Tableau Server on EC2",
     "Native Athena JDBC/ODBC\nconnector; analysts reach it\nvia internal ALB + IdP SSO", size=2.8, ts=8.9, ds=7.4)
node(VPC_EP, 154, 26, "Interface Endpoints\n(PrivateLink)",
     "Athena · Glue · STS —\nqueries never traverse\nthe public internet", size=2.5, ts=8.9, ds=7.4)
node(VPC_EP, 154, 13, "S3 Gateway Endpoint",
     "Reads query results\nand extract refreshes", size=2.4, ts=8.9, ds=7.4)

# --------------------------------------------------------------------------- flows
CH_TOP = 58.2       # horizontal channel between the VPC row and the governance band
CH_A = 59           # vertical channel: Ingestion VPC | Processing VPC
CH_B = 101          # vertical channel: Processing VPC | Data Lake
CH_LAKE = 135.5     # vertical channel inside the lake, right of the bucket captions
CH_C = 138          # vertical channel: Data Lake | Consumption VPC

# 1 - schedule triggers the ingestion job
route([(51.3, 66.3), (51.3, CH_TOP), (38, CH_TOP), (38, 56.2)], n=1, badge_at=(44.5, CH_TOP))
# 2 - all egress is forced through the inspection subnet, then NAT, then IGW
route([(31, 17.4), (31, 23.6), (50, 23.6), (50, 31.8), (39.4, 31.8)], n=2, badge_at=(44.5, 23.6))
route([(38, 33.2), (38, 38.4), (46, 38.4), (46, 42.9)])
route([(44.6, 44.3), (31.4, 44.3)])
# 3 - the platform's only outbound internet hop
route([(28.6, 44.3), (17.2, 44.3), (17.2, 47.5), (9.8, 47.5)], n=3, badge_at=(22.5, 44.3))
# 4 - raw files land in the lake through the S3 gateway endpoint
route([(32.4, 16), (44.6, 16)])
route([(47.3, 16), (CH_A, 16), (CH_A, CH_TOP), (120, CH_TOP), (120, 48.5)], n=4, badge_at=(90, CH_TOP))
# 5 - orchestrator triggers the ETL stage
route([(53.5, 66.3), (53.5, 59.8), (80, 59.8), (80, 56.2)], n=5, badge_at=(68, 59.8))
# 6 / 7 - ETL reads raw, writes the validated zones back
route([(118.7, 47), (73, 47), (73, 45.5)], n=6, badge_at=(CH_B, 47))
route([(74.5, 44), (CH_B + 1, 44), (CH_B + 1, 38.5), (109.7, 38.5)], n=7, badge_at=(CH_B + 1, 41.5))
# 8 - crawler registers schema + new partitions in the catalog
route([(74.3, 25), (CH_B + 1, 25), (CH_B + 1, 12), (109.7, 12)], n=8, badge_at=(CH_B + 1, 18))
# Athena reads the curated zones; catalog supplies schema
route([(130.2, 30), (CH_LAKE, 30), (CH_LAKE, 16), (129, 16), (129, 13.4)])
route([(113.3, 12), (127.6, 12)])
# 9 / 10 - Tableau queries Athena over PrivateLink
route([(152.6, 41), (145.5, 41), (145.5, 26), (152.7, 26)], n=9, badge_at=(145.5, 33.5))
route([(152.7, 26), (CH_C - 0.2, 26), (CH_C - 0.2, 12), (130.4, 12)], n=10, badge_at=(CH_C - 0.2, 16))
# 11 - results are read back privately through the S3 gateway endpoint
route([(130.2, 21.5), (CH_C + 2.2, 21.5), (CH_C + 2.2, 13), (152.75, 13)], n=11, badge_at=(134.3, 21.5))

# --------------------------------------------------------------------------- footer
ax.text(18, -1.0,
        "1  scheduled trigger      2  egress forced through allow-list firewall      3  API calls (only internet traffic)      "
        "4  file streamed via S3 Gateway Endpoint into raw/      5  trigger ETL      6  read raw",
        ha="left", va="center", fontsize=9.6, color=C_MUTED)
ax.text(18, -2.8,
        "7  write validated Parquet zones      8  DQ publish gate, then register partitions      9  Tableau query      "
        "10  Athena over PrivateLink      11  results read back privately",
        ha="left", va="center", fontsize=9.6, color=C_MUTED)

ax.set_xlim(XMIN, XMAX)
ax.set_ylim(YMIN, YMAX)
plt.savefig(OUT_PATH, dpi=DPI, bbox_inches="tight", facecolor="white", pad_inches=0.3)
print(f"Saved: {OUT_PATH}")
