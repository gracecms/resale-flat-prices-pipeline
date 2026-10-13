"""Generate an editable draw.io (diagrams.net) version of the Part 2 architecture.

Produces `data_platform_architecture.drawio` — plain, uncompressed mxGraph XML, so it is
diffable in git and opens directly in draw.io / diagrams.net (File > Open, or the VS Code
Draw.io Integration extension).

The official AWS Architecture Icons are embedded as data URIs rather than referenced through
draw.io's own AWS shape library, so the file renders identically in every draw.io version with
no dependency on their shape naming. The icon pack is downloaded and cached by
`generate_diagram.py`; run that first (or let this script trigger the same download).

    python architecture/generate_drawio.py
"""
from __future__ import annotations

import base64
from pathlib import Path
from xml.sax.saxutils import escape

from aws_icons import (
    ATHENA, BUCKET, CLOUDTRAIL, EC2, EVENTBRIDGE, GLUE, GLUE_CATALOG, GLUE_CRAWLER, GLUE_DQ,
    GUARDDUTY, IGW, INTERNET, KMS, LAKEFORM, NAT_GW, NETFW, SECRETS, SFN, SNS, VPC_EP, ico,
)

OUT = Path(__file__).resolve().parent / "data_platform_architecture.drawio"

C_CLOUD, C_VPC, C_PUBLIC, C_PRIVATE = "#242F3E", "#8C4FFF", "#7AA116", "#00A4A6"
C_GOV, C_LAKE, C_MUTED, C_FLOW, C_ALERT = "#E7157B", "#3B48CC", "#5A6470", "#414D5C", "#C7303C"

cells: list[str] = []
_uid = iter(range(1000, 100000))
_img_cache: dict[str, str] = {}


def data_uri(pattern: str) -> str:
    if pattern not in _img_cache:
        raw = ico(pattern).read_bytes()
        _img_cache[pattern] = "data:image/png," + base64.b64encode(raw).decode("ascii")
    return _img_cache[pattern]


def nid(prefix: str = "c") -> str:
    return f"{prefix}{next(_uid)}"


def esc(text: str) -> str:
    return escape(text, {'"': "&quot;"})


def vertex(value: str, style: str, x: float, y: float, w: float, h: float,
           parent: str = "1", cid: str | None = None) -> str:
    cid = cid or nid()
    cells.append(
        f'        <mxCell id="{cid}" value="{esc(value)}" style="{esc(style)}" vertex="1" parent="{parent}">\n'
        f'          <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />\n'
        f'        </mxCell>'
    )
    return cid


def group(label: str, x: float, y: float, w: float, h: float, color: str,
          dashed: bool = False, sublabel: str = "", sub_color: str = C_MUTED,
          fontsize: int = 15) -> str:
    value = f"<b>{label}</b>"
    if sublabel:
        value += f'<br><font style="font-size:11px;font-weight:normal" color="{sub_color}"><i>{sublabel}</i></font>'
    style = (
        "rounded=0;whiteSpace=wrap;html=1;fillColor=none;"
        f"strokeColor={color};strokeWidth=2;dashed={1 if dashed else 0};"
        f"{'dashPattern=8 8;' if dashed else ''}"
        "verticalAlign=top;align=left;spacingLeft=12;spacingTop=8;"
        f"fontColor={color};fontSize={fontsize};container=0;"
    )
    return vertex(value, style, x, y, w, h)


def node(pattern: str, cx: float, top: float, size: float, title: str, detail: str = "",
         label_w: float = 210) -> str:
    """Icon with the label rendered underneath (draw.io's verticalLabelPosition=bottom)."""
    value = f"<b>{title}</b>"
    if detail:
        value += f'<br><font style="font-size:10px;font-weight:normal" color="{C_MUTED}">{detail}</font>'
    style = (
        "shape=image;html=1;labelBackgroundColor=none;imageAspect=0;aspect=fixed;"
        "verticalLabelPosition=bottom;verticalAlign=top;align=center;"
        f"fontSize=11;fontColor=#16191F;spacingTop=2;labelWidth={label_w};"
        f"image={data_uri(pattern)};"
    )
    return vertex(value, style, cx - size / 2, top, size, size)


def label(text: str, cx: float, cy: float, w: float = 420, h: float = 20,
          size: int = 10, color: str = C_MUTED, italic: bool = True) -> str:
    style = (
        f"text;html=1;align=center;verticalAlign=middle;fontSize={size};fontColor={color};"
        f"{'fontStyle=2;' if italic else ''}whiteSpace=wrap;"
    )
    return vertex(text, style, cx - w / 2, cy - h / 2, w, h)


def edge(src: str, tgt: str, waypoints: list[tuple[float, float]] | None = None,
         exit_xy: tuple[float, float] | None = None, entry_xy: tuple[float, float] | None = None,
         dashed: bool = False) -> None:
    style = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;"
        f"strokeColor={C_FLOW};strokeWidth=2;endArrow=blockThin;endFill=1;"
        f"dashed={1 if dashed else 0};{'dashPattern=6 6;' if dashed else ''}"
    )
    if exit_xy:
        style += f"exitX={exit_xy[0]};exitY={exit_xy[1]};exitDx=0;exitDy=0;"
    if entry_xy:
        style += f"entryX={entry_xy[0]};entryY={entry_xy[1]};entryDx=0;entryDy=0;"
    cid = nid("e")
    pts = ""
    if waypoints:
        inner = "".join(f'\n              <mxPoint x="{x}" y="{y}" />' for x, y in waypoints)
        pts = f'\n            <Array as="points">{inner}\n            </Array>'
    cells.append(
        f'        <mxCell id="{cid}" style="{esc(style)}" edge="1" parent="1" source="{src}" target="{tgt}">\n'
        f'          <mxGeometry relative="1" as="geometry">{pts}\n'
        f'          </mxGeometry>\n'
        f'        </mxCell>'
    )


def badge(n: int, cx: float, cy: float) -> None:
    style = (
        f"ellipse;whiteSpace=wrap;html=1;fillColor={C_FLOW};strokeColor=#ffffff;strokeWidth=2;"
        "fontColor=#ffffff;fontStyle=1;fontSize=12;align=center;verticalAlign=middle;"
    )
    vertex(str(n), style, cx - 14, cy - 14, 28, 28)


# =========================================================================== title
vertex("<b>HDB Resale Data Platform — Data Ingestion &amp; Data Exploitation Architecture</b>",
       "text;html=1;align=center;verticalAlign=middle;fontSize=26;fontColor=#16191F;",
       520, 20, 1640, 40)
label("Scheduled batch ingestion from the public data.gov.sg endpoint into a network-segmented private data lake, "
      "queried by Tableau over PrivateLink with no public internet path",
      1340, 78, w=1700, h=24, size=13, italic=False)

# =========================================================================== public internet
group("Public Internet", 40, 560, 230, 250, "#8A8A8A", dashed=True, fontsize=13)
n_internet = node(INTERNET, 155, 620, 72, "data.gov.sg",
                  "Public HTTPS API · files &gt; 100 MB served from its own S3 bucket")

# =========================================================================== AWS cloud
group("AWS Cloud   —   Region: ap-southeast-1 (Singapore)", 300, 110, 2060, 1330, C_CLOUD, fontsize=17)

# ---- governance band
group("Orchestration, Security &amp; Governance   (regional serverless — no VPC footprint)",
      330, 160, 2000, 210, C_GOV, fontsize=13)
BAND = [
    (EVENTBRIDGE, "Amazon EventBridge", "Monthly batch schedule"),
    (SFN, "AWS Step Functions", "Orchestration, retries, DQ publish gate"),
    (SNS, "Amazon SNS", "Job + data-quality alerts"),
    (SECRETS, "AWS Secrets Manager", "HMAC pepper for de-identification"),
    (LAKEFORM, "AWS Lake Formation", "Table/column grants over the catalog"),
    (CLOUDTRAIL, "CloudTrail + CloudWatch", "API audit, job metrics, logs"),
    (GUARDDUTY, "Amazon GuardDuty", "Threat detection (S3 + VPC)"),
]
band_ids = []
for i, (icon_name, title, detail) in enumerate(BAND):
    band_ids.append(node(icon_name, 330 + (2000 / 7) * (i + 0.5), 210, 60, title, detail, label_w=250))
n_eventbridge, n_sfn = band_ids[0], band_ids[1]

# =========================================================================== ingestion VPC
g_ingest = group("Ingestion (Landing) VPC   10.1.0.0/16", 330, 410, 540, 990, C_VPC,
                 sublabel="The only VPC with any route to the internet", sub_color=C_ALERT)

group("Public subnet   10.1.0.0/24", 360, 480, 480, 185, C_PUBLIC, fontsize=12)
n_igw = node(IGW, 460, 525, 56, "Internet Gateway", "Egress routing only; no inbound")
n_nat = node(NAT_GW, 700, 525, 56, "NAT Gateway", "Sole outbound path")

group("Inspection subnet   10.1.10.0/24", 360, 700, 480, 200, C_PRIVATE, fontsize=12)
n_fw = node(NETFW, 600, 745, 64, "AWS Network Firewall",
            "Allow-list: data.gov.sg API hosts only (api-production, api-open);<br>all else dropped and logged · cost-optimised alt: DNS Firewall (README §4)",
            label_w=420)

group("Private subnet   10.1.20.0/24", 360, 935, 480, 430, C_PRIVATE, fontsize=12)
n_glue_in = node(GLUE, 470, 985, 64, "AWS Glue (Python Shell)",
                 "Streams source files to S3 by multipart<br>upload — no file-size ceiling.<br>1/16 DPU: right-sized for I/O work")
n_ep_in = node(VPC_EP, 730, 990, 56, "VPC Endpoints",
               "S3 Gateway: file download + raw/ writes<br>(never via firewall/NAT) · Interface:<br>Glue · Logs · STS")
label("VPC Flow Logs enabled  ·  SG: egress :443; inbound only Glue's self-referencing rule", 600, 1320, w=460)

# =========================================================================== processing VPC
g_proc = group("Processing VPC   10.2.0.0/16", 910, 410, 540, 990, C_VPC,
               sublabel="No IGW · no NAT · zero internet reachability", sub_color=C_ALERT)

group("Private subnet   10.2.20.0/24", 940, 480, 480, 885, C_PRIVATE, fontsize=12)
n_glue_etl = node(GLUE, 1040, 540, 64, "AWS Glue ETL (PySpark)",
                  "Part 1 logic at scale: combine, lease,<br>anomaly, identifier, HMAC.<br>Writes Parquet partitioned by month")
n_dq = node(GLUE_DQ, 1300, 745, 60, "AWS Glue Data Quality",
            "Jan-2012 domain rules;<br>failures routed to quarantine")
n_crawler = node(GLUE_CRAWLER, 1040, 940, 56, "AWS Glue Crawler",
                 "Registers schema and<br>new month partitions")
n_ep_proc = node(VPC_EP, 1180, 1140, 56, "VPC Endpoints",
                 "S3 (Gateway) · Secrets Manager · KMS · Glue · STS · Logs<br>(Interface / PrivateLink) — the HMAC pepper is<br>fetched with no internet egress in the path",
                 label_w=440)

# =========================================================================== data lake
group("Data Lake — Amazon S3", 1490, 410, 480, 990, C_LAKE,
      sublabel="Regional service; reachable only via VPC endpoints")
n_raw = node(BUCKET, 1730, 490, 56, "raw /  (landing)", "Byte-for-byte; versioned")
n_clean = node(BUCKET, 1610, 640, 56, "cleaned /", "Validated (Parquet)", label_w=170)
n_trans = node(BUCKET, 1850, 640, 56, "transformed /", "+ Resale Identifier", label_w=170)
n_quar = node(BUCKET, 1610, 790, 56, "quarantined /", "DE triage only", label_w=170)
n_hash = node(BUCKET, 1850, 790, 56, "hashed /", "De-identified", label_w=170)
n_kms = node(KMS, 1610, 940, 56, "AWS KMS (CMK)", "SSE-KMS per zone", label_w=170)
n_results = node(BUCKET, 1850, 940, 56, "athena-results /", "7-day lifecycle", label_w=170)
n_catalog = node(GLUE_CATALOG, 1610, 1100, 56, "Glue Data Catalog", "Schema + partitions", label_w=170)
n_athena = node(ATHENA, 1850, 1100, 60, "Amazon Athena", "Scan cap + result reuse", label_w=180)
label("Block Public Access  ·  bucket policies scoped to the platform VPC endpoints", 1730, 1330, w=460)

# =========================================================================== consumption VPC
group("Consumption VPC   10.3.0.0/16", 2010, 410, 330, 990, C_VPC,
      sublabel="Data Science Team · no internet route", sub_color=C_ALERT, fontsize=14)

group("Private subnets (2 AZs)   10.3.20.0/24", 2040, 480, 270, 885, C_PRIVATE, fontsize=12)
n_tableau = node(EC2, 2175, 540, 64, "Tableau Server on EC2",
                 "Native Athena JDBC/ODBC connector;<br>analysts reach it via internal<br>ALB + IdP SSO", label_w=240)
n_ep_cons = node(VPC_EP, 2175, 800, 56, "Interface Endpoints (PrivateLink)",
                 "Athena · Glue · STS — queries<br>never traverse the public internet", label_w=240)
n_ep_s3_cons = node(VPC_EP, 2175, 1070, 56, "S3 Gateway Endpoint",
                    "Reads query results and<br>extract refreshes", label_w=240)

# =========================================================================== flows
edge(n_eventbridge, n_sfn, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

# 1 - schedule triggers ingestion
edge(n_sfn, g_ingest, waypoints=[(616, 398), (550, 398)], exit_xy=(0.5, 1), entry_xy=(0.407, 0))
badge(1, 550, 398)

# 2 - egress forced through the inspection subnet
edge(n_glue_in, n_fw, waypoints=[(470, 917), (600, 917)], exit_xy=(0.5, 0), entry_xy=(0.5, 1))
badge(2, 535, 917)
edge(n_fw, n_nat, waypoints=[(600, 682), (700, 682)], exit_xy=(0.5, 0), entry_xy=(0.5, 1))
edge(n_nat, n_igw, exit_xy=(0, 0.5), entry_xy=(1, 0.5))

# 3 - the platform's only outbound internet hop
edge(n_igw, n_internet, waypoints=[(300, 553), (300, 656)], exit_xy=(0, 0.5), entry_xy=(1, 0.5))
badge(3, 360, 553)

# 4 - raw files land in the lake through the gateway endpoint
edge(n_glue_in, n_ep_in, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
edge(n_ep_in, n_raw, waypoints=[(890, 1018), (890, 386), (1730, 386)],
     exit_xy=(1, 0.5), entry_xy=(0.5, 0))
badge(4, 1300, 386)

# 5 - orchestrator triggers the ETL stage
edge(n_sfn, g_proc, waypoints=[(616, 398), (1180, 398)], exit_xy=(0.5, 1), entry_xy=(0.5, 0))
badge(5, 1180, 398)

# 6 / 7 - ETL reads raw, writes the validated zones
edge(n_raw, n_glue_etl, waypoints=[(1040, 518)], exit_xy=(0, 0.5), entry_xy=(0.5, 0))
badge(6, 1360, 518)
edge(n_glue_etl, n_clean, waypoints=[(1470, 572), (1470, 668)], exit_xy=(1, 0.5), entry_xy=(0, 0.5))
badge(7, 1470, 620)

# 8 - crawler registers schema + partitions
edge(n_crawler, n_catalog, waypoints=[(1470, 968), (1470, 1128)], exit_xy=(1, 0.5), entry_xy=(0, 0.5))
badge(8, 1470, 1048)

# Athena reads the curated zones; the catalog supplies schema
edge(n_hash, n_athena, waypoints=[(1945, 818), (1945, 1060), (1850, 1060)],
     exit_xy=(1, 0.5), entry_xy=(0.5, 0))
edge(n_catalog, n_athena, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

# 9 / 10 / 11 - Tableau queries Athena, results come back privately
edge(n_tableau, n_ep_cons, waypoints=[(2060, 572), (2060, 828)], exit_xy=(0, 0.5), entry_xy=(0, 0.5))
badge(9, 2060, 700)
edge(n_ep_cons, n_athena, waypoints=[(1982, 828), (1982, 1128)], exit_xy=(0, 0.5), entry_xy=(1, 0.5))
badge(10, 1982, 1020)
edge(n_results, n_ep_s3_cons, waypoints=[(1998, 968), (1998, 1098)], exit_xy=(1, 0.5), entry_xy=(0, 0.5))
badge(11, 1930, 968)

# =========================================================================== footer
label("1 scheduled trigger   ·   2 egress forced through allow-list firewall   ·   3 API calls (only internet traffic)   ·   "
      "4 file streamed via S3 Gateway Endpoint into raw/   ·   5 trigger ETL   ·   6 read raw",
      1200, 1470, w=1960, h=22, size=12)
label("7 write validated Parquet zones   ·   8 DQ publish gate, then register partitions   ·   9 Tableau query   ·   "
      "10 Athena over PrivateLink   ·   11 results read back privately",
      1200, 1496, w=1960, h=22, size=12)
label("Availability: ingestion and processing run in one AZ, since a re-run is their recovery path; the Tableau tier is multi-AZ. Costed alternatives in architecture/README.md.", 1200, 1522, w=1960, h=22, size=12)

# =========================================================================== emit
body = "\n".join(cells)
xml = f'''<mxfile host="app.diagrams.net" type="device">
  <diagram id="hdb-data-platform" name="HDB Data Platform Architecture">
    <mxGraphModel dx="1422" dy="762" grid="0" gridSize="10" guides="1" tooltips="1" connect="1"
                  arrows="1" fold="1" page="1" pageScale="1" pageWidth="2384" pageHeight="1684"
                  math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
{body}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
'''
OUT.write_text(xml)
print(f"Saved: {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
