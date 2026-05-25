"""Bentley ProjectWise adapter.

ProjectWise has a Web SDK that exposes datasource browsing + file
read/write over HTTPS. The endpoint URL and an integrated-auth
session token are firm-specific; the bridge reads them from env.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from verolas_bridge.tools import register


@register("bentley-projectwise")
async def run_projectwise_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a ProjectWise job by action."""
    action = payload.get("action") or "ping"
    endpoint = payload.get("endpoint") or os.environ.get("VEROLAS_BRIDGE_PROJECTWISE_URL")
    token = os.environ.get("VEROLAS_BRIDGE_PROJECTWISE_TOKEN")
    if not endpoint or not token:
        raise RuntimeError(
            "ProjectWise requires VEROLAS_BRIDGE_PROJECTWISE_URL and "
            "VEROLAS_BRIDGE_PROJECTWISE_TOKEN on the bridge host."
        )
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        if action == "ping":
            response = await client.get(f"{endpoint}/PWWSDK/api/info")
            response.raise_for_status()
            return {"action": "ping", "info": response.json()}
        raise RuntimeError(f"ProjectWise action '{action}' not implemented in this bridge build")


__all__ = ["run_projectwise_job"]
