"""Direct unit tests for the Origin quality-check module.

The parser-level tests exercise the happy path; these tests pin the
warning branches of segmentation, alignment, and walls_closed so a
refactor of the heuristic thresholds is caught immediately.
"""

from __future__ import annotations

from verolas_api.workflow.origin.geometry import (
    Extents,
    Floor,
    Geometry,
    Point2D,
    Wall,
)
from verolas_api.workflow.origin.quality import run_all_checks


def _floor(
    *,
    name: str,
    min_x: float = 0.0,
    min_y: float = 0.0,
    max_x: float = 10.0,
    max_y: float = 10.0,
    walls: list[Wall] | None = None,
    is_roof: bool = False,
) -> Floor:
    return Floor(
        key=name.lower().replace(" ", "_"),
        name=name,
        extents=Extents(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y),
        walls=walls or [],
        is_roof=is_roof,
    )


def _check(geometry: Geometry, name: str) -> object:
    report = run_all_checks(geometry)
    return next(c for c in report.checks if c.name == name)


def test_segmentation_warns_on_tiny_floor() -> None:
    geometry = Geometry(
        source_format="dxf",
        floors=[
            _floor(
                name="Title block",
                max_x=1.0,
                max_y=1.0,
                walls=[
                    Wall(
                        id="w0",
                        start=Point2D(x=0.0, y=0.0),
                        end=Point2D(x=1.0, y=0.0),
                    )
                ],
            ),
            _floor(name="Floor 1"),
            _floor(name="Roof", is_roof=True),
        ],
    )
    check = _check(geometry, "segmentation")
    assert check.status == "warning"  # type: ignore[attr-defined]
    assert "Title block" in check.message  # type: ignore[attr-defined]


def test_segmentation_warns_on_huge_floor() -> None:
    geometry = Geometry(
        source_format="dxf",
        floors=[
            _floor(
                name="Drawing border",
                max_x=200.0,
                max_y=200.0,  # 40,000 m^2 -> way over the 5,000 m^2 threshold
            ),
        ],
    )
    check = _check(geometry, "segmentation")
    assert check.status == "warning"  # type: ignore[attr-defined]


def test_alignment_warns_when_floors_drift_apart() -> None:
    geometry = Geometry(
        source_format="dxf",
        floors=[
            _floor(name="Floor 1"),
            _floor(name="Floor 2", min_x=200.0, max_x=210.0, min_y=200.0, max_y=210.0),
        ],
    )
    check = _check(geometry, "alignment")
    assert check.status == "warning"  # type: ignore[attr-defined]
    assert "Floor 2" in check.message  # type: ignore[attr-defined]


def test_alignment_ok_for_single_floor() -> None:
    geometry = Geometry(
        source_format="dxf",
        floors=[_floor(name="Floor 1")],
    )
    check = _check(geometry, "alignment")
    assert check.status == "ok"  # type: ignore[attr-defined]


def test_walls_closed_warns_on_loose_endpoints() -> None:
    # Two disconnected wall segments far apart => 100% loose ends.
    walls = [
        Wall(
            id="w0",
            start=Point2D(x=0.0, y=0.0),
            end=Point2D(x=2.0, y=0.0),
        ),
        Wall(
            id="w1",
            start=Point2D(x=5.0, y=5.0),
            end=Point2D(x=7.0, y=5.0),
        ),
    ]
    geometry = Geometry(
        source_format="dxf",
        floors=[_floor(name="Floor 1", walls=walls)],
    )
    check = _check(geometry, "walls_closed")
    assert check.status == "warning"  # type: ignore[attr-defined]
    assert "Floor 1" in check.message  # type: ignore[attr-defined]


def test_walls_closed_ok_for_closed_polygon() -> None:
    # Four walls forming a closed rectangle => every endpoint touches another.
    walls = [
        Wall(id="w0", start=Point2D(x=0.0, y=0.0), end=Point2D(x=4.0, y=0.0)),
        Wall(id="w1", start=Point2D(x=4.0, y=0.0), end=Point2D(x=4.0, y=3.0)),
        Wall(id="w2", start=Point2D(x=4.0, y=3.0), end=Point2D(x=0.0, y=3.0)),
        Wall(id="w3", start=Point2D(x=0.0, y=3.0), end=Point2D(x=0.0, y=0.0)),
    ]
    geometry = Geometry(
        source_format="dxf",
        floors=[_floor(name="Floor 1", walls=walls)],
    )
    check = _check(geometry, "walls_closed")
    assert check.status == "ok"  # type: ignore[attr-defined]


def test_single_plan_errors_on_empty_geometry() -> None:
    geometry = Geometry(source_format="dxf", floors=[])
    check = _check(geometry, "single_plan")
    assert check.status == "error"  # type: ignore[attr-defined]
