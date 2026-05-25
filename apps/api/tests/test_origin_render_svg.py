"""Unit tests for the server-side SVG renderer."""

from __future__ import annotations

import re

from verolas_api.workflow.origin.geometry import (
    Column,
    Extents,
    Floor,
    Opening,
    Point2D,
    Slab,
    Wall,
)
from verolas_api.workflow.origin.render_svg import render_floor_svg


def _floor() -> Floor:
    return Floor(
        key="floor_1",
        name="Floor 1",
        extents=Extents(min_x=0.0, min_y=0.0, max_x=10.0, max_y=6.0),
        walls=[
            Wall(id="w0", start=Point2D(x=0.0, y=0.0), end=Point2D(x=10.0, y=0.0)),
            Wall(id="w1", start=Point2D(x=10.0, y=0.0), end=Point2D(x=10.0, y=6.0)),
            Wall(id="w2", start=Point2D(x=10.0, y=6.0), end=Point2D(x=0.0, y=6.0)),
            Wall(id="w3", start=Point2D(x=0.0, y=6.0), end=Point2D(x=0.0, y=0.0)),
        ],
        openings=[
            Opening(id="op0", center=Point2D(x=5.0, y=0.0), width_m=0.9, kind="door"),
            Opening(id="op1", center=Point2D(x=2.5, y=6.0), width_m=1.2, kind="window"),
        ],
        slabs=[],
        columns=[Column(id="c0", center=Point2D(x=5.0, y=3.0), size_m=(0.30, 0.30))],
    )


def test_render_produces_valid_svg_envelope() -> None:
    svg = render_floor_svg(_floor())
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    # viewBox is set with padded extents (1.5 m padding each side ->
    # 13 m wide, 9 m tall).
    viewbox_match = re.search(r'viewBox="(-?\d+\.\d+) (-?\d+\.\d+) (\d+\.\d+) (\d+\.\d+)"', svg)
    assert viewbox_match is not None
    width_str = viewbox_match.group(3)
    height_str = viewbox_match.group(4)
    assert abs(float(width_str) - 13.0) < 0.01
    assert abs(float(height_str) - 9.0) < 0.01


def test_render_includes_one_line_per_wall() -> None:
    svg = render_floor_svg(_floor())
    assert svg.count("<line") == 4


def test_render_marks_columns_and_openings() -> None:
    svg = render_floor_svg(_floor())
    # Columns drawn as <rect>, openings as <circle>.
    assert svg.count("<rect") >= 1  # at least the column (one background rect also exists)
    assert svg.count("<circle") == 2  # one door, one window


def test_render_uses_distinct_colour_for_doors_and_windows() -> None:
    svg = render_floor_svg(_floor())
    # Door fill (red) and window fill (blue) must both appear.
    assert "#C0463E" in svg  # door
    assert "#3A6BBF" in svg  # window


def test_render_includes_floor_name_label() -> None:
    svg = render_floor_svg(_floor())
    assert "<text" in svg
    assert ">Floor 1</text>" in svg


def test_render_handles_slabs() -> None:
    floor = Floor(
        key="floor_2",
        name="Floor 2",
        extents=Extents(min_x=0.0, min_y=0.0, max_x=5.0, max_y=5.0),
        walls=[],
        openings=[],
        slabs=[
            Slab(
                id="s0",
                polygon=[
                    Point2D(x=0.0, y=0.0),
                    Point2D(x=5.0, y=0.0),
                    Point2D(x=5.0, y=5.0),
                    Point2D(x=0.0, y=5.0),
                    Point2D(x=0.0, y=0.0),
                ],
            )
        ],
        columns=[],
    )
    svg = render_floor_svg(floor)
    assert "<polygon" in svg


def test_render_y_flip_applied() -> None:
    """Ensure the renderer flips Y so plans display right-side up."""
    svg = render_floor_svg(_floor())
    # The Y-flip uses scale(1,-1) inside a wrapping <g> transform.
    assert "scale(1,-1)" in svg


def test_render_escapes_floor_name_xml_special_chars() -> None:
    floor = Floor(
        key="weird",
        name="A&B <Roof>",
        extents=Extents(min_x=0.0, min_y=0.0, max_x=2.0, max_y=2.0),
        walls=[],
        openings=[],
        slabs=[],
        columns=[],
    )
    svg = render_floor_svg(floor)
    assert "A&amp;B &lt;Roof&gt;" in svg
    assert "A&B <Roof>" not in svg  # original chars do not leak
