"""Autodesk Platform Services adapter.

Covers AutoCAD, Revit, BIM 360, and Autodesk Construction Cloud via
the single APS OAuth app. The instance picker returns one option per
project under each hub the caller can read; the binding then resolves
to a `hub:<id>/project:<id>` ref that the sync engine can walk.

Token refresh uses the standard APS authentication/v2/token flow.
The same client id + secret env vars work across every Autodesk
product because APS sits in front of all of them.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from verolas_api.connector_instances import ConnectorInstanceOption, register

APS_TOKEN_URL = "https://developer.api.autodesk.com/authentication/v2/token"
APS_BASE = "https://developer.api.autodesk.com"
MAX_ROWS = 200


async def _ensure_fresh_token(credentials: dict[str, Any]) -> str:
    """Return a usable access token, refreshing via refresh_token if needed."""
    access = credentials.get("access_token")
    refresh = credentials.get("refresh_token")
    if isinstance(access, str) and access and not credentials.get("_force_refresh"):
        return access
    if not isinstance(refresh, str) or not refresh:
        raise RuntimeError("Autodesk installation has no refresh_token; reinstall the connector.")

    client_id = os.environ.get("AUTODESK_APS_CLIENT_ID")
    client_secret = os.environ.get("AUTODESK_APS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("AUTODESK_APS_CLIENT_ID / _SECRET are not configured.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            APS_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Autodesk refresh failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict) or "access_token" not in payload:
        raise RuntimeError("Autodesk refresh returned no access_token.")
    return str(payload["access_token"])


async def _aps_get(client: httpx.AsyncClient, path: str, token: str) -> dict[str, Any]:
    response = await client.get(
        f"{APS_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if response.status_code >= 400:
        raise RuntimeError(f"APS GET {path} failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"APS GET {path} returned non-object payload.")
    return payload


@register("autodesk-aps")
async def list_aps_projects(credentials: dict[str, Any]) -> list[ConnectorInstanceOption]:
    """Return one option per Autodesk project under each visible hub.

    APS returns hubs of three flavors:

    - `core:Team`        : an old A360 team. Often present, rarely used by firms.
    - `bim360:Account`   : a BIM 360 account.
    - `acc:Account`      : an ACC (Autodesk Construction Cloud) account.

    The format of `id` is consistent: a URN like `b.<uuid>`. Projects under
    the hub have the same shape. The bind picker stores `hub:<id>/project:<id>`
    so the sync engine knows both to walk the right hub.
    """
    token = await _ensure_fresh_token(credentials)
    options: list[ConnectorInstanceOption] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        hubs = await _aps_get(client, "/project/v1/hubs", token)
        for hub in (hubs.get("data") or [])[:MAX_ROWS]:
            if not isinstance(hub, dict):
                continue
            hub_id = hub.get("id")
            hub_name = (hub.get("attributes") or {}).get("name") or "Hub"
            hub_type = (hub.get("attributes") or {}).get("extension", {}).get("type", "")
            if not isinstance(hub_id, str):
                continue
            projects = await _aps_get(client, f"/project/v1/hubs/{hub_id}/projects", token)
            for project in (projects.get("data") or [])[:MAX_ROWS]:
                if not isinstance(project, dict):
                    continue
                project_id = project.get("id")
                project_name = (project.get("attributes") or {}).get("name") or "Project"
                if not isinstance(project_id, str):
                    continue
                options.append(
                    ConnectorInstanceOption(
                        ref=f"hub:{hub_id}/project:{project_id}",
                        label=f"{hub_name} / {project_name}",
                        hint=hub_type or None,
                    )
                )
                if len(options) >= MAX_ROWS:
                    return options
    return options


__all__ = ["list_aps_projects"]
