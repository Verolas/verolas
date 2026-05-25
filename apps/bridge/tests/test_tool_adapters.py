"""Unit tests for the bridge tool adapters.

We can't run the real vendor software in CI (no Windows host, no
licensed RFEM / SOFiSTiK / Tekla / etc.). Instead the tests verify:

- Every adapter registers itself with the dispatcher at bootstrap.
- The Dlubal RFEM adapter hits the Web Service correctly (httpx
  mocked with respx).
- Each Windows-only adapter reports a clean "SDK not installed"
  error when its vendor package cannot be imported.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
import respx

from verolas_bridge.tools import bootstrap_tools, handler_for
from verolas_bridge.tools._sdk import SDKNotAvailable, import_sdk
from verolas_bridge.tools.rfem import run_rfem_job


def test_bootstrap_registers_every_adapter() -> None:
    bootstrap_tools()
    for class_id in (
        "dlubal-rfem",
        "sofistik",
        "tekla",
        "csi-suite",
        "staad",
        "idea-statica",
        "plaxis",
        "bentley-projectwise",
        "rhino",
    ):
        assert handler_for(class_id) is not None, f"no handler for {class_id}"


@pytest.mark.asyncio
async def test_rfem_ping_returns_info() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("http://localhost:8081/api/v1/info").mock(
            return_value=httpx.Response(200, json={"version": "6.04", "license": "academic"})
        )
        result = await run_rfem_job({"action": "ping"})
    assert result == {
        "action": "ping",
        "rws_url": "http://localhost:8081",
        "rfem_info": {"version": "6.04", "license": "academic"},
    }


@pytest.mark.asyncio
async def test_rfem_ping_unreachable_returns_clean_error() -> None:
    with respx.mock() as router:
        router.get("http://localhost:8081/api/v1/info").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        with pytest.raises(RuntimeError, match="Dlubal RWS"):
            await run_rfem_job({"action": "ping"})


@pytest.mark.asyncio
async def test_rfem_unknown_action_raises() -> None:
    with pytest.raises(RuntimeError, match="not implemented"):
        await run_rfem_job({"action": "deduplicate_nodes"})


def test_import_sdk_returns_module_when_available() -> None:
    # `json` is in the stdlib so the import always succeeds.
    mod = import_sdk("json", "install hint")
    assert mod.dumps({"k": "v"}) == '{"k": "v"}'


def test_import_sdk_raises_when_missing() -> None:
    with pytest.raises(SDKNotAvailable, match="install hint"):
        import_sdk("definitely_not_a_real_vendor_sdk_xyz", "install hint")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "class_id",
    ["sofistik", "staad", "plaxis"],
)
async def test_sdk_adapters_surface_missing_sdk(class_id: str) -> None:
    """Adapters whose vendor SDK isn't on the host fail with a clear error."""
    bootstrap_tools()
    handler = handler_for(class_id)
    assert handler is not None
    payload: dict[str, Any] = {"action": "ping"}
    if class_id == "plaxis":
        payload["password"] = "x"

    with patch("verolas_bridge.tools._sdk.import_module", side_effect=ImportError("nope")):
        with pytest.raises(SDKNotAvailable):
            await handler(payload)


@pytest.mark.asyncio
async def test_rhino_ping_hits_compute() -> None:
    bootstrap_tools()
    handler = handler_for("rhino")
    assert handler is not None
    with respx.mock() as router:
        router.get("http://localhost:6500/version").mock(
            return_value=httpx.Response(200, text="8.0.0")
        )
        result = await handler({"action": "ping"})
    assert result["compute_version"] == "8.0.0"


@pytest.mark.asyncio
async def test_projectwise_requires_env_config() -> None:
    bootstrap_tools()
    handler = handler_for("bentley-projectwise")
    assert handler is not None
    with pytest.raises(RuntimeError, match="PROJECTWISE"):
        await handler({"action": "ping"})
