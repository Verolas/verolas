"""IDEA StatiCa adapter.

IDEA StatiCa exposes its model service through .NET assemblies.
This adapter loads the IdeaStatiCa.* assemblies via pythonnet on a
Windows bridge host with IDEA installed.
"""

from __future__ import annotations

from typing import Any

from verolas_bridge.tools import register
from verolas_bridge.tools._sdk import import_sdk

INSTALL_HINT = (
    "Install IDEA StatiCa on the bridge host (Windows) and "
    "`pip install pythonnet` so the Open Model API assemblies are reachable."
)


@register("idea-statica")
async def run_idea_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch an IDEA StatiCa job by action."""
    action = payload.get("action") or "ping"
    clr = import_sdk("clr", INSTALL_HINT)
    clr.AddReference("IdeaStatiCa.Plugin")

    plugin = __import__(
        "IdeaStatiCa.Plugin",
        fromlist=["ConnHiddenClientFactory"],
    )

    if action == "ping":
        factory = plugin.ConnHiddenClientFactory("")
        # The factory object loads the plugin assemblies; surfacing it
        # back as a string lets the cloud confirm the SDK booted.
        return {
            "action": "ping",
            "idea_factory": type(factory).__name__,
        }

    raise RuntimeError(f"IDEA StatiCa action '{action}' not implemented in this bridge build")


__all__ = ["run_idea_job"]
