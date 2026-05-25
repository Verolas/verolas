"""Rhino + Grasshopper adapter (via Rhino.Compute).

Rhino.Compute is a stateless HTTP server that exposes Rhino + Grasshopper
solvers. Operators run it next to a licensed Rhino install (Windows or a
managed Rhino.Compute Linux distribution) and point the bridge at it.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from verolas_bridge.tools import register


@register("rhino")
async def run_rhino_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a Rhino / Grasshopper job by action."""
    action = payload.get("action") or "ping"
    compute_url = (
        payload.get("compute_url")
        or os.environ.get("VEROLAS_BRIDGE_RHINO_COMPUTE_URL")
        or "http://localhost:6500"
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        if action == "ping":
            response = await client.get(f"{compute_url}/version")
            response.raise_for_status()
            return {
                "action": "ping",
                "compute_url": compute_url,
                "compute_version": response.text.strip(),
            }
        if action == "run_grasshopper":
            grasshopper_definition = payload.get("definition")
            inputs = payload.get("inputs") or {}
            if not isinstance(grasshopper_definition, str):
                raise RuntimeError("run_grasshopper requires a 'definition' (file URL or base64)")
            response = await client.post(
                f"{compute_url}/grasshopper",
                json={
                    "algo": grasshopper_definition,
                    "pointer": None,
                    "values": inputs,
                },
            )
            response.raise_for_status()
            return {"action": "run_grasshopper", "outputs": response.json()}
        raise RuntimeError(f"Rhino action '{action}' not implemented in this bridge build")


__all__ = ["run_rhino_job"]
