"""Tekla Structures adapter.

Tekla exposes its .NET Open API via the `Tekla.Structures.Model`
assembly. From Python we reach it through `pythonnet`; both pieces
need to be on the bridge host, plus a licensed Tekla install.

Supported actions:

- `ping`             confirm the .NET assembly loads + a model is open
- `read_part_count`  return how many physical parts are in the open model
"""

from __future__ import annotations

from typing import Any

from verolas_bridge.tools import register
from verolas_bridge.tools._sdk import import_sdk

INSTALL_HINT = (
    "Install Tekla Structures on the bridge host (Windows) and run "
    "`pip install pythonnet` so .NET assemblies are reachable from Python."
)


def _bootstrap_clr() -> Any:
    clr = import_sdk("clr", INSTALL_HINT)
    clr.AddReference("Tekla.Structures.Model")
    return clr


@register("tekla")
async def run_tekla_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a Tekla job by action."""
    action = payload.get("action") or "ping"
    _bootstrap_clr()

    # Importing the .NET namespace returns a dynamic module; mypy can
    # therefore not type-check the calls below, hence the explicit
    # Any annotation on the import.
    from Tekla.Structures.Model import Model  # type: ignore[import-not-found]

    model = Model()
    if not model.GetConnectionStatus():
        raise RuntimeError("Cannot connect to a running Tekla Structures session on this host.")

    if action == "ping":
        info = model.GetInfo()
        return {
            "action": "ping",
            "model_name": getattr(info, "ModelName", "unknown"),
        }

    if action == "read_part_count":
        enumerator = model.GetModelObjectSelector().GetAllObjects()
        count = 0
        while enumerator.MoveNext():
            count += 1
        return {"action": "read_part_count", "parts": count}

    raise RuntimeError(f"Tekla action '{action}' not implemented in this bridge build")


__all__ = ["run_tekla_job"]
