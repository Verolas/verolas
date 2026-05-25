"""Quality checks for parsed CAD geometry.

Five checks modelled after Genia's CAD Upload Guide. Each returns a
status (`ok`, `warning`, `error`) plus a human-readable message that
the engineer sees in the architectural review step. Checks are
non-blocking by design: an `error` does not prevent the workflow from
proceeding, it just flags issues the engineer should address before
asking the AI to generate options.

The checks are deliberately heuristic. They favour false positives
(warn when unsure) over false negatives because the engineer is the
final reviewer; they need to know what the parser was unsure about.

References to Genia's checks:
1. Single-Plan      -> single_plan
2. Segmentation     -> segmentation
3. Alignment        -> alignment
4. Walls            -> walls_closed
5. Roof             -> roof_present
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from verolas_api.workflow.origin.geometry import Geometry

CheckName = Literal[
    "single_plan",
    "segmentation",
    "alignment",
    "walls_closed",
    "roof_present",
]
CheckStatus = Literal["ok", "warning", "error"]


class QualityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CheckName
    status: CheckStatus
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class QualityReport(BaseModel):
    """Aggregate quality report for one parsed `Geometry`."""

    model_config = ConfigDict(extra="forbid")

    checks: list[QualityCheck]

    @property
    def all_ok(self) -> bool:
        return all(c.status == "ok" for c in self.checks)

    @property
    def worst_status(self) -> CheckStatus:
        if any(c.status == "error" for c in self.checks):
            return "error"
        if any(c.status == "warning" for c in self.checks):
            return "warning"
        return "ok"


def run_all_checks(geometry: Geometry) -> QualityReport:
    """Run every check against a parsed geometry."""
    return QualityReport(
        checks=[
            _check_single_plan(geometry),
            _check_segmentation(geometry),
            _check_alignment(geometry),
            _check_walls_closed(geometry),
            _check_roof_present(geometry),
        ]
    )


def _check_single_plan(geometry: Geometry) -> QualityCheck:
    """Each floor should be its own logical container."""
    if geometry.floor_count == 0:
        return QualityCheck(
            name="single_plan",
            status="error",
            message="No floors parsed. The file may be empty or in an unsupported format.",
        )
    if geometry.floor_count == 1 and geometry.source_format == "dxf":
        # DXF with a single floor in Model space; warn so the engineer
        # knows the file may benefit from per-floor layouts.
        return QualityCheck(
            name="single_plan",
            status="warning",
            message=(
                "Only one floor found and it lives in Model space. "
                "Consider splitting each floor into its own paper-space "
                "layout for cleaner per-floor handover."
            ),
        )
    return QualityCheck(
        name="single_plan",
        status="ok",
        message=f"{geometry.floor_count} floors found, each in its own layout.",
    )


def _check_segmentation(geometry: Geometry) -> QualityCheck:
    """Detect floors that look like title blocks or detail sheets."""
    suspicious: list[str] = []
    for floor in geometry.floors:
        # A title block is usually under 5 m2 in real-world units; a
        # detail sheet can be enormous (whole drawing border = many
        # thousand m2). Both flag.
        if floor.extents.area_m2 < 5.0 and (floor.walls or floor.slabs):
            suspicious.append(f"{floor.name} (tiny: {floor.extents.area_m2:.1f} m^2)")
        elif floor.extents.area_m2 > 5000.0:
            suspicious.append(f"{floor.name} (huge: {floor.extents.area_m2:.0f} m^2)")
    if suspicious:
        return QualityCheck(
            name="segmentation",
            status="warning",
            message=(
                "Some floors look like title blocks or detail sheets rather "
                "than building plans: " + ", ".join(suspicious)
            ),
            details={"suspicious": suspicious},
        )
    return QualityCheck(
        name="segmentation",
        status="ok",
        message="No floors look like title blocks or detail sheets.",
    )


def _check_alignment(geometry: Geometry) -> QualityCheck:
    """Floor centroids should align vertically across storeys."""
    if geometry.floor_count < 2:
        return QualityCheck(
            name="alignment",
            status="ok",
            message="Single-floor file; alignment check skipped.",
        )

    centroids = [
        (
            (f.extents.min_x + f.extents.max_x) / 2.0,
            (f.extents.min_y + f.extents.max_y) / 2.0,
            f.name,
        )
        for f in geometry.floors
    ]
    cx0, cy0, _ = centroids[0]
    drifts: list[tuple[str, float]] = []
    for cx, cy, name in centroids[1:]:
        drift = math.hypot(cx - cx0, cy - cy0)
        if drift > 50.0:
            drifts.append((name, drift))

    if drifts:
        return QualityCheck(
            name="alignment",
            status="warning",
            message=(
                "Some floors are offset by more than 50 m from the first "
                "floor: " + ", ".join(f"{name} ({d:.1f} m)" for name, d in drifts)
            ),
            details={"drifts": [{"floor": n, "drift_m": d} for n, d in drifts]},
        )
    return QualityCheck(
        name="alignment",
        status="ok",
        message="All floors are aligned (centroids within 50 m of each other).",
    )


def _check_walls_closed(geometry: Geometry) -> QualityCheck:
    """At least 80% of wall endpoints should connect to another wall."""
    loose_total = 0
    endpoint_total = 0
    floors_with_loose: list[str] = []

    for floor in geometry.floors:
        if not floor.walls:
            continue
        endpoints: list[tuple[float, float]] = []
        for wall in floor.walls:
            endpoints.append((wall.start.x, wall.start.y))
            endpoints.append((wall.end.x, wall.end.y))
        endpoint_total += len(endpoints)
        loose_here = sum(
            1 for i, p in enumerate(endpoints) if not _has_neighbour(p, endpoints, exclude_index=i)
        )
        loose_total += loose_here
        if endpoints and loose_here / len(endpoints) > 0.2:
            floors_with_loose.append(floor.name)

    if endpoint_total == 0:
        return QualityCheck(
            name="walls_closed",
            status="ok",
            message="No walls found yet; nothing to check.",
        )

    loose_pct = 100.0 * loose_total / endpoint_total
    if floors_with_loose:
        return QualityCheck(
            name="walls_closed",
            status="warning",
            message=(
                f"{loose_pct:.0f}% of wall endpoints do not connect to "
                "another wall. Floors with the most gaps: " + ", ".join(floors_with_loose)
            ),
            details={
                "loose_pct": loose_pct,
                "floors_with_loose_walls": floors_with_loose,
            },
        )
    return QualityCheck(
        name="walls_closed",
        status="ok",
        message="Wall endpoints connect cleanly (under 20% loose ends per floor).",
    )


def _has_neighbour(
    point: tuple[float, float],
    others: list[tuple[float, float]],
    *,
    exclude_index: int,
    tolerance_m: float = 0.05,
) -> bool:
    for i, other in enumerate(others):
        if i == exclude_index:
            continue
        if math.hypot(other[0] - point[0], other[1] - point[1]) <= tolerance_m:
            return True
    return False


def _check_roof_present(geometry: Geometry) -> QualityCheck:
    """One floor should be marked as roof or named like one."""
    if not geometry.floors:
        return QualityCheck(
            name="roof_present",
            status="error",
            message="No floors parsed; cannot check for a roof.",
        )
    if any(f.is_roof for f in geometry.floors):
        return QualityCheck(
            name="roof_present",
            status="ok",
            message="Roof floor identified.",
        )
    return QualityCheck(
        name="roof_present",
        status="warning",
        message=(
            "No floor is marked as a roof. Rename the top layout/storey "
            "to include 'roof' or 'dach' so the structural concept "
            "generator knows where to lay roof framing."
        ),
    )
