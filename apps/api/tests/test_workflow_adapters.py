"""Unit tests for the workflow adapter framework and the Statik adapter."""

from __future__ import annotations

from uuid import uuid4

import pytest

from verolas_api.workflow.adapters import (
    clear_adapters_for_tests,
    get_adapter,
    register_adapter,
    registered_tools,
)
from verolas_api.workflow.adapters.base import (
    AdapterContext,
    AdapterResult,
    NodeAdapter,
)


def _ctx() -> AdapterContext:
    return AdapterContext(
        org_id=uuid4(),
        project_id=uuid4(),
        run_id=uuid4(),
        node_id=uuid4(),
        node_key="statik_compile",
        params={"tool": "verolas.statik_compile"},
        storage=None,
    )


class _DummyAdapter(NodeAdapter):
    tool = "test.dummy"

    async def run(
        self, ctx: AdapterContext, inputs: dict[str, object]
    ) -> AdapterResult:
        return AdapterResult(outputs={"ok": True, "input_count": len(inputs)})


def test_registry_register_and_lookup() -> None:
    clear_adapters_for_tests()
    adapter = _DummyAdapter()
    register_adapter(adapter)
    found = get_adapter("test.dummy")
    assert found is adapter
    assert "test.dummy" in registered_tools()


def test_registry_register_same_instance_idempotent() -> None:
    clear_adapters_for_tests()
    adapter = _DummyAdapter()
    register_adapter(adapter)
    register_adapter(adapter)
    assert registered_tools() == ["test.dummy"]


def test_registry_rejects_double_registration_of_different_instances() -> None:
    clear_adapters_for_tests()
    register_adapter(_DummyAdapter())
    with pytest.raises(RuntimeError, match="registered twice"):
        register_adapter(_DummyAdapter())


def test_registry_get_missing_returns_none() -> None:
    clear_adapters_for_tests()
    assert get_adapter("nope") is None


@pytest.mark.asyncio
async def test_dummy_adapter_runs_and_returns_outputs() -> None:
    clear_adapters_for_tests()
    adapter = _DummyAdapter()
    register_adapter(adapter)
    result = await adapter.run(_ctx(), inputs={"upstream": {"x": 1}})
    assert result.succeeded
    assert result.outputs == {"ok": True, "input_count": 1}


@pytest.mark.asyncio
async def test_statik_compile_adapter_produces_pdf() -> None:
    """The Statik adapter should produce a real PDF (magic bytes %PDF)
    and structured outputs even when storage is not configured."""
    import importlib
    import sys

    sys.modules.pop("verolas_api.workflow.adapters.statik_compile", None)
    clear_adapters_for_tests()
    importlib.import_module("verolas_api.workflow.adapters.statik_compile")

    adapter = get_adapter("verolas.statik_compile")
    assert adapter is not None

    ctx = _ctx()
    inputs = {
        "lastannahmen": {"dead_load": "5.0 kN/m2", "live_load": "3.0 kN/m2"},
        "schnittgroessen": {"max_moment_kNm": 120.5},
        "bemessung_decken": {"reinforcement": "Q257A top + bottom"},
    }
    result = await adapter.run(ctx, inputs)

    assert result.succeeded
    assert result.outputs["statik_storage_key"].endswith("/statik.pdf")
    assert result.outputs["statik_size_bytes"] > 1000
    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.content_type == "application/pdf"
    assert artifact.label == "Statik PDF"

    # Re-render and verify PDF magic bytes.
    pdf_bytes = adapter._render_pdf(ctx, inputs)  # type: ignore[attr-defined]
    assert pdf_bytes.startswith(b"%PDF-")
    assert b"%%EOF" in pdf_bytes[-20:]
