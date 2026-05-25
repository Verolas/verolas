"""Normalized building geometry produced by CAD parsers.

Every Origin parser (DXF, IFC, future formats) emits a `Geometry` value
of this shape. Downstream consumers (the SVG renderer in 6c.4, the
parametric grid engine in 6c.7, the AI options adapter, the 3D viewer)
read this same model. Keeping one normalized representation means each
adapter can be unit-tested without touching the raw CAD libraries.

Units: all distances are metres. Coordinates are in the floor's local
2D plane (x, y); elevation belongs to the `Floor` row, not to entities.
The parsers convert from the CAD file's native units to metres before
emitting.

Entity ids are stable per-floor. They are deterministic strings the
parser assigns ("wall_0", "wall_1", ...) so two consecutive parses of
the same file produce diff-friendly output. They are NOT meant to
survive across parses of a newly edited file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WallKind = Literal["exterior", "interior", "shear", "unknown"]
OpeningKind = Literal["door", "window", "opening"]
SourceFormat = Literal["dxf", "ifc"]


class Point2D(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float
    y: float


class Extents(BaseModel):
    """Axis-aligned bounding box of a floor or set of entities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width_m(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth_m(self) -> float:
        return self.max_y - self.min_y

    @property
    def area_m2(self) -> float:
        return max(0.0, self.width_m) * max(0.0, self.depth_m)


class Wall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    start: Point2D
    end: Point2D
    thickness_m: float = 0.20
    kind: WallKind = "unknown"

    @property
    def length_m(self) -> float:
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        return float((dx * dx + dy * dy) ** 0.5)


class Opening(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    # Wall this opening pierces. May be empty when the parser cannot
    # associate the opening with a specific wall; the architectural
    # review step lets the engineer re-anchor it.
    wall_id: str = ""
    center: Point2D
    width_m: float
    kind: OpeningKind = "opening"


class Slab(BaseModel):
    """A slab outline, used to draw the floor plate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    # Closed polygon vertices in 2D. The parser ensures the polygon is
    # closed (first == last); consumers should not assume CCW vs CW.
    polygon: list[Point2D] = Field(min_length=3)


class Column(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    center: Point2D
    # Plan footprint of the column. (width, depth) in metres; for round
    # columns the parser sets width == depth == diameter.
    size_m: tuple[float, float] = (0.30, 0.30)


class Floor(BaseModel):
    """One storey of the building."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str  # stable id, e.g. "floor_1"
    name: str  # display label, e.g. "Floor 1" or "Top Roof"
    elevation_m: float = 0.0
    extents: Extents
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    slabs: list[Slab] = Field(default_factory=list)
    columns: list[Column] = Field(default_factory=list)
    # True if this floor represents a roof rather than an occupied
    # storey. The quality checker uses this for the roof-present check.
    is_roof: bool = False


class Geometry(BaseModel):
    """Top-level container for a parsed CAD file."""

    model_config = ConfigDict(extra="forbid")

    source_format: SourceFormat
    floors: list[Floor]
    # Parser warnings the caller may surface to the engineer, e.g.
    # "no layer named 'wall' found; treated all LWPOLYLINE as walls".
    parser_notes: list[str] = Field(default_factory=list)

    @property
    def floor_count(self) -> int:
        return len(self.floors)

    @property
    def wall_count(self) -> int:
        return sum(len(f.walls) for f in self.floors)

    @property
    def opening_count(self) -> int:
        return sum(len(f.openings) for f in self.floors)

    @property
    def column_count(self) -> int:
        return sum(len(f.columns) for f in self.floors)

    @property
    def slab_count(self) -> int:
        return sum(len(f.slabs) for f in self.floors)
