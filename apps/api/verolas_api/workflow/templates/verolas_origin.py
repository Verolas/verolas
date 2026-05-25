"""Verolas template: Origin (greenfield structural concept design).

The ten-node Origin workflow takes an architect's DWG or IFC into a
sealed structural concept design. It is sold standalone or embedded as
a sub-workflow ahead of a downstream Statik permit workflow.

Conceptually the steps mirror the Genia-style CAD-to-options-to-export
loop: the engineer submits a brief and CAD, the platform parses each
floor into vector geometry, the engineer reviews/corrects the parse,
roof framing is placed, the AI proposes three structural options with
takeoff and DCR analysis, the engineer picks one, refines members, and
exports a sealed DWG + PDF + IFC package.

All ten nodes belong to a single `origin` group so the parent workflow
canvas can collapse them into one supernode and expand inline. Inside
the group the graph is a simple linear chain; group structure is pure
UI so the executor still walks the flat node list.

SLA labels live as integer params (sla_minutes / sla_business_days) so
the UI renders them as expected-vs-elapsed badges without baking day
numbers into node names.
"""

from __future__ import annotations

from verolas_api.workflow.registry import register_template
from verolas_api.workflow.schema import (
    EdgeDef,
    GroupDef,
    NodeDef,
    NodeKind,
    TemplateDefinition,
    TemplateSpec,
)

_GROUP_KEY = "origin"


def _build() -> TemplateSpec:
    nodes = [
        NodeDef(
            key="submit_brief",
            kind=NodeKind.MANUAL,
            name="Submit project brief",
            description=(
                "Name the project, set the address, choose the asset "
                "type (residential, mixed-use, etc.) and the structural "
                "system (light-frame wood, steel MRF, RC flat slab, "
                "CLT hybrid, ...). The brief seeds every downstream "
                "step. Mark this node done once the brief is complete."
            ),
            params={
                "step": "brief",
                "sla_minutes": 15,
                "expected_outputs": [
                    "project_name",
                    "address",
                    "asset_type",
                    "structural_system",
                ],
            },
            group_key=_GROUP_KEY,
        ),
        NodeDef(
            key="upload_cad",
            kind=NodeKind.MANUAL,
            name="Upload architect CAD",
            description=(
                "Drop the architect drawing as DWG, DXF, or IFC. The "
                "upload guide previews the five quality checks the "
                "parser will run (single-plan, segmentation, alignment, "
                "walls, roof). Re-upload until the checks pass."
            ),
            params={
                "step": "cad",
                "sla_minutes": 10,
                "accepted_formats": ["dwg", "dxf", "ifc"],
                "expected_outputs": ["cad_file_key", "cad_format"],
            },
            group_key=_GROUP_KEY,
        ),
        NodeDef(
            key="parameters",
            kind=NodeKind.MANUAL,
            name="Set design parameters",
            description=(
                "Fill in the parameter tabs: Code & Classification, "
                "Gravity Loads (snow / live / dead per floor), "
                "Limitations (deflection, depths), Material Allowed "
                "(beam / joist / wall stud / post / foundation), and "
                "Calculation Preference (Optimized vs Conservative)."
            ),
            params={
                "step": "parameters",
                "sla_minutes": 20,
                "expected_outputs": [
                    "code_classification",
                    "gravity_loads",
                    "limitations",
                    "material_allowed",
                    "calc_preference",
                ],
            },
            group_key=_GROUP_KEY,
        ),
        NodeDef(
            key="floor_parse",
            kind=NodeKind.AUTOMATED,
            name="Parse floors from CAD",
            description=(
                "Read the uploaded DWG/DXF/IFC, segment per floor, and "
                "emit normalized vector geometry (walls, openings, "
                "slabs, columns) as SVG previews and a geometry JSON "
                "the next steps consume."
            ),
            params={
                "tool": "verolas.origin.floor_parse",
                "sla_minutes": 3,
            },
            group_key=_GROUP_KEY,
        ),
        NodeDef(
            key="architectural_review",
            kind=NodeKind.MANUAL,
            name="Review parsed floors",
            description=(
                "Open the parsed-floor canvas, correct anything the "
                "parser misread, and confirm wall lines, openings, and "
                "columns per floor. Palette: Wall, Door, Window, "
                "Stairs, Deck, Opening, Column, Roof."
            ),
            params={
                "step": "architectural_review",
                "sla_minutes": 30,
                "expected_outputs": ["reviewed_geometry_key"],
            },
            group_key=_GROUP_KEY,
        ),
        NodeDef(
            key="roof_framing",
            kind=NodeKind.MANUAL,
            name="Place roof framing",
            description=(
                "Lay out roof trusses and girder trusses over the "
                "footprint. The canvas validates that regular truss "
                "coverage spans the full roof area before the next "
                "step runs."
            ),
            params={
                "step": "roof_framing",
                "sla_minutes": 20,
                "expected_outputs": ["roof_framing_key"],
            },
            group_key=_GROUP_KEY,
        ),
        NodeDef(
            key="ai_options",
            kind=NodeKind.AUTOMATED,
            name="AI proposes three options",
            description=(
                "The grid engine builds three candidate bay grids "
                "(Optimized, Balanced, Conservative). The AI design "
                "assistant refines each into a concept option with "
                "material takeoff, DCR distribution, and "
                "constructibility metrics."
            ),
            params={
                "tool": "verolas.origin.generator",
                "sla_minutes": 5,
            },
            group_key=_GROUP_KEY,
        ),
        NodeDef(
            key="select_option",
            kind=NodeKind.GATE_APPROVE,
            name="Select an option",
            description=(
                "Pick the option that goes to refinement. Approve to "
                "confirm (record the option_id in the note); Reject to "
                "send the AI back for another round with adjusted "
                "parameters."
            ),
            params={
                "assignee_role": "project_lead",
                "sla_business_days": 1,
            },
            group_key=_GROUP_KEY,
        ),
        NodeDef(
            key="detail_edit",
            kind=NodeKind.MANUAL,
            name="Detail the selected option",
            description=(
                "Open the layered detail editor for the chosen option. "
                "Toggle layers (walls, beams, joists, posts, trusses, "
                "foundation), click any member to edit its type, "
                "sizing, and connection. Live 3D preview shows the "
                "assembled structure."
            ),
            params={
                "step": "detail_edit",
                "sla_business_days": 2,
                "expected_outputs": ["refined_option_key"],
            },
            group_key=_GROUP_KEY,
        ),
        NodeDef(
            key="export_seal",
            kind=NodeKind.MANUAL,
            name="Engineer seals and exports",
            description=(
                "Licensed structural engineer (Tragwerksplaner in DE, "
                "PE/SE in US, ingenieur structures in FR) signs off, "
                "applies their professional seal or qualified "
                "electronic signature, and exports the DWG, PDF/A "
                "report, and IFC package."
            ),
            params={
                "step": "export_seal",
                "sla_business_days": 5,
                "expected_outputs": [
                    "sealed_dwg_key",
                    "sealed_pdf_key",
                    "sealed_ifc_key",
                ],
            },
            group_key=_GROUP_KEY,
        ),
    ]

    edges = [
        EdgeDef(from_key="submit_brief", to_key="upload_cad"),
        EdgeDef(from_key="upload_cad", to_key="parameters"),
        EdgeDef(from_key="parameters", to_key="floor_parse"),
        EdgeDef(from_key="floor_parse", to_key="architectural_review"),
        EdgeDef(from_key="architectural_review", to_key="roof_framing"),
        EdgeDef(from_key="roof_framing", to_key="ai_options"),
        EdgeDef(from_key="ai_options", to_key="select_option"),
        EdgeDef(from_key="select_option", to_key="detail_edit"),
        EdgeDef(from_key="detail_edit", to_key="export_seal"),
    ]

    groups = [
        GroupDef(
            key=_GROUP_KEY,
            name="Verolas Origin",
            description=(
                "AI-assisted greenfield structural concept design. "
                "Submit a brief and architect CAD, get three viable "
                "structural options with takeoffs and DCR, pick one, "
                "refine member-by-member, and export a sealed DWG + "
                "PDF + IFC."
            ),
            collapsed_by_default=True,
            params={"accent": "brand", "icon": "compass"},
        ),
    ]

    definition = TemplateDefinition(
        nodes=nodes,
        edges=edges,
        entry_keys=["submit_brief"],
        groups=groups,
    )

    return TemplateSpec(
        slug="verolas-origin",
        name="Verolas Origin: greenfield concept",
        description=(
            "AI-assisted structural concept design. Architect CAD in, "
            "three viable structural options out, engineer refines and "
            "seals the chosen one. Output feeds downstream Statik "
            "permit workflows."
        ),
        jurisdiction=None,
        project_type="concept",
        definition=definition,
    )


register_template(_build())
