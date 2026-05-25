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
from verolas_api.workflow.origin.geometry import Geometry
from verolas_api.workflow.origin.parse_dxf import parse_dxf
from verolas_api.workflow.origin.parse_ifc import parse_ifc
from verolas_api.workflow.origin.quality import QualityReport, run_all_checks

logger = logging.getLogger(__name__)

_JSON_CONTENT_TYPE = "application/json"


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

        geometry_json = geometry.model_dump_json()
        geometry_key = f"workflow-runs/{ctx.org_id}/{ctx.run_id}/origin/geometry.json"

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

        artifacts = (
            [
                ArtifactRef(
                    storage_key=geometry_key,
                    content_type=_JSON_CONTENT_TYPE,
                    size_bytes=len(geometry_json.encode("utf-8")),
                    label="Parsed geometry",
                )
            ]
            if ctx.storage is not None
            else []
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


register_adapter(OriginFloorParseAdapter())
