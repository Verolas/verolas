"""The Verolas connector catalog.

A connector class is the *integration as a product*. It is static, code
managed, and ships with the app. An organisation installs a class once
(per firm) to authenticate; a project then binds one or more *instances*
of that class (a SharePoint library, an ACC hub, a Slack channel...) to
its workspace.

Tiers describe the implementation reality, not the price:

- A — OAuth 2 + a documented REST API. Self-serve install.
- B — Vendor SDK behind a free dev programme. Self-serve once the firm
       supplies its own API key, or shipped via app credentials where
       the vendor's policy allows.
- C — Paid partner agreement or on-prem agent. Installable on demand;
       an installation triggers the waitlist + sales flow until the
       partnership lands, at which point the auth method swaps in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ConnectorTier = Literal["A", "B", "C", "internal"]

ConnectorAuthMethod = Literal[
    "oauth2_pkce",
    "oauth2_client_credentials",
    "api_key",
    "vendor_sdk",
    "on_prem_agent",
    "internal",
]

ConnectorCategory = Literal[
    "cad_bim",
    "structural_fea",
    "geotech_fea",
    "documents",
    "construction_mgmt",
    "markup",
    "spreadsheets",
    "communication",
    "signing",
    "internal",
]


@dataclass(frozen=True, slots=True)
class ConnectorClass:
    """Static catalog entry for one connector class."""

    id: str
    name: str
    vendor: str
    category: ConnectorCategory
    tier: ConnectorTier
    auth_method: ConnectorAuthMethod
    blurb: str
    region_tags: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    docs_url: str | None = None
    instance_label: str = "Resource"


_ALL_REGIONS = ("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca")
_EU_REGIONS = ("de", "ch", "at", "fr", "nl", "be", "uk")
_US_REGIONS = ("us", "ca")


CONNECTORS: dict[str, ConnectorClass] = {
    c.id: c
    for c in (
        # ---- cad_bim ----
        ConnectorClass(
            id="autodesk-aps",
            name="Autodesk Platform Services",
            vendor="Autodesk",
            category="cad_bim",
            tier="A",
            auth_method="oauth2_pkce",
            blurb=(
                "Sign in once to reach AutoCAD, Revit, BIM 360, and "
                "Autodesk Construction Cloud hubs from every project."
            ),
            region_tags=_ALL_REGIONS,
            scopes=("data:read", "data:write", "account:read", "viewables:read"),
            docs_url="https://aps.autodesk.com/",
            instance_label="ACC hub or BIM 360 account",
        ),
        ConnectorClass(
            id="allplan",
            name="Allplan",
            vendor="Nemetschek",
            category="cad_bim",
            tier="B",
            auth_method="vendor_sdk",
            blurb="Nemetschek Allplan model exchange via the Allplan Bimplus API.",
            region_tags=_EU_REGIONS,
            scopes=("bimplus.models.read", "bimplus.models.write"),
            instance_label="Bimplus project",
        ),
        ConnectorClass(
            id="tekla",
            name="Tekla Structures",
            vendor="Trimble",
            category="cad_bim",
            tier="C",
            auth_method="on_prem_agent",
            blurb=(
                "Read Tekla Structural Designer + Tekla Structures models "
                "via the Verolas Bridge agent."
            ),
            region_tags=_ALL_REGIONS,
            instance_label="Tekla model",
        ),
        ConnectorClass(
            id="rhino",
            name="Rhino + Grasshopper",
            vendor="McNeel",
            category="cad_bim",
            tier="B",
            auth_method="on_prem_agent",
            blurb=(
                "Read .3dm geometry and Grasshopper script results "
                "through the Rhino Compute bridge."
            ),
            region_tags=_ALL_REGIONS,
            instance_label="Rhino Compute endpoint",
        ),
        # ---- structural_fea ----
        ConnectorClass(
            id="dlubal-rfem",
            name="Dlubal RFEM / RSTAB",
            vendor="Dlubal Software",
            category="structural_fea",
            tier="C",
            auth_method="on_prem_agent",
            blurb="Submit and parse Dlubal RFEM and RSTAB runs from a project workspace.",
            region_tags=_EU_REGIONS + _US_REGIONS,
            instance_label="RFEM workstation",
        ),
        ConnectorClass(
            id="sofistik",
            name="SOFiSTiK",
            vendor="SOFiSTiK AG",
            category="structural_fea",
            tier="C",
            auth_method="on_prem_agent",
            blurb="SOFiSTiK SOFiLOAD + SOFiMSHC + ASE jobs scheduled via the Verolas Bridge agent.",
            region_tags=_EU_REGIONS,
            instance_label="SOFiSTiK workstation",
        ),
        ConnectorClass(
            id="csi-suite",
            name="SAP2000 / ETABS",
            vendor="Computers and Structures Inc.",
            category="structural_fea",
            tier="C",
            auth_method="on_prem_agent",
            blurb="Submit ETABS and SAP2000 analyses via the CSI OAPI through the bridge agent.",
            region_tags=_ALL_REGIONS,
            instance_label="CSI workstation",
        ),
        ConnectorClass(
            id="staad",
            name="STAAD.Pro",
            vendor="Bentley Systems",
            category="structural_fea",
            tier="C",
            auth_method="on_prem_agent",
            blurb="Read and run STAAD.Pro models via OpenSTAAD through the bridge agent.",
            region_tags=_ALL_REGIONS,
            instance_label="STAAD workstation",
        ),
        ConnectorClass(
            id="idea-statica",
            name="IDEA StatiCa",
            vendor="IDEA StatiCa s.r.o.",
            category="structural_fea",
            tier="C",
            auth_method="on_prem_agent",
            blurb="Connection design + member checks via the IDEA StatiCa Open Model API.",
            region_tags=_EU_REGIONS + _US_REGIONS,
            instance_label="IDEA StatiCa workstation",
        ),
        # ---- geotech_fea ----
        ConnectorClass(
            id="plaxis",
            name="Plaxis",
            vendor="Bentley Systems",
            category="geotech_fea",
            tier="C",
            auth_method="on_prem_agent",
            blurb="Plaxis 2D + 3D geotechnical models via the Plaxis Remote Scripting Server.",
            region_tags=_EU_REGIONS + _US_REGIONS,
            instance_label="Plaxis workstation",
        ),
        # ---- documents ----
        ConnectorClass(
            id="bentley-projectwise",
            name="Bentley ProjectWise",
            vendor="Bentley Systems",
            category="documents",
            tier="C",
            auth_method="on_prem_agent",
            blurb="ProjectWise document repository sync via the ProjectWise Web SDK.",
            region_tags=_ALL_REGIONS,
            instance_label="ProjectWise datasource",
        ),
        ConnectorClass(
            id="ms-sharepoint",
            name="SharePoint",
            vendor="Microsoft",
            category="documents",
            tier="A",
            auth_method="oauth2_pkce",
            blurb=(
                "SharePoint document libraries via Microsoft Graph; bind any library per project."
            ),
            region_tags=_ALL_REGIONS,
            scopes=("Sites.Read.All", "Files.Read.All", "offline_access"),
            docs_url="https://learn.microsoft.com/graph/",
            instance_label="SharePoint library",
        ),
        ConnectorClass(
            id="ms-onedrive",
            name="OneDrive",
            vendor="Microsoft",
            category="documents",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="OneDrive for Business folders via Microsoft Graph.",
            region_tags=_ALL_REGIONS,
            scopes=("Files.Read.All", "offline_access"),
            instance_label="OneDrive folder",
        ),
        ConnectorClass(
            id="box",
            name="Box",
            vendor="Box, Inc.",
            category="documents",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Box enterprise folder sync via the Box Content API.",
            region_tags=_ALL_REGIONS,
            scopes=("root_readwrite",),
            instance_label="Box folder",
        ),
        ConnectorClass(
            id="dropbox",
            name="Dropbox",
            vendor="Dropbox",
            category="documents",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Dropbox Business team folder sync.",
            region_tags=_ALL_REGIONS,
            scopes=("files.content.read", "files.metadata.read"),
            instance_label="Dropbox folder",
        ),
        ConnectorClass(
            id="egnyte",
            name="Egnyte",
            vendor="Egnyte, Inc.",
            category="documents",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Egnyte Connect document workspace sync.",
            region_tags=_US_REGIONS + _EU_REGIONS,
            scopes=("Egnyte.filesystem",),
            instance_label="Egnyte folder",
        ),
        ConnectorClass(
            id="newforma",
            name="Newforma Project Center",
            vendor="Newforma",
            category="documents",
            tier="B",
            auth_method="vendor_sdk",
            blurb="Newforma Project Center file index + transmittal sync.",
            region_tags=_US_REGIONS + _EU_REGIONS,
            instance_label="Newforma project",
        ),
        # ---- construction_mgmt ----
        ConnectorClass(
            id="procore",
            name="Procore",
            vendor="Procore Technologies",
            category="construction_mgmt",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Procore RFIs, submittals, drawings, and daily logs via the Procore REST API.",
            region_tags=(*_US_REGIONS, "au", "uk"),
            scopes=("read", "write"),
            docs_url="https://developers.procore.com/",
            instance_label="Procore company / project",
        ),
        # ---- markup ----
        ConnectorClass(
            id="bluebeam-studio",
            name="Bluebeam Studio",
            vendor="Bluebeam, Inc.",
            category="markup",
            tier="B",
            auth_method="oauth2_pkce",
            blurb="Bluebeam Studio sessions + projects for shared PDF markup.",
            region_tags=_ALL_REGIONS,
            scopes=("studio.read", "studio.write"),
            instance_label="Bluebeam Studio project",
        ),
        # ---- spreadsheets ----
        ConnectorClass(
            id="ms-excel",
            name="Excel Online",
            vendor="Microsoft",
            category="spreadsheets",
            tier="A",
            auth_method="oauth2_pkce",
            blurb=(
                "Live Excel workbooks via Microsoft Graph; "
                "calc-sheet round-trips with named ranges."
            ),
            region_tags=_ALL_REGIONS,
            scopes=("Files.ReadWrite.All", "offline_access"),
            instance_label="Excel workbook",
        ),
        ConnectorClass(
            id="google-sheets",
            name="Google Sheets",
            vendor="Google",
            category="spreadsheets",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Live Google Sheets via the Sheets API; bind any spreadsheet per project.",
            region_tags=_ALL_REGIONS,
            scopes=("https://www.googleapis.com/auth/spreadsheets",),
            instance_label="Google spreadsheet",
        ),
        # ---- communication ----
        ConnectorClass(
            id="ms-teams",
            name="Microsoft Teams",
            vendor="Microsoft",
            category="communication",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Post run summaries and review threads to a Teams channel.",
            region_tags=_ALL_REGIONS,
            scopes=("ChannelMessage.Send", "Channel.ReadBasic.All"),
            instance_label="Teams team / channel",
        ),
        ConnectorClass(
            id="slack",
            name="Slack",
            vendor="Slack Technologies",
            category="communication",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Post run updates + reviewer mentions to a Slack channel.",
            region_tags=_ALL_REGIONS,
            scopes=("chat:write", "channels:read", "files:write"),
            instance_label="Slack workspace / channel",
        ),
        ConnectorClass(
            id="ms-outlook",
            name="Outlook + Exchange",
            vendor="Microsoft",
            category="communication",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Send transmittals and reviewer requests from Outlook via Microsoft Graph.",
            region_tags=_ALL_REGIONS,
            scopes=("Mail.Send", "Mail.ReadWrite"),
            instance_label="Outlook mailbox",
        ),
        ConnectorClass(
            id="gmail",
            name="Gmail",
            vendor="Google",
            category="communication",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Send transmittals and reviewer requests from Gmail.",
            region_tags=_ALL_REGIONS,
            scopes=("https://www.googleapis.com/auth/gmail.send",),
            instance_label="Gmail mailbox",
        ),
        ConnectorClass(
            id="google-drive",
            name="Google Drive",
            vendor="Google",
            category="communication",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Google Drive folder sync; bind any shared drive or folder per project.",
            region_tags=_ALL_REGIONS,
            scopes=("https://www.googleapis.com/auth/drive",),
            instance_label="Google Drive folder",
        ),
        # ---- signing ----
        ConnectorClass(
            id="docusign",
            name="DocuSign",
            vendor="DocuSign",
            category="signing",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Send signed deliverables through a DocuSign envelope.",
            region_tags=_ALL_REGIONS,
            scopes=("signature", "impersonation"),
            instance_label="DocuSign account",
        ),
        ConnectorClass(
            id="adobe-sign",
            name="Adobe Acrobat Sign",
            vendor="Adobe",
            category="signing",
            tier="A",
            auth_method="oauth2_pkce",
            blurb="Send signed deliverables through Adobe Acrobat Sign.",
            region_tags=_ALL_REGIONS,
            scopes=("agreement_send", "agreement_read"),
            instance_label="Adobe Sign account",
        ),
        ConnectorClass(
            id="d-trust-qes",
            name="D-Trust QES",
            vendor="Bundesdruckerei",
            category="signing",
            tier="C",
            auth_method="on_prem_agent",
            blurb="Qualified electronic signatures for German permit submissions.",
            region_tags=("de", "ch", "at"),
            instance_label="D-Trust account",
        ),
        # ---- internal ----
        ConnectorClass(
            id="verolas-library",
            name="Verolas Library",
            vendor="Verolas",
            category="internal",
            tier="internal",
            auth_method="internal",
            blurb=(
                "Org-managed file library: upload PDFs, drawings, calc sheets, or "
                "reference standards once and mount any folder into a project."
            ),
            region_tags=_ALL_REGIONS,
            instance_label="Library folder",
        ),
    )
}


def lookup(class_id: str) -> ConnectorClass | None:
    """Return the catalog entry for a class id, or None if unknown."""
    return CONNECTORS.get(class_id)


def by_category() -> dict[str, list[ConnectorClass]]:
    """Group catalog entries by category, preserving catalog order."""
    grouped: dict[str, list[ConnectorClass]] = {}
    for entry in CONNECTORS.values():
        grouped.setdefault(entry.category, []).append(entry)
    return grouped


__all__ = [
    "CONNECTORS",
    "ConnectorAuthMethod",
    "ConnectorCategory",
    "ConnectorClass",
    "ConnectorTier",
    "by_category",
    "lookup",
]
