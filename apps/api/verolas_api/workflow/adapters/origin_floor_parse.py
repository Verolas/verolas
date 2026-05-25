"""Verolas Origin floor-parse adapter.

Tool key: `verolas.origin.floor_parse`. Used by the `floor_parse` node
in the Verolas Origin template. Reads the architect CAD file uploaded
in the previous step, dispatches the right parser by extension, runs
the quality checks, persists the normalized geometry as a JSON
artifact, and emits the storage key plus a summary on the node's
outputs.

The architectural-review step that follows consumes those outputs:

- `geometry_key`: storage key of the geometry JSON. The frontend uses
  this in 6c.4 to render per-floor SVG previews.
- `geometry_summary`: floor / wall / column / opening / slab counts.
- `quality_report`: the 5 check results so the engineer can see what
  the parser was unsure about.

When `ctx.storage` is None (unit tests, dev without S3), we skip the
upload but still return the in-memory geometry on outputs so callers
can introspect it.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from verolas_api.workflow.adapters import register_adapter
from verolas_api.workflow.adapters.base import (
    AdapterContext,
    AdapterResult,
    ArtifactRef,
    NodeAdapter,
)
from verolas_api.workflow.origin.geometry import Floor, Geometry
from verolas_api.workflow.origin.parse_dxf import parse_dxf
from verolas_api.workflow.origin.parse_ifc import parse_ifc
from verolas_api.workflow.origin.quality import QualityReport, run_all_checks
from verolas_api.workflow.origin.render_svg import render_floor_svg

logger = logging.getLogger(__name__)

_JSON_CONTENT_TYPE = "application/json"
_SVG_CONTENT_TYPE = "image/svg+xml"


class OriginFloorParseAdapter(NodeAdapter):
    tool = "verolas.origin.floor_parse"

    async def run(
        self,
        ctx: AdapterContext,
        inputs: dict[str, Any],
    ) -> AdapterResult:
        upload = inputs.get("upload_cad") or {}
        cad_key = upload.get("cad_file_key")
        cad_format = (upload.get("cad_format") or "").lower().lstrip(".")

        if not cad_key:
            return AdapterResult(
                outputs={},
                error=(
                    "upload_cad node did not emit a cad_file_key. "
                    "Re-upload the architect CAD before retrying."
                ),
            )

        if cad_format not in {"dxf", "ifc"}:
            return AdapterResult(
                outputs={},
                error=(
                    f"Unsupported cad_format {cad_format!r}. Floor-parse "
                    "currently accepts dxf or ifc; export DWG as DXF "
                    "from AutoCAD before uploading."
                ),
            )

        # Read source bytes.
        try:
            content = await self._read_source(ctx, cad_key)
        except FileNotFoundError as exc:
            return AdapterResult(
                outputs={},
                error=f"Could not read uploaded CAD at {cad_key!r}: {exc}",
            )
        except Exception as exc:
            logger.exception(
                "origin_floor_parse.read_error",
                extra={"run_id": str(ctx.run_id), "cad_key": cad_key},
            )
            return AdapterResult(
                outputs={},
                error=f"Reading uploaded CAD failed: {exc}",
            )

        # Parse off the event loop; ezdxf + ifcopenshell are sync.
        try:
            geometry = await asyncio.to_thread(_parse, content, cad_format)
        except Exception as exc:
            logger.exception(
                "origin_floor_parse.parse_error",
                extra={"run_id": str(ctx.run_id), "cad_format": cad_format},
            )
            return AdapterResult(
                outputs={},
                error=f"Parsing the {cad_format.upper()} file failed: {exc}",
            )

        report: QualityReport = await asyncio.to_thread(run_all_checks, geometry)

        # Render each floor to SVG up-front so the architectural-review
        # gallery has a durable image to display without re-running the
        # parser. We compute SVGs even when storage is None (tests) so
        # the in-memory result still surfaces them.
        svgs: list[tuple[Floor, str]] = await asyncio.to_thread(_render_all_svgs, geometry)

        geometry_json = geometry.model_dump_json()
        geometry_key = f"workflow-runs/{ctx.org_id}/{ctx.run_id}/origin/geometry.json"
        artifacts: list[ArtifactRef] = []
        floor_svgs_out: list[dict[str, Any]] = []

        if ctx.storage is not None:
            try:
                await asyncio.to_thread(
                    ctx.storage.put_bytes,
                    key=geometry_key,
                    body=geometry_json.encode("utf-8"),
                    content_type=_JSON_CONTENT_TYPE,
                )
            except Exception as exc:
                logger.exception(
                    "origin_floor_parse.upload_error",
                    extra={"run_id": str(ctx.run_id), "geometry_key": geometry_key},
                )
                return AdapterResult(
                    outputs={},
                    error=f"Storing parsed geometry failed: {exc}",
                )
            artifacts.append(
                ArtifactRef(
                    storage_key=geometry_key,
                    content_type=_JSON_CONTENT_TYPE,
                    size_bytes=len(geometry_json.encode("utf-8")),
                    label="Parsed geometry",
                )
            )

            for floor, svg in svgs:
                svg_key = f"workflow-runs/{ctx.org_id}/{ctx.run_id}/origin/floor_{floor.key}.svg"
                svg_bytes = svg.encode("utf-8")
                try:
                    await asyncio.to_thread(
                        ctx.storage.put_bytes,
                        key=svg_key,
                        body=svg_bytes,
                        content_type=_SVG_CONTENT_TYPE,
                    )
                except Exception as exc:
                    logger.exception(
                        "origin_floor_parse.svg_upload_error",
                        extra={"run_id": str(ctx.run_id), "svg_key": svg_key},
                    )
                    return AdapterResult(
                        outputs={},
                        error=f"Storing floor SVG failed: {exc}",
                    )
                artifacts.append(
                    ArtifactRef(
                        storage_key=svg_key,
                        content_type=_SVG_CONTENT_TYPE,
                        size_bytes=len(svg_bytes),
                        label=f"Floor: {floor.name}",
                    )
                )
                floor_svgs_out.append(
                    {
                        "floor_key": floor.key,
                        "name": floor.name,
                        "is_roof": floor.is_roof,
                        "svg_key": svg_key,
                        "size_bytes": len(svg_bytes),
                    }
                )
        else:
            # Storage off: still report the rendered SVGs inline so
            # tests and dev-without-S3 can introspect them.
            for floor, svg in svgs:
                floor_svgs_out.append(
                    {
                        "floor_key": floor.key,
                        "name": floor.name,
                        "is_roof": floor.is_roof,
                        "svg_key": "",
                        "svg_inline": svg,
                        "size_bytes": len(svg.encode("utf-8")),
                    }
                )

        return AdapterResult(
            outputs={
                "geometry_key": geometry_key if ctx.storage is not None else "",
                "geometry_summary": {
                    "source_format": geometry.source_format,
                    "floor_count": geometry.floor_count,
                    "wall_count": geometry.wall_count,
                    "opening_count": geometry.opening_count,
                    "column_count": geometry.column_count,
                    "slab_count": geometry.slab_count,
                    "floor_names": [f.name for f in geometry.floors],
                },
                "floor_svgs": floor_svgs_out,
                "quality_report": report.model_dump(),
                "parser_notes": list(geometry.parser_notes),
                "parsed_at": datetime.now(UTC).isoformat(),
            },
            artifacts=artifacts,
        )

    async def _read_source(self, ctx: AdapterContext, cad_key: str) -> bytes:
        """Read the source CAD bytes from storage. None storage -> error."""
        if ctx.storage is None:
            raise FileNotFoundError("storage service not configured")
        return await asyncio.to_thread(ctx.storage.get_bytes, key=cad_key)


def _parse(content: bytes, fmt: str) -> Geometry:
    if fmt == "dxf":
        return parse_dxf(content)
    if fmt == "ifc":
        return parse_ifc(content)
    raise ValueError(f"unsupported format: {fmt}")


def _render_all_svgs(geometry: Geometry) -> list[tuple[Floor, str]]:
    """Render every floor in `geometry` to SVG, preserving floor order."""
    return [(floor, render_floor_svg(floor)) for floor in geometry.floors]


register_adapter(OriginFloorParseAdapter())
