"""Server-side SVG renderer for parsed floors.

Turns a `Floor` from the normalized geometry into a self-contained SVG
string. We render server-side so the same image the AI saw on
generation can be replayed later from the run's artifact store, even
if the renderer is rewritten. The frontend may also re-render
geometry interactively (zoom, layer toggles, member edits) in later
sub-stages; the server-side SVG is the durable record.

Conventions:
- Distances in metres. SVG units = 1 metre by default; the viewBox is
  computed from the floor extents with padding so the image is
  self-scaling at any display size.
- Y axis is flipped so positive Y points up, matching engineering and
  CAD convention. Without the flip, plans render upside-down.
- All visual constants live as `_STYLE` so a designer can tune them
  without changing logic.

Output is plain SVG 1.1 (no JS, no external CSS) so it can be embedded
in an `<img>` tag, downloaded directly, or rasterised later. Tests
snapshot the string structure rather than pixel output.
"""

from __future__ import annotations

from typing import Final

from verolas_api.workflow.origin.geometry import Floor

_PADDING_M: Final[float] = 1.5
_WALL_STROKE_M: Final[float] = 0.2
_COLUMN_SIZE_M: Final[float] = 0.35

_STYLE: Final[dict[str, str]] = {
    "background_fill": "#FAFAF7",
    "slab_fill": "#E8E6DE",
    "wall_stroke": "#1F1F1B",
    "column_fill": "#1F1F1B",
    "door_fill": "#C0463E",
    "window_fill": "#3A6BBF",
    "label_color": "#5C5C58",
    "border_stroke": "#CECEC2",
}


def render_floor_svg(floor: Floor) -> str:
    """Return a complete SVG document for a single floor."""
    width_m, height_m, view_min_x, view_min_y = _viewbox(floor)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{view_min_x:.3f} {view_min_y:.3f} {width_m:.3f} {height_m:.3f}" '
        f'preserveAspectRatio="xMidYMid meet">'
    )
    parts.append(
        f'<rect x="{view_min_x:.3f}" y="{view_min_y:.3f}" '
        f'width="{width_m:.3f}" height="{height_m:.3f}" '
        f'fill="{_STYLE["background_fill"]}" stroke="{_STYLE["border_stroke"]}" '
        f'stroke-width="0.05"/>'
    )

    # Apply a Y-flip transform so model-space +y points "up" in the
    # rendered SVG (SVG's default is +y down).
    parts.append(
        f'<g transform="translate(0,{(view_min_y + view_min_y + height_m):.3f}) scale(1,-1)">'
    )

    # Layer order: slabs (back), walls, columns, openings (front).
    for slab in floor.slabs:
        points = " ".join(f"{p.x:.3f},{p.y:.3f}" for p in slab.polygon)
        parts.append(f'<polygon points="{points}" fill="{_STYLE["slab_fill"]}" stroke="none"/>')

    for wall in floor.walls:
        parts.append(
            f'<line x1="{wall.start.x:.3f}" y1="{wall.start.y:.3f}" '
            f'x2="{wall.end.x:.3f}" y2="{wall.end.y:.3f}" '
            f'stroke="{_STYLE["wall_stroke"]}" '
            f'stroke-width="{_WALL_STROKE_M:.3f}" stroke-linecap="square"/>'
        )

    for column in floor.columns:
        half_w = column.size_m[0] / 2.0 if column.size_m[0] > 0 else _COLUMN_SIZE_M / 2.0
        half_d = column.size_m[1] / 2.0 if column.size_m[1] > 0 else _COLUMN_SIZE_M / 2.0
        parts.append(
            f'<rect x="{column.center.x - half_w:.3f}" '
            f'y="{column.center.y - half_d:.3f}" '
            f'width="{half_w * 2:.3f}" height="{half_d * 2:.3f}" '
            f'fill="{_STYLE["column_fill"]}"/>'
        )

    for opening in floor.openings:
        fill = _STYLE["door_fill"] if opening.kind == "door" else _STYLE["window_fill"]
        r = max(opening.width_m / 2.0, 0.15)
        parts.append(
            f'<circle cx="{opening.center.x:.3f}" cy="{opening.center.y:.3f}" '
            f'r="{r:.3f}" fill="{fill}" fill-opacity="0.75"/>'
        )

    parts.append("</g>")

    # Floor-name label, rendered in SVG (not flipped) so the text is
    # right-side up regardless of the model orientation.
    label_x = view_min_x + 0.4
    label_y = view_min_y + 0.9
    # Use a font-size that scales with the viewBox to stay legible.
    font_size = max(0.4, min(1.0, width_m / 30.0))
    parts.append(
        f'<text x="{label_x:.3f}" y="{label_y:.3f}" '
        f'font-family="Inter, system-ui, sans-serif" '
        f'font-size="{font_size:.3f}" font-weight="500" '
        f'fill="{_STYLE["label_color"]}">{_escape(floor.name)}</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


def _viewbox(floor: Floor) -> tuple[float, float, float, float]:
    """Compute (width, height, min_x, min_y) for the SVG viewBox."""
    ex = floor.extents
    width = max(ex.width_m, 1.0) + 2 * _PADDING_M
    height = max(ex.depth_m, 1.0) + 2 * _PADDING_M
    return width, height, ex.min_x - _PADDING_M, ex.min_y - _PADDING_M


def _escape(text: str) -> str:
    """Minimal XML escape; floor names are user-controlled strings."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
