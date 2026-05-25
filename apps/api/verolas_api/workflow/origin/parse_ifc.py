"""IFC parser for Verolas Origin.

Reads an IFC document using `ifcopenshell` and emits a normalized
`Geometry`. IFC is a much richer model than DXF: it has explicit
storeys, typed elements, and parametric geometry. Our job is to flatten
that into the same per-floor walls + openings + columns + slabs shape
the DXF parser produces, so downstream code never branches on source.

Scope for 6c.3 (MVP):
- Walk every `IfcBuildingStorey`. Each storey becomes one `Floor`.
- For elements directly contained in a storey, dispatch by IFC class:
  - `IfcWall`, `IfcWallStandardCase` -> wall
  - `IfcColumn` -> column
  - `IfcSlab`, `IfcSlabStandardCase` -> slab outline (bounding box for
    now; full polyline extraction is later work)
  - `IfcDoor` -> opening (kind="door")
  - `IfcWindow` -> opening (kind="window")
- Geometry extraction is placement-based, not geometry-engine based.
  We pull the local placement matrix to find the entity origin in
  world coordinates. For walls we get the axis curve if it is a
  straight `IfcPolyline` with two control points; otherwise we fall
  back to an anchor point with a default 3 m length pointing along
  the placement's X axis. The architectural_review step lets the
  engineer correct anything the heuristic missed.

Unit conversion: IFC files declare units in `IfcUnitAssignment`. We
read the length unit and convert everything to metres. If the file
omits the unit (rare but possible) we default to metres.
"""

from __future__ import annotations

import logging
import math
import tempfile
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.unit
import numpy as np

from verolas_api.workflow.origin.geometry import (
    Column,
    Extents,
    Floor,
    Geometry,
    Opening,
    Point2D,
    Slab,
    Wall,
)

logger = logging.getLogger(__name__)

# Some IFC exporters omit a representation we can read; in that case we
# place a placeholder wall with this length so the floor extent still
# contains the entity and the engineer can re-anchor in review.
_DEFAULT_WALL_LENGTH_M = 3.0


def parse_ifc(content: bytes) -> Geometry:
    """Parse an IFC document from raw bytes."""
    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        ifc = ifcopenshell.open(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    scale = _length_scale_to_metres(ifc)
    notes: list[str] = []

    storeys = ifc.by_type("IfcBuildingStorey")
    if not storeys:
        notes.append("IFC contains no IfcBuildingStorey; cannot segment per floor.")
        return Geometry(source_format="ifc", floors=[], parser_notes=notes)

    floors: list[Floor] = []
    for index, storey in enumerate(storeys, start=1):
        floors.append(_parse_storey(storey, index=index, scale=scale))

    return Geometry(source_format="ifc", floors=floors, parser_notes=notes)


def _length_scale_to_metres(ifc: object) -> float:
    try:
        return float(ifcopenshell.util.unit.calculate_unit_scale(ifc))  # type: ignore[arg-type]
    except Exception:
        # Newer/older API variants; fall back to a unit IFC.
        return 1.0


def _parse_storey(storey: object, *, index: int, scale: float) -> Floor:
    walls: list[Wall] = []
    openings: list[Opening] = []
    slabs: list[Slab] = []
    columns: list[Column] = []

    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    def track(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        if x < min_x:
            min_x = x
        if y < min_y:
            min_y = y
        if x > max_x:
            max_x = x
        if y > max_y:
            max_y = y

    # `get_contained` returns elements placed in the storey via
    # IfcRelContainedInSpatialStructure (walls, columns, slabs, ...).
    # `get_decomposition` would also pull aggregated children (which is
    # the storey -> building -> site tree direction, not what we want).
    elements = list(ifcopenshell.util.element.get_contained(storey))  # type: ignore[arg-type]
    for element in elements:
        ifc_class = element.is_a()
        if ifc_class in ("IfcWall", "IfcWallStandardCase"):
            anchor = _placement_xy(element, scale)
            if anchor is None:
                continue
            length, direction = _wall_axis(element, scale)
            end = Point2D(
                x=anchor.x + length * direction[0],
                y=anchor.y + length * direction[1],
            )
            track(anchor.x, anchor.y)
            track(end.x, end.y)
            walls.append(
                Wall(
                    id=f"wall_{len(walls)}",
                    start=anchor,
                    end=end,
                    kind="unknown",
                )
            )

        elif ifc_class == "IfcColumn":
            anchor = _placement_xy(element, scale)
            if anchor is None:
                continue
            track(anchor.x, anchor.y)
            columns.append(Column(id=f"column_{len(columns)}", center=anchor, size_m=(0.30, 0.30)))

        elif ifc_class in ("IfcSlab", "IfcSlabStandardCase"):
            anchor = _placement_xy(element, scale)
            if anchor is None:
                continue
            # MVP: emit a unit slab around the anchor so the engineer
            # sees the slab on the canvas. Real polyline extraction is
            # a later iteration once we know what we are missing in
            # real-world files.
            half = 1.0
            poly = [
                Point2D(x=anchor.x - half, y=anchor.y - half),
                Point2D(x=anchor.x + half, y=anchor.y - half),
                Point2D(x=anchor.x + half, y=anchor.y + half),
                Point2D(x=anchor.x - half, y=anchor.y + half),
                Point2D(x=anchor.x - half, y=anchor.y - half),
            ]
            for p in poly:
                track(p.x, p.y)
            slabs.append(Slab(id=f"slab_{len(slabs)}", polygon=poly))

        elif ifc_class == "IfcDoor":
            anchor = _placement_xy(element, scale)
            if anchor is None:
                continue
            track(anchor.x, anchor.y)
            openings.append(
                Opening(
                    id=f"opening_{len(openings)}",
                    center=anchor,
                    width_m=0.90,
                    kind="door",
                )
            )

        elif ifc_class == "IfcWindow":
            anchor = _placement_xy(element, scale)
            if anchor is None:
                continue
            track(anchor.x, anchor.y)
            openings.append(
                Opening(
                    id=f"opening_{len(openings)}",
                    center=anchor,
                    width_m=1.20,
                    kind="window",
                )
            )

    if min_x == float("inf"):
        extents = Extents(min_x=0.0, min_y=0.0, max_x=0.0, max_y=0.0)
    else:
        extents = Extents(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

    elevation_m = _storey_elevation(storey, scale)
    name = _storey_name(storey, index)
    is_roof = "roof" in name.lower() or "dach" in name.lower()

    return Floor(
        key=f"floor_{index}",
        name=name,
        elevation_m=elevation_m,
        extents=extents,
        walls=walls,
        openings=openings,
        slabs=slabs,
        columns=columns,
        is_roof=is_roof,
    )


def _placement_xy(element: object, scale: float) -> Point2D | None:
    """Return the (x, y) origin of an element's local placement, in metres.

    When the element has no `ObjectPlacement` (rare in real exports but
    common in programmatically built IFCs), we anchor the element at
    the origin so it still shows up. Returning None would silently
    drop the element from the parser output.
    """
    placement = getattr(element, "ObjectPlacement", None)
    if placement is None:
        return Point2D(x=0.0, y=0.0)
    try:
        matrix = ifcopenshell.util.placement.get_local_placement(placement)
    except Exception:
        return Point2D(x=0.0, y=0.0)
    return Point2D(x=float(matrix[0][3]) * scale, y=float(matrix[1][3]) * scale)


def _wall_axis(element: object, scale: float) -> tuple[float, tuple[float, float]]:
    """Return (length_m, (dir_x, dir_y)) for a wall's axis.

    Best effort: walk the wall's Representations looking for an Axis
    representation whose item is a two-point IfcPolyline. If found, use
    those two points to compute length + direction. Otherwise fall back
    to a default length aligned with the placement's local X axis.
    """
    representation = getattr(element, "Representation", None)
    if representation is not None:
        for shape in getattr(representation, "Representations", None) or []:
            if getattr(shape, "RepresentationIdentifier", None) != "Axis":
                continue
            for item in getattr(shape, "Items", None) or []:
                if item.is_a("IfcPolyline"):
                    points = list(item.Points)
                    if len(points) >= 2:
                        p0 = points[0].Coordinates
                        p1 = points[1].Coordinates
                        dx = (p1[0] - p0[0]) * scale
                        dy = (p1[1] - p0[1]) * scale
                        length = math.hypot(dx, dy)
                        if length > 0.0:
                            return length, (dx / length, dy / length)

    # Fall back: orient along placement local X.
    placement = getattr(element, "ObjectPlacement", None)
    if placement is not None:
        try:
            matrix = ifcopenshell.util.placement.get_local_placement(placement)
            axis = np.array([1.0, 0.0, 0.0, 0.0])
            world = matrix @ axis
            dx, dy = float(world[0]), float(world[1])
            mag = math.hypot(dx, dy)
            if mag > 0.0:
                return _DEFAULT_WALL_LENGTH_M, (dx / mag, dy / mag)
        except Exception:
            pass

    return _DEFAULT_WALL_LENGTH_M, (1.0, 0.0)


def _storey_elevation(storey: object, scale: float) -> float:
    elevation = getattr(storey, "Elevation", None)
    if elevation is None:
        return 0.0
    try:
        return float(elevation) * scale
    except Exception:
        return 0.0


def _storey_name(storey: object, index: int) -> str:
    name = getattr(storey, "Name", None) or getattr(storey, "LongName", None)
    if name:
        return str(name)
    return f"Floor {index}"
