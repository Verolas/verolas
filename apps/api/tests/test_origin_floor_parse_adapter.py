"""Tests for the Verolas Origin floor_parse adapter.

We exercise the adapter against a fake storage that captures put_bytes
and replays get_bytes. The synthetic DXF the parser test already uses
is rebuilt here to keep tests independent.
"""

from __future__ import annotations

import io
import json
from typing import Any
from uuid import uuid4

import ezdxf
import pytest

from verolas_api.workflow.adapters import (
    clear_adapters_for_tests,
    get_adapter,
)
from verolas_api.workflow.adapters.base import AdapterContext


class _FakeStorage:
    """Minimal in-memory replacement for PresignedUrlService."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def get_bytes(self, *, key: str) -> bytes:
        if key not in self.store:
            raise FileNotFoundError(key)
        return self.store[key]

    def put_bytes(self, *, key: str, body: bytes, content_type: str | None = None) -> None:
        self.store[key] = body


def _ctx(storage: _FakeStorage | None) -> AdapterContext:
    return AdapterContext(
        org_id=uuid4(),
        project_id=uuid4(),
        run_id=uuid4(),
        node_id=uuid4(),
        node_key="floor_parse",
        params={"tool": "verolas.origin.floor_parse"},
        storage=storage,  # type: ignore[arg-type]
        settings=None,
    )


def _reload_adapter() -> Any:
    import importlib
    import sys

    sys.modules.pop("verolas_api.workflow.adapters.origin_floor_parse", None)
    clear_adapters_for_tests()
    importlib.import_module("verolas_api.workflow.adapters.origin_floor_parse")
    adapter = get_adapter("verolas.origin.floor_parse")
    assert adapter is not None
    return adapter


def _synthetic_dxf_bytes() -> bytes:
    doc = ezdxf.new(setup=True)  # type: ignore[attr-defined]
    doc.header["$INSUNITS"] = 4
    doc.layers.add("WALL")
    layout = doc.layouts.new("Floor 1")
    if "Layout1" in doc.layouts.names():
        doc.layouts.delete("Layout1")
    layout.add_lwpolyline(
        [(0, 0), (5000, 0), (5000, 4000), (0, 4000), (0, 0)],
        dxfattribs={"layer": "WALL"},
    )
    roof = doc.layouts.new("Roof")
    roof.add_lwpolyline(
        [(0, 0), (5000, 0), (5000, 4000), (0, 4000), (0, 0)],
        dxfattribs={"layer": "WALL"},
    )
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


@pytest.mark.asyncio
async def test_floor_parse_happy_path_writes_geometry_artifact() -> None:
    storage = _FakeStorage()
    cad_key = "uploads/test/floor.dxf"
    storage.store[cad_key] = _synthetic_dxf_bytes()
    adapter = _reload_adapter()
    result = await adapter.run(
        _ctx(storage=storage),
        inputs={"upload_cad": {"cad_file_key": cad_key, "cad_format": "dxf"}},
    )

    assert result.succeeded
    assert result.outputs["geometry_summary"]["floor_count"] == 2
    geometry_key = result.outputs["geometry_key"]
    assert geometry_key in storage.store

    # The stored JSON should parse back into the geometry shape.
    saved = json.loads(storage.store[geometry_key].decode("utf-8"))
    assert saved["source_format"] == "dxf"
    assert len(saved["floors"]) == 2

    # Quality report should be present and structurally complete.
    report = result.outputs["quality_report"]
    assert len(report["checks"]) == 5
    assert {c["name"] for c in report["checks"]} == {
        "single_plan",
        "segmentation",
        "alignment",
        "walls_closed",
        "roof_present",
    }

    # An artifact ref should describe the parsed-geometry JSON.
    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.storage_key == geometry_key
    assert artifact.content_type == "application/json"
    assert artifact.label == "Parsed geometry"


@pytest.mark.asyncio
async def test_floor_parse_errors_when_upload_missing() -> None:
    adapter = _reload_adapter()
    result = await adapter.run(_ctx(storage=_FakeStorage()), inputs={})
    assert not result.succeeded
    assert "did not emit a cad_file_key" in (result.error or "")


@pytest.mark.asyncio
async def test_floor_parse_errors_on_unsupported_format() -> None:
    adapter = _reload_adapter()
    storage = _FakeStorage()
    storage.store["uploads/foo.dwg"] = b"not really a dwg"
    result = await adapter.run(
        _ctx(storage=storage),
        inputs={"upload_cad": {"cad_file_key": "uploads/foo.dwg", "cad_format": "dwg"}},
    )
    assert not result.succeeded
    assert "dwg" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_floor_parse_errors_when_cad_bytes_invalid() -> None:
    adapter = _reload_adapter()
    storage = _FakeStorage()
    storage.store["uploads/broken.dxf"] = b"this is not a dxf file at all"
    result = await adapter.run(
        _ctx(storage=storage),
        inputs={"upload_cad": {"cad_file_key": "uploads/broken.dxf", "cad_format": "dxf"}},
    )
    assert not result.succeeded
    assert "parsing" in (result.error or "").lower() or "dxf" in (result.error or "").lower()
