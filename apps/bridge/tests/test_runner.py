"""Runner unit tests with mocked BridgeClient."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from verolas_bridge.runner import _dispatch
from verolas_bridge.tools import handler_for, register


@pytest.fixture(autouse=True)
def _clear_registry():  # type: ignore[no-untyped-def]
    """Each test starts with a clean tool registry."""
    from verolas_bridge.tools import _REGISTRY

    snapshot = dict(_REGISTRY)
    _REGISTRY.clear()
    yield
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)


@pytest.mark.asyncio
async def test_dispatch_fails_when_no_handler_registered() -> None:
    client = AsyncMock()
    job = {"id": "job-1", "class_id": "sofistik", "payload": {}}
    await _dispatch(client, job)
    client.submit_result.assert_awaited_once_with(
        "job-1",
        status="failed",
        error="Bridge has no handler for class_id=sofistik",
    )


@pytest.mark.asyncio
async def test_dispatch_runs_registered_handler() -> None:
    @register("rfem")
    async def fake_handler(payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "echo": payload}

    client = AsyncMock()
    job = {"id": "job-2", "class_id": "rfem", "payload": {"model": "bridge-1"}}
    await _dispatch(client, job)
    client.submit_result.assert_awaited_once_with(
        "job-2",
        status="completed",
        result={"ok": True, "echo": {"model": "bridge-1"}},
    )


@pytest.mark.asyncio
async def test_dispatch_failed_handler_reports_failure() -> None:
    @register("staad")
    async def boom(payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("license missing")

    client = AsyncMock()
    job = {"id": "job-3", "class_id": "staad", "payload": {}}
    await _dispatch(client, job)
    client.submit_result.assert_awaited_once_with(
        "job-3",
        status="failed",
        error="license missing",
    )


def test_handler_registration_returns_callable() -> None:
    @register("plaxis")
    async def fake(payload: dict[str, Any]) -> dict[str, Any]:
        return {}

    assert handler_for("plaxis") is fake
    assert handler_for("does-not-exist") is None
