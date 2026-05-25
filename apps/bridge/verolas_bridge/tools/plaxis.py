"""Plaxis adapter.

Plaxis 2D / 3D expose the Remote Scripting Server, accessed from
Python through `plxscripting.easy`. The server has to be enabled
manually inside the Plaxis Input application before the bridge can
talk to it.
"""

from __future__ import annotations

import os
from typing import Any

from verolas_bridge.tools import register
from verolas_bridge.tools._sdk import import_sdk

INSTALL_HINT = (
    "Install Plaxis on the bridge host (Windows) with the Remote "
    "Scripting Server enabled, then `pip install plxscripting`."
)


@register("plaxis")
async def run_plaxis_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a Plaxis job by action."""
    action = payload.get("action") or "ping"
    easy = import_sdk("plxscripting.easy", INSTALL_HINT)

    host = payload.get("host") or os.environ.get("VEROLAS_BRIDGE_PLAXIS_HOST", "localhost")
    port_raw = payload.get("port") or os.environ.get("VEROLAS_BRIDGE_PLAXIS_PORT", "10000")
    password = payload.get("password") or os.environ.get("VEROLAS_BRIDGE_PLAXIS_PASSWORD")
    if not password:
        raise RuntimeError(
            "Plaxis requires the scripting server password (set "
            "VEROLAS_BRIDGE_PLAXIS_PASSWORD on the bridge host)."
        )
    port = int(port_raw)
    s_i, _g_i = easy.new_server(host, port, password=password)

    if action == "ping":
        return {
            "action": "ping",
            "plaxis_version": getattr(s_i, "version", "unknown"),
            "host": host,
            "port": port,
        }

    raise RuntimeError(f"Plaxis action '{action}' not implemented in this bridge build")


__all__ = ["run_plaxis_job"]
