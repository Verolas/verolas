"""Unit tests for the Origin DXF + IFC parsers and quality checks.

We do not ship binary fixture files; instead we build a synthetic DXF
and a synthetic IFC programmatically using `ezdxf` and `ifcopenshell`
in the test setup. This keeps the repo small, isolates the tests from
any one architect's CAD style, and exercises the parsers against
geometry whose ground truth we know.
"""

from __future__ import annotations

import io
import math
import tempfile
from pathlib import Path

import ezdxf
import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit

from verolas_api.workflow.origin.parse_dxf import parse_dxf
from verolas_api.workflow.origin.parse_ifc import parse_ifc
from verolas_api.workflow.origin.quality import run_all_checks


def _build_synthetic_dxf() -> bytes:
    """Build a small DXF with two floors, walls, columns, openings."""
    doc = ezdxf.new(setup=True)
    # Tell the parser this file is in mm. Most real EU exports are mm.
    doc.header["$INSUNITS"] = 4  # mm

    # Make sure the wall + column + door + roof layers exist.
    doc.layers.add("WALL")
    doc.layers.add("COLUMN")
    doc.layers.add("DOOR")
    doc.layers.add("WINDOW")

    # Floor 1: rectangular outline, two columns, one door.
    floor1 = doc.layouts.new("Floor 1")
    # `setup=True` creates a default "Layout1"; remove it now that we
    # have at least one other paperspace layout (ezdxf refuses to
    # remove the last one).
    if "Layout1" in doc.layouts.names():
        doc.layouts.delete("Layout1")
    # Wall rectangle 10m x 6m (= 10000mm x 6000mm at scale)
    floor1.add_lwpolyline(
        [(0, 0), (10000, 0), (10000, 6000), (0, 6000), (0, 0)],
        dxfattribs={"layer": "WALL"},
    )
    # Two columns
    floor1.add_point((3000, 3000), dxfattribs={"layer": "COLUMN"})
    floor1.add_point((7000, 3000), dxfattribs={"layer": "COLUMN"})
    # Door on south wall
    floor1.add_point((5000, 0), dxfattribs={"layer": "DOOR"})

    # Top Roof: simpler outline.
    roof = doc.layouts.new("Top Roof")
    roof.add_lwpolyline(
        [(0, 0), (10000, 0), (10000, 6000), (0, 6000), (0, 0)],
        dxfattribs={"layer": "WALL"},
    )

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_dxf_parser_finds_floors_walls_columns_doors() -> None:
    geometry = parse_dxf(_build_synthetic_dxf())

    assert geometry.source_format == "dxf"
    assert geometry.floor_count == 2

    floor1 = next(f for f in geometry.floors if f.name == "Floor 1")
    # Closed rectangle -> 4 segments (the fifth point is the duplicate
    # closer, producing 4 unique walls).
    assert len(floor1.walls) == 4
    assert len(floor1.columns) == 2
    assert len(floor1.openings) == 1
    # The DXF was in mm; the parser scales to metres.
    assert floor1.extents.width_m == 10.0
    assert floor1.extents.depth_m == 6.0
    # All wall endpoints fall inside the 10x6 grid (in metres).
    for wall in floor1.walls:
        assert 0.0 <= wall.start.x <= 10.0
        assert 0.0 <= wall.end.x <= 10.0

    roof = next(f for f in geometry.floors if f.name == "Top Roof")
    assert roof.is_roof is True


def test_dxf_quality_report_passes_on_clean_geometry() -> None:
    geometry = parse_dxf(_build_synthetic_dxf())
    report = run_all_checks(geometry)
    statuses = {c.name: c.status for c in report.checks}

    # Multi-floor file in proper layouts, with a roof storey.
    assert statuses["single_plan"] == "ok"
    assert statuses["roof_present"] == "ok"
    # Closed rectangle perimeter -> walls connect cleanly.
    assert statuses["walls_closed"] == "ok"


def test_dxf_quality_warns_when_no_roof() -> None:
    doc = ezdxf.new(setup=True)
    doc.header["$INSUNITS"] = 4
    doc.layers.add("WALL")
    layout = doc.layouts.new("Floor 1")
    if "Layout1" in doc.layouts.names():
        doc.layouts.delete("Layout1")
    layout.add_lwpolyline(
        [(0, 0), (5000, 0), (5000, 5000), (0, 5000), (0, 0)],
        dxfattribs={"layer": "WALL"},
    )
    buf = io.StringIO()
    doc.write(buf)
    geometry = parse_dxf(buf.getvalue().encode("utf-8"))
    report = run_all_checks(geometry)
    statuses = {c.name: c.status for c in report.checks}
    assert statuses["roof_present"] == "warning"


def _build_synthetic_ifc() -> bytes:
    """Build a tiny IFC4 file with a project, building, two storeys, and a wall."""
    ifc = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject", name="Test")
    ifcopenshell.api.unit.assign_unit(ifc, length={"is_metric": True, "raw": "METERS"})
    context = ifcopenshell.api.context.add_context(ifc, context_type="Model")
    body_context = ifcopenshell.api.context.add_context(
        ifc,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )
    _ = body_context

    site = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.root.create_entity(
        ifc, ifc_class="IfcBuilding", name="Test Building"
    )
    storey1 = ifcopenshell.api.root.create_entity(
        ifc, ifc_class="IfcBuildingStorey", name="Floor 1"
    )
    storey2 = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcBuildingStorey", name="Roof")

    # Spatial hierarchy uses IfcRelAggregates (aggregate.assign_object)
    # for project -> site -> building -> storey, then
    # IfcRelContainedInSpatialStructure (spatial.assign_container) for
    # elements inside a storey.
    ifcopenshell.api.aggregate.assign_object(ifc, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(ifc, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(
        ifc, products=[storey1, storey2], relating_object=building
    )

    # Add a wall + column to floor 1.
    wall = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcWall", name="Wall A")
    column = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcColumn", name="Column A")
    ifcopenshell.api.spatial.assign_container(
        ifc, relating_structure=storey1, products=[wall, column]
    )

    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        ifc.write(str(tmp_path))
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


def test_ifc_parser_finds_two_storeys_with_elements() -> None:
    geometry = parse_ifc(_build_synthetic_ifc())

    assert geometry.source_format == "ifc"
    assert geometry.floor_count == 2

    storey_names = [f.name for f in geometry.floors]
    assert "Floor 1" in storey_names
    assert "Roof" in storey_names

    floor1 = next(f for f in geometry.floors if f.name == "Floor 1")
    # We added 1 wall + 1 column to Floor 1.
    assert len(floor1.walls) == 1
    assert len(floor1.columns) == 1

    # The wall used the placement default (length 3 m), so its length
    # should be near that without geometry-engine assistance.
    wall = floor1.walls[0]
    assert math.isclose(wall.length_m, 3.0, abs_tol=0.01)

    roof = next(f for f in geometry.floors if f.name == "Roof")
    assert roof.is_roof is True


def test_ifc_quality_report_runs() -> None:
    geometry = parse_ifc(_build_synthetic_ifc())
    report = run_all_checks(geometry)
    # Just confirm the report shape; specifics depend on heuristics.
    assert len(report.checks) == 5
    assert {c.name for c in report.checks} == {
        "single_plan",
        "segmentation",
        "alignment",
        "walls_closed",
        "roof_present",
    }
