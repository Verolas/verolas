"""Tests for the Verolas Origin AI Design adapter.

We do not call Anthropic in CI. Instead:
- Engine-only path: with no API key the adapter emits the deterministic
  grid-engine options for the reviewed geometry.
- Parse path: _parse_response handles plain + markdown-fenced JSON.
- Template structure: the ten-node Origin workflow still registers.
"""

from __future__ import annotations

import importlib
import sys
from uuid import uuid4

import pytest

from verolas_api.workflow.adapters import (
    clear_adapters_for_tests,
    get_adapter,
)
from verolas_api.workflow.adapters.base import AdapterContext
from verolas_api.workflow.origin.geometry import (
    Extents,
    Floor,
    Geometry,
    Point2D,
    Wall,
)
from verolas_api.workflow.registry import (
    clear_registry_for_tests,
    registered_templates,
)


def _ctx(settings: object | None = None) -> AdapterContext:
    return AdapterContext(
        org_id=uuid4(),
        project_id=uuid4(),
        run_id=uuid4(),
        node_id=uuid4(),
        node_key="ai_options",
        params={"tool": "verolas.origin.generator"},
        storage=None,
        settings=settings,  # type: ignore[arg-type]
    )


def _reload_origin_adapter() -> object:
    sys.modules.pop("verolas_api.workflow.adapters.origin_generator", None)
    clear_adapters_for_tests()
    importlib.import_module("verolas_api.workflow.adapters.origin_generator")
    adapter = get_adapter("verolas.origin.generator")
    assert adapter is not None
    return adapter


def _sample_reviewed_geometry() -> dict[str, object]:
    geometry = Geometry(
        source_format="dxf",
        floors=[
            Floor(
                key="floor_1",
                name="Floor 1",
                extents=Extents(min_x=0.0, min_y=0.0, max_x=20.0, max_y=15.0),
                walls=[
                    Wall(
                        id="w0",
                        start=Point2D(x=0.0, y=0.0),
                        end=Point2D(x=20.0, y=0.0),
                    ),
                ],
            ),
            Floor(
                key="floor_2",
                name="Roof",
                elevation_m=3.0,
                extents=Extents(min_x=0.0, min_y=0.0, max_x=20.0, max_y=15.0),
                is_roof=True,
            ),
        ],
    )
    return geometry.model_dump(mode="json")


@pytest.mark.asyncio
async def test_origin_engine_options_with_reviewed_geometry() -> None:
    """With no API key, emit the deterministic engine shortlist."""
    adapter = _reload_origin_adapter()

    class _FakeSettings:
        anthropic_api_key = None
        anthropic_model = "claude-sonnet-4-6"

    inputs = {
        "architectural_review": {"reviewed_geometry": _sample_reviewed_geometry()},
    }
    result = await adapter.run(_ctx(settings=_FakeSettings()), inputs=inputs)  # type: ignore[attr-defined]
    assert result.succeeded
    options = result.outputs["options"]
    assert isinstance(options, list)
    assert len(options) == 3
    variants = {o["variant"] for o in options}
    assert variants == {"optimized", "balanced", "conservative"}
    for option in options:
        assert "bay_grid_m" in option
        assert "takeoff" in option
        assert "dcr_distribution" in option
        assert "constructibility" in option
        # boq positive
        assert option["boq_estimate_eur_m2"] > 0
    assert result.outputs["model"] == "engine"


@pytest.mark.asyncio
async def test_origin_errors_without_any_geometry() -> None:
    adapter = _reload_origin_adapter()
    result = await adapter.run(_ctx(settings=None), inputs={})  # type: ignore[attr-defined]
    assert not result.succeeded
    assert "reviewed_geometry" in (result.error or "")


def test_origin_parse_plain_json() -> None:
    adapter = _reload_origin_adapter()
    raw = '{"options": [{"option_id": "rc-flat-slab", "summary": "..."}]}'
    options = adapter._parse_response(raw)  # type: ignore[attr-defined]
    assert len(options) == 1
    assert options[0]["option_id"] == "rc-flat-slab"


def test_origin_parse_markdown_fenced_json() -> None:
    adapter = _reload_origin_adapter()
    raw = '```json\n{"options": [{"option_id": "steel-mrf", "summary": "..."}]}\n```'
    options = adapter._parse_response(raw)  # type: ignore[attr-defined]
    assert len(options) == 1
    assert options[0]["option_id"] == "steel-mrf"


def test_origin_parse_rejects_non_list_options() -> None:
    adapter = _reload_origin_adapter()
    with pytest.raises(ValueError, match="'options' list"):
        adapter._parse_response('{"options": "not a list"}')  # type: ignore[attr-defined]


def test_origin_parse_rejects_polished_entry_missing_option_id() -> None:
    adapter = _reload_origin_adapter()
    with pytest.raises(ValueError, match="option_id"):
        adapter._parse_response('{"options": [{"summary": "no id"}]}')  # type: ignore[attr-defined]


def test_verolas_origin_template_structure() -> None:
    """The Origin template should register with 10 linear nodes in one group."""
    clear_registry_for_tests()
    sys.modules.pop("verolas_api.workflow.templates.verolas_origin", None)
    importlib.import_module("verolas_api.workflow.templates.verolas_origin")

    spec = next(t for t in registered_templates() if t.slug == "verolas-origin")
    assert len(spec.definition.nodes) == 10
    assert len(spec.definition.edges) == 9
    assert spec.definition.entry_keys == ["submit_brief"]

    keys_in_order = [
        "submit_brief",
        "upload_cad",
        "parameters",
        "floor_parse",
        "architectural_review",
        "roof_framing",
        "ai_options",
        "select_option",
        "detail_edit",
        "export_seal",
    ]
    for key in keys_in_order:
        assert any(n.key == key for n in spec.definition.nodes), f"missing node {key}"

    # The ai_options node names the adapter tool the generator uses.
    ai_node = next(n for n in spec.definition.nodes if n.key == "ai_options")
    assert ai_node.params.get("tool") == "verolas.origin.generator"

    # The floor_parse node names the parser adapter (built in 6c.3).
    parser = next(n for n in spec.definition.nodes if n.key == "floor_parse")
    assert parser.params.get("tool") == "verolas.origin.floor_parse"

    # All nodes belong to the single `origin` group.
    for node in spec.definition.nodes:
        assert node.group_key == "origin", f"{node.key} missing group_key"

    # The template declares the `origin` group with display metadata.
    assert len(spec.definition.groups) == 1
    origin_group = spec.definition.groups[0]
    assert origin_group.key == "origin"
    assert origin_group.name == "Verolas Origin"
    assert origin_group.collapsed_by_default is True

    # SLAs are numeric params, not in node names.
    submit = next(n for n in spec.definition.nodes if n.key == "submit_brief")
    assert submit.params.get("sla_minutes") == 15
    seal = next(n for n in spec.definition.nodes if n.key == "export_seal")
    assert seal.params.get("sla_business_days") == 5
