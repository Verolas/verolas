"""DXF parser for Verolas Origin.

Reads an AutoCAD DXF using `ezdxf` and emits a normalized `Geometry`.

DXF organisation in the wild varies a lot. Our convention follows what
most architects produce when they export per-floor plans for structural
handover:

- Each paper-space layout corresponds to one floor. Layout names like
  "Floor 1", "1.OG", "Ground", "Top Roof" become Floor.name. If the
  file has only the model space (no layouts), we treat model space as
  a single floor named "Floor".
- Entities are categorised by layer name (case-insensitive substring):
  - layer contains "wall" or "wand" -> wall
  - layer contains "col", "column", "stuetze", "post" -> column
  - layer contains "door", "tur", "tuer" -> door opening
  - layer contains "window", "fenster" -> window opening
  - layer contains "slab", "decke", "floor" -> slab outline
  - layer contains "roof", "dach" -> sets is_roof on the parsed floor

Per-floor entity ids are deterministic: walls -> "wall_0", "wall_1"...
in iteration order. The first parse and any subsequent re-parse of the
same DXF produce diff-friendly outputs.

Unit handling: DXF stores units in $INSUNITS in the header. We convert
to metres. If $INSUNITS is missing/zero (unitless), we default to
millimetres which matches what most German + EU architects export.
"""

from __future__ import annotations

import io
import logging

import ezdxf
from ezdxf.document import Drawing

from verolas_api.workflow.origin.geometry import (
    Column,
    Extents,
    Floor,
    Geometry,
    Opening,
    OpeningKind,
    Point2D,
    Slab,
    Wall,
    WallKind,
)

logger = logging.getLogger(__name__)


# $INSUNITS code -> metres-per-unit factor.
# https://help.autodesk.com/view/OARX/2024/ENU/?guid=GUID-3F0380A5-1C15-464D-BC0B-EE4DD0DDBE48
_UNIT_TO_METRES: dict[int, float] = {
    0: 0.001,  # Unitless -> assume mm (most EU exports)
    1: 0.0254,  # Inches
    2: 0.3048,  # Feet
    4: 0.001,  # Millimetres
    5: 0.01,  # Centimetres
    6: 1.0,  # Metres
}


def parse_dxf(content: bytes) -> Geometry:
    """Parse a DXF document from raw bytes."""
    text = content.decode("utf-8", errors="replace")
    doc = ezdxf.read(io.StringIO(text))  # type: ignore[attr-defined]
    return _parse_drawing(doc)


def _parse_drawing(doc: Drawing) -> Geometry:
    scale = _scale_to_metres(doc)
    notes: list[str] = []

    layout_names = [name for name in doc.layouts.names() if name != "Model"]
    if not layout_names:
        notes.append("DXF has no paper-space layouts; treating model space as a single floor.")
        layout_names = ["Model"]

    floors: list[Floor] = []
    for index, name in enumerate(layout_names, start=1):
        layout = doc.layout(name)
        floor = _parse_layout(layout, layout_name=name, index=index, scale=scale)
        floors.append(floor)

    return Geometry(source_format="dxf", floors=floors, parser_notes=notes)


def _scale_to_metres(doc: Drawing) -> float:
    """Return the multiplier to convert DXF coordinates into metres."""
    code = int(doc.header.get("$INSUNITS", 0) or 0)
    return _UNIT_TO_METRES.get(code, 0.001)


def _parse_layout(layout: object, *, layout_name: str, index: int, scale: float) -> Floor:
    """Walk one layout and bucket entities into walls / columns / openings."""
    walls: list[Wall] = []
    openings: list[Opening] = []
    slabs: list[Slab] = []
    columns: list[Column] = []
    is_roof = "roof" in layout_name.lower() or "dach" in layout_name.lower()

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

    for entity in layout:  # type: ignore[attr-defined]
        layer_name = str(getattr(entity.dxf, "layer", "")).lower()
        category = _categorise_layer(layer_name)
        dxftype = entity.dxftype()

        if category in ("wall", "slab") and dxftype in ("LWPOLYLINE", "POLYLINE"):
            points = list(_iter_polyline_points(entity, scale))
            for p in points:
                track(p.x, p.y)
            if category == "slab" and len(points) >= 3:
                # Ensure the polygon closes.
                if points[0] != points[-1]:
                    points = [*points, points[0]]
                slabs.append(Slab(id=f"slab_{len(slabs)}", polygon=points))
            else:
                # A polyline contributes one wall per segment so the
                # downstream grid engine can reason about individual
                # straight segments instead of multi-vertex paths.
                for i in range(len(points) - 1):
                    walls.append(
                        Wall(
                            id=f"wall_{len(walls)}",
                            start=points[i],
                            end=points[i + 1],
                            kind=_wall_kind(layer_name),
                        )
                    )

        elif category == "wall" and dxftype == "LINE":
            start = _scaled_point(entity.dxf.start, scale)
            end = _scaled_point(entity.dxf.end, scale)
            track(start.x, start.y)
            track(end.x, end.y)
            walls.append(
                Wall(
                    id=f"wall_{len(walls)}",
                    start=start,
                    end=end,
                    kind=_wall_kind(layer_name),
                )
            )

        elif category == "column":
            center = _entity_center(entity, scale)
            if center is None:
                continue
            track(center.x, center.y)
            columns.append(Column(id=f"column_{len(columns)}", center=center, size_m=(0.30, 0.30)))

        elif category in ("door", "window"):
            center = _entity_center(entity, scale)
            if center is None:
                continue
            track(center.x, center.y)
            opening_kind: OpeningKind = "door" if category == "door" else "window"
            openings.append(
                Opening(
                    id=f"opening_{len(openings)}",
                    center=center,
                    width_m=0.90 if category == "door" else 1.20,
                    kind=opening_kind,
                )
            )

    if not walls and not slabs and not columns and not openings:
        # Nothing recognised on this layout; record an empty floor so
        # the engineer sees that the parser did not silently drop it.
        extents = Extents(min_x=0.0, min_y=0.0, max_x=0.0, max_y=0.0)
    else:
        extents = Extents(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

    return Floor(
        key=f"floor_{index}",
        name=layout_name,
        extents=extents,
        walls=walls,
        openings=openings,
        slabs=slabs,
        columns=columns,
        is_roof=is_roof,
    )


def _categorise_layer(layer: str) -> str:
    """Return 'wall', 'column', 'door', 'window', 'slab', or '' for ignored layers."""
    # Order matters: more specific keywords first.
    if "column" in layer or "stuetze" in layer or "stütze" in layer or "post" in layer:
        return "column"
    if "door" in layer or "tur" in layer or "tuer" in layer or "tür" in layer:
        return "door"
    if "window" in layer or "fenster" in layer:
        return "window"
    if "slab" in layer or "decke" in layer or "floor" in layer:
        return "slab"
    if "wall" in layer or "wand" in layer:
        return "wall"
    return ""


def _wall_kind(layer: str) -> WallKind:
    if "ext" in layer:
        return "exterior"
    if "int" in layer or "innen" in layer:
        return "interior"
    if "shear" in layer or "schub" in layer:
        return "shear"
    return "unknown"


def _iter_polyline_points(entity: object, scale: float) -> list[Point2D]:
    """Yield 2D points from an LWPOLYLINE or POLYLINE."""
    points: list[Point2D] = []
    if entity.dxftype() == "LWPOLYLINE":  # type: ignore[attr-defined]
        for vertex in entity.get_points("xy"):  # type: ignore[attr-defined]
            x, y = vertex[0], vertex[1]
            points.append(Point2D(x=x * scale, y=y * scale))
    else:  # POLYLINE (legacy)
        for vertex in entity.vertices:  # type: ignore[attr-defined]
            loc = vertex.dxf.location
            points.append(Point2D(x=loc[0] * scale, y=loc[1] * scale))
    return points


def _entity_center(entity: object, scale: float) -> Point2D | None:
    """Best-effort center extraction for an INSERT / CIRCLE / POINT."""
    dxftype = entity.dxftype()  # type: ignore[attr-defined]
    if dxftype == "INSERT":
        loc = entity.dxf.insert  # type: ignore[attr-defined]
        return Point2D(x=loc[0] * scale, y=loc[1] * scale)
    if dxftype == "POINT":
        loc = entity.dxf.location  # type: ignore[attr-defined]
        return Point2D(x=loc[0] * scale, y=loc[1] * scale)
    if dxftype == "CIRCLE":
        loc = entity.dxf.center  # type: ignore[attr-defined]
        return Point2D(x=loc[0] * scale, y=loc[1] * scale)
    return None


def _scaled_point(vec: object, scale: float) -> Point2D:
    return Point2D(x=vec[0] * scale, y=vec[1] * scale)  # type: ignore[index]
