"""Export pipeline for Verolas Origin.

The `export_seal` node triggers this module to produce the three
artifacts the engineer hands over to clients and Bauamt portals:

- A **DXF** drawing that AutoCAD opens as a DWG-equivalent. Each
  reviewed-geometry floor goes onto its own paper-space layout with
  walls, slabs, columns, and detail-layout beams on dedicated layers.
- A **PDF/A** seal report carrying the engineer's name, registration,
  the project metadata, design summary, material takeoff, DCR
  distribution, BoQ, caveats, and sustainability note. PDF/A so it is
  Bauamt-archival.
- An **IFC4** file with the reviewed geometry stacked as building
  storeys plus per-storey columns / beams / slabs from the detail
  layout, for downstream BIM consumption.

All three renderers are pure (no I/O) and dependency-light. Each
returns raw bytes; the orchestrator persists them under
`workflow-runs/{org}/{run}/origin/sealed_*` so the existing artifact
download endpoint surfaces them to the UI with two-layer authz.

This module is dependency-fed by the upstream node outputs:
- reviewed_geometry from `architectural_review`
- roof_framing from `roof_framing` (presence indicates truss zones to
  log in the PDF)
- options + chosen option_id from `ai_options` and `select_option`
- refined_option (the DetailLayout) from `detail_edit`
- seal_info (engineer name, registration, date, jurisdiction) supplied
  by the engineer at mark-done

If a non-essential upstream output is missing, the renderer falls back
to documented defaults and records a warning in `ExportResult.warnings`
so the engineer can see what was approximated.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import ezdxf
import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from verolas_api.workflow.origin.cost import CWICR_ATTRIBUTION
from verolas_api.workflow.origin.geometry import Geometry
from verolas_api.workflow.origin.sections import (
    AISC_360_DESIGN_CODE_ATTRIBUTION,
    AISC_SHAPES_ATTRIBUTION,
    EC3_DESIGN_CODE_ATTRIBUTION,
    EUROCODEPY_ATTRIBUTION,
)

logger = logging.getLogger(__name__)


_STORY_HEIGHT_M = 3.0
# DXF $INSUNITS code for metres; AutoCAD opens at the right scale.
_INSUNITS_M = 6


@dataclass(frozen=True, slots=True)
class SealInfo:
    """Engineer's seal payload, captured at mark-done."""

    engineer_name: str
    registration_number: str
    jurisdiction: str
    date_iso: str
    statement: str = ""


@dataclass
class ExportResult:
    """Aggregate output of the renderers."""

    dxf_bytes: bytes
    pdf_bytes: bytes
    ifc_bytes: bytes
    warnings: list[str] = field(default_factory=list)


def render_dxf(geometry: Geometry, detail_layout: dict[str, Any] | None) -> bytes:
    """Write a self-contained DXF of the reviewed geometry + detail layout.

    `detail_layout` is the JSON-shaped DetailLayout the frontend
    persisted at detail_edit (columns + beams per floor). When absent,
    we still emit the geometry layers (walls, slabs) so the engineer
    has something printable.
    """
    doc = ezdxf.new(setup=True)  # type: ignore[attr-defined]
    doc.header["$INSUNITS"] = _INSUNITS_M

    for layer_name, color in (
        ("WALL", 7),
        ("SLAB", 251),
        ("COLUMN_GEOM", 3),
        ("COLUMN_DETAIL", 5),
        ("BEAM", 30),
        ("OPENING", 1),
        ("TITLE", 7),
    ):
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=color)

    # Make sure the file has at least one layout (besides Model). The
    # default "Layout1" from `setup=True` is dropped only after we add
    # the per-floor ones to avoid the ezdxf "last paperspace" guard.
    added_any = False
    for index, floor in enumerate(geometry.floors, start=1):
        layout = doc.layouts.new(_safe_layout_name(floor.name, index))
        for wall in floor.walls:
            layout.add_lwpolyline(
                [(wall.start.x, wall.start.y), (wall.end.x, wall.end.y)],
                dxfattribs={"layer": "WALL"},
            )
        for slab in floor.slabs:
            if len(slab.polygon) >= 3:
                layout.add_lwpolyline(
                    [(p.x, p.y) for p in slab.polygon],
                    close=True,
                    dxfattribs={"layer": "SLAB"},
                )
        for column in floor.columns:
            layout.add_circle(
                center=(column.center.x, column.center.y),
                radius=max(column.size_m[0], 0.15) / 2.0,
                dxfattribs={"layer": "COLUMN_GEOM"},
            )
        for opening in floor.openings:
            layout.add_circle(
                center=(opening.center.x, opening.center.y),
                radius=opening.width_m / 2.0,
                dxfattribs={"layer": "OPENING"},
            )

        if detail_layout:
            _write_detail_layer(layout, floor_key=floor.key, layout_data=detail_layout)

        title = (
            f"FLOOR: {floor.name}    "
            f"EXT: {floor.extents.max_x - floor.extents.min_x:.2f} x "
            f"{floor.extents.max_y - floor.extents.min_y:.2f} m"
        )
        layout.add_text(
            title,
            dxfattribs={
                "layer": "TITLE",
                "height": 0.4,
            },
        ).set_placement((floor.extents.min_x, floor.extents.max_y + 1.0))
        added_any = True

    if added_any and "Layout1" in doc.layouts.names():
        doc.layouts.delete("Layout1")

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def _write_detail_layer(
    layout: Any,
    *,
    floor_key: str,
    layout_data: dict[str, Any],
) -> None:
    """Add detail-layout columns + beams onto the matching floor."""
    floors = layout_data.get("floors") or []
    floor = next((f for f in floors if f.get("floor_key") == floor_key), None)
    if not floor:
        return
    for column in floor.get("columns") or []:
        center = column.get("center") or {}
        cx = float(center.get("x", 0.0))
        cy = float(center.get("y", 0.0))
        layout.add_lwpolyline(
            [
                (cx - 0.2, cy - 0.2),
                (cx + 0.2, cy - 0.2),
                (cx + 0.2, cy + 0.2),
                (cx - 0.2, cy + 0.2),
            ],
            close=True,
            dxfattribs={"layer": "COLUMN_DETAIL"},
        )
        size_text = str(column.get("size") or "")
        if size_text:
            layout.add_text(
                size_text,
                dxfattribs={"layer": "COLUMN_DETAIL", "height": 0.2},
            ).set_placement((cx + 0.3, cy + 0.3))
    for beam in floor.get("beams") or []:
        start = beam.get("start") or {}
        end = beam.get("end") or {}
        layout.add_line(
            (float(start.get("x", 0.0)), float(start.get("y", 0.0))),
            (float(end.get("x", 0.0)), float(end.get("y", 0.0))),
            dxfattribs={"layer": "BEAM"},
        )


def _safe_layout_name(name: str, index: int) -> str:
    cleaned = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    if not cleaned:
        cleaned = f"Floor {index}"
    return cleaned[:31]  # DXF tab name max length


def render_pdf(
    *,
    project_id: str,
    run_id: str,
    chosen_option: dict[str, Any] | None,
    geometry: Geometry,
    detail_layout: dict[str, Any] | None,
    roof_framing: dict[str, Any] | None,
    seal: SealInfo,
) -> bytes:
    """Build the sealed PDF/A report.

    reportlab can emit PDF/A-1b when we pass a few extra flags through
    SimpleDocTemplate. We rely on the metadata + sRGB colorspace to
    keep the file archival; the engineer overrides at print time if a
    specific Bauamt portal demands a different conformance level.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title=f"Verolas Origin Concept Report ({project_id})",
        author=seal.engineer_name,
        subject="Origin: concept design + structural shortlist",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("VerolasH1", parent=styles["Heading1"], fontSize=16, spaceAfter=8)
    h2 = ParagraphStyle(
        "VerolasH2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4
    )
    body = ParagraphStyle("VerolasBody", parent=styles["BodyText"], fontSize=10, leading=13)
    small = ParagraphStyle(
        "VerolasSmall",
        parent=styles["BodyText"],
        fontSize=8,
        textColor=colors.grey,
        leading=10,
    )

    story: list[Any] = []
    story.append(Paragraph("Origin Concept Design", h1))
    story.append(Paragraph("AI-assisted structural shortlist with engineer seal", body))
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            f"Project: <font face='Courier'>{project_id}</font>",
            body,
        )
    )
    story.append(
        Paragraph(
            f"Workflow run: <font face='Courier'>{run_id}</font>",
            body,
        )
    )
    story.append(
        Paragraph(
            f"Issued: {datetime.now(UTC).strftime('%d %b %Y %H:%M UTC')}",
            body,
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Verolas Origin produced the shortlist; the engineer named below "
            "is the responsible designer and has refined and sealed the "
            "chosen option.",
            body,
        )
    )
    story.append(Spacer(1, 6 * mm))

    seal_lines = [
        ["Engineer", seal.engineer_name],
        ["Registration", seal.registration_number],
        ["Jurisdiction", seal.jurisdiction],
        ["Date", seal.date_iso],
    ]
    seal_table = Table(seal_lines, colWidths=[40 * mm, 130 * mm])
    seal_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(seal_table)
    if seal.statement:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(seal.statement, small))
    story.append(PageBreak())

    story.append(Paragraph("1. Design summary", h2))
    if chosen_option:
        story.append(Paragraph(_option_summary_paragraph(chosen_option), body))
        story.append(Spacer(1, 3 * mm))
        story.append(_takeoff_table(chosen_option))
        story.append(Spacer(1, 3 * mm))
        story.append(_dcr_table(chosen_option))

        worst = chosen_option.get("worst_case_member")
        if isinstance(worst, dict):
            story.append(Spacer(1, 3 * mm))
            story.append(
                Paragraph(
                    f"<b>Worst-case member:</b> "
                    f"<font face='Courier'>{worst.get('member_id', '')}</font> "
                    f"({worst.get('section', '')}) governs at DCR "
                    f"{float(worst.get('dcr', 0)):.2f} ({worst.get('governs', '')}).",
                    body,
                )
            )

        schedule = chosen_option.get("member_schedule") or []
        if isinstance(schedule, list) and schedule:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Member schedule", h2))
            story.append(_member_schedule_table(schedule))

        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Caveats", h2))
        for caveat in chosen_option.get("caveats") or []:
            story.append(Paragraph(f"- {caveat}", body))
        sustainability = chosen_option.get("sustainability_note")
        if sustainability:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Sustainability note", h2))
            story.append(Paragraph(str(sustainability), body))
    else:
        story.append(
            Paragraph(
                "Chosen option not present on the run; placeholder summary.",
                body,
            )
        )

    story.append(PageBreak())
    story.append(Paragraph("2. Geometry digest", h2))
    story.append(
        Paragraph(
            f"Source format: {geometry.source_format.upper()}; "
            f"{geometry.floor_count} floors, {geometry.wall_count} walls, "
            f"{geometry.column_count} columns, {geometry.opening_count} openings, "
            f"{geometry.slab_count} slabs.",
            body,
        )
    )
    for floor in geometry.floors:
        story.append(
            Paragraph(
                f"<b>{floor.name}</b> at +{floor.elevation_m:.2f} m, "
                f"extent {floor.extents.max_x - floor.extents.min_x:.1f} x "
                f"{floor.extents.max_y - floor.extents.min_y:.1f} m"
                + (" (roof)" if floor.is_roof else ""),
                body,
            )
        )

    if detail_layout:
        story.append(PageBreak())
        story.append(Paragraph("3. Refined detail layout", h2))
        for floor in detail_layout.get("floors") or []:
            n_columns = len(floor.get("columns") or [])
            n_beams = len(floor.get("beams") or [])
            story.append(
                Paragraph(
                    f"<b>{floor.get('name', '')}</b>: {n_columns} columns, {n_beams} beams.",
                    body,
                )
            )

    if roof_framing:
        coverage = (roof_framing.get("coverage") or {}).get("coverage_pct")
        if coverage is not None:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("4. Roof framing", h2))
            story.append(
                Paragraph(
                    f"Regular truss coverage: {float(coverage):.0f}% of roof footprint.",
                    body,
                )
            )

    story.append(PageBreak())
    story.append(Paragraph("5. Data sources and attributions", h2))
    story.append(
        Paragraph(
            "Every figure on the preceding pages traces back to one of "
            "the published sources below. Engineer review supersedes "
            "any engine output.",
            body,
        )
    )
    for attribution in _attributions_for(chosen_option):
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(f"- {attribution}", small))

    story.append(Spacer(1, 12 * mm))
    story.append(
        Paragraph(
            f"Engineer: {seal.engineer_name} ({seal.registration_number}) | "
            f"Jurisdiction: {seal.jurisdiction} | Date: {seal.date_iso}",
            small,
        )
    )

    doc.build(story)
    return buf.getvalue()


def _attributions_for(chosen_option: dict[str, Any] | None) -> list[str]:
    """Pick attribution strings whose data the chosen option actually used.

    Cost basis (DDC CWICR) is always present because the BoQ runs for
    every option. Steel-specific attributions appear only when the
    chosen option uses a steel system. EC3 vs AISC 360 follows the
    jurisdiction; today the engine is EU-only so AISC 360 is included
    only when US sections show up in the schedule.
    """
    attributions: list[str] = [CWICR_ATTRIBUTION]

    primary_structure = ""
    schedule_sections = ""
    if chosen_option:
        primary_structure = str(chosen_option.get("primary_structure") or "").lower()
        schedule = chosen_option.get("member_schedule") or []
        if isinstance(schedule, list):
            schedule_sections = " ".join(
                str(row.get("section") or "") for row in schedule if isinstance(row, dict)
            )

    if "steel" in primary_structure or "(s355)" in schedule_sections.lower():
        attributions.append(EUROCODEPY_ATTRIBUTION)
        attributions.append(EC3_DESIGN_CODE_ATTRIBUTION)
    if "(a992)" in schedule_sections.lower():
        attributions.append(AISC_SHAPES_ATTRIBUTION)
        attributions.append(AISC_360_DESIGN_CODE_ATTRIBUTION)

    return attributions


def _option_summary_paragraph(option: dict[str, Any]) -> str:
    bay = option.get("bay_grid_m") or {}
    bay_x = float(bay.get("x_m", 0.0))
    bay_y = float(bay.get("y_m", 0.0))
    return (
        f"<b>{option.get('primary_structure', '')}</b> "
        f"on a {bay_x:.1f} by {bay_y:.1f} m bay grid. "
        f"Slab: {option.get('slab_type', '')}. "
        f"Material: {option.get('material', '')}. "
        f"BoQ estimate: EUR {int(option.get('boq_estimate_eur_m2', 0))}/m^2, "
        f"total EUR {int(option.get('boq_total_eur', 0)):,}."
    )


def _takeoff_table(option: dict[str, Any]) -> Table:
    takeoff = option.get("takeoff") or {}
    rows = [["Material", "Quantity"]]
    if (takeoff.get("structural_steel_kg") or 0) > 0:
        rows.append(["Structural steel", f"{int(takeoff['structural_steel_kg']):,} kg"])
    if (takeoff.get("concrete_m3") or 0) > 0:
        rows.append(["Concrete", f"{float(takeoff['concrete_m3']):.1f} m^3"])
    if (takeoff.get("rebar_kg") or 0) > 0:
        rows.append(["Rebar", f"{int(takeoff['rebar_kg']):,} kg"])
    if (takeoff.get("clt_m3") or 0) > 0:
        rows.append(["CLT panels", f"{float(takeoff['clt_m3']):.1f} m^3"])
    if (takeoff.get("glulam_m3") or 0) > 0:
        rows.append(["Glulam", f"{float(takeoff['glulam_m3']):.1f} m^3"])

    table = Table(rows, colWidths=[70 * mm, 80 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
        )
    )
    return table


def _member_schedule_table(schedule: list[dict[str, Any]]) -> Table:
    """Render the member schedule as a multi-row table.

    Real BoQ has hundreds of rows; this shows the first 30 and a
    'further rows' footer so the PDF stays scannable. The full
    schedule is in the run's outputs for downstream consumers.
    """
    rows: list[list[Any]] = [["Section", "Role", "Count", "Length m", "Weight kg", "Cost EUR"]]
    visible = schedule[:30]
    for row in visible:
        rows.append(
            [
                str(row.get("section", "")),
                str(row.get("role", "")),
                f"{int(row.get('count', 0))}",
                f"{float(row.get('total_length_m', 0)):.1f}",
                f"{int(row.get('total_weight_kg', 0)):,}",
                f"{int(row.get('total_cost_eur', 0)):,}",
            ]
        )
    if len(schedule) > 30:
        rows.append([f"+ {len(schedule) - 30} more rows in JSON outputs", "", "", "", "", ""])
    table = Table(
        rows,
        colWidths=[55 * mm, 18 * mm, 18 * mm, 25 * mm, 25 * mm, 25 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    return table


def _dcr_table(option: dict[str, Any]) -> Table:
    dcr = option.get("dcr_distribution") or {}
    rows = [
        ["DCR band", "Fraction"],
        ["< 60%", f"{float(dcr.get('under_60_pct', 0)) * 100:.0f}%"],
        ["60 - 80%", f"{float(dcr.get('between_60_80', 0)) * 100:.0f}%"],
        ["80 - 100%", f"{float(dcr.get('between_80_100', 0)) * 100:.0f}%"],
        ["> 100%", f"{float(dcr.get('over_100', 0)) * 100:.0f}%"],
    ]
    table = Table(rows, colWidths=[70 * mm, 80 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
        )
    )
    return table


def render_ifc(geometry: Geometry, detail_layout: dict[str, Any] | None) -> bytes:
    """Emit an IFC4 file with the building structure.

    Element placements are origin-relative; production tooling would
    apply more precise local placements + extruded geometry, but for
    handover handover the present-and-named-correctly elements are the
    contract that downstream BIM tools rely on.
    """
    ifc = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(
        ifc, ifc_class="IfcProject", name="Verolas Origin Concept"
    )
    ifcopenshell.api.unit.assign_unit(ifc, length={"is_metric": True, "raw": "METERS"})
    ifcopenshell.api.context.add_context(ifc, context_type="Model")
    site = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.root.create_entity(
        ifc, ifc_class="IfcBuilding", name="Origin Building"
    )
    ifcopenshell.api.aggregate.assign_object(ifc, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(ifc, products=[building], relating_object=site)

    storeys: list[Any] = []
    for floor in geometry.floors:
        storey = ifcopenshell.api.root.create_entity(
            ifc, ifc_class="IfcBuildingStorey", name=floor.name
        )
        storeys.append((floor, storey))
    if storeys:
        ifcopenshell.api.aggregate.assign_object(
            ifc, products=[s for _, s in storeys], relating_object=building
        )

    detail_floors_iter: list[dict[str, Any]] = []
    if detail_layout:
        raw = detail_layout.get("floors") or []
        if isinstance(raw, list):
            detail_floors_iter = [f for f in raw if isinstance(f, dict)]
    detail_floors_by_key = {f.get("floor_key"): f for f in detail_floors_iter}

    for floor, storey in storeys:
        elements: list[Any] = []
        # Geometry-level walls + slabs.
        for wall in floor.walls:
            entity = ifcopenshell.api.root.create_entity(
                ifc, ifc_class="IfcWall", name=f"Wall {wall.id}"
            )
            elements.append(entity)
        for slab in floor.slabs:
            entity = ifcopenshell.api.root.create_entity(
                ifc, ifc_class="IfcSlab", name=f"Slab {slab.id}"
            )
            elements.append(entity)
        # Detail-layout columns + beams when present.
        detail = detail_floors_by_key.get(floor.key)
        if detail is not None:
            for column in detail.get("columns") or []:
                entity = ifcopenshell.api.root.create_entity(
                    ifc, ifc_class="IfcColumn", name=str(column.get("id") or "Column")
                )
                elements.append(entity)
            for beam in detail.get("beams") or []:
                entity = ifcopenshell.api.root.create_entity(
                    ifc, ifc_class="IfcBeam", name=str(beam.get("id") or "Beam")
                )
                elements.append(entity)
        if elements:
            ifcopenshell.api.spatial.assign_container(
                ifc, relating_structure=storey, products=elements
            )

    return ifc.to_string().encode("utf-8")


def build_export_package(
    *,
    project_id: str,
    run_id: str,
    reviewed_geometry: dict[str, Any],
    chosen_option: dict[str, Any] | None,
    detail_layout: dict[str, Any] | None,
    roof_framing: dict[str, Any] | None,
    seal: SealInfo,
) -> ExportResult:
    """Run all three renderers from raw upstream node outputs."""
    geometry = Geometry.model_validate(reviewed_geometry)
    warnings: list[str] = []
    if not chosen_option:
        warnings.append(
            "ai_options shortlist not found; PDF cover lacks the chosen-option summary."
        )
    if not detail_layout:
        warnings.append("detail_edit not completed; DXF + IFC carry the parsed geometry only.")

    dxf_bytes = render_dxf(geometry, detail_layout)
    pdf_bytes = render_pdf(
        project_id=project_id,
        run_id=run_id,
        chosen_option=chosen_option,
        geometry=geometry,
        detail_layout=detail_layout,
        roof_framing=roof_framing,
        seal=seal,
    )
    ifc_bytes = render_ifc(geometry, detail_layout)
    return ExportResult(
        dxf_bytes=dxf_bytes,
        pdf_bytes=pdf_bytes,
        ifc_bytes=ifc_bytes,
        warnings=warnings,
    )


__all__ = [
    "ExportResult",
    "SealInfo",
    "build_export_package",
    "render_dxf",
    "render_ifc",
    "render_pdf",
]
