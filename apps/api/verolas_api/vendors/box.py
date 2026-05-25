"""Box adapter.

Lists top-level folders the install's user can read. Box numbers root
as folder id `0`; child folders + files appear under
`/folders/0/items`. We surface folders (`type=folder`) and let the
project bind a specific folder by id.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from verolas_api.connector_instances import ConnectorInstanceOption, register

BOX_TOKEN_URL = "https://api.box.com/oauth2/token"
BOX_BASE = "https://api.box.com/2.0"
MAX_ROWS = 200


async def _ensure_fresh_token(credentials: dict[str, Any]) -> str:
    access = credentials.get("access_token")
    refresh = credentials.get("refresh_token")
    if isinstance(access, str) and access and not credentials.get("_force_refresh"):
        return access
    if not isinstance(refresh, str) or not refresh:
        raise RuntimeError("Box installation has no refresh_token; reinstall the connector.")

    client_id = os.environ.get("BOX_CLIENT_ID")
    client_secret = os.environ.get("BOX_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("BOX_CLIENT_ID / _SECRET are not configured.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            BOX_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Box refresh failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict) or "access_token" not in payload:
        raise RuntimeError("Box refresh returned no access_token.")
    return str(payload["access_token"])


async def _box_get(
    client: httpx.AsyncClient,
    path: str,
    token: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.get(
        f"{BOX_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        params=params,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Box GET {path} failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Box GET {path} returned non-object payload.")
    return payload


@register("box")
async def list_box_folders(credentials: dict[str, Any]) -> list[ConnectorInstanceOption]:
    """Return top-level folders under the user's All Files (folder id `0`)."""
    token = await _ensure_fresh_token(credentials)
    options: list[ConnectorInstanceOption] = [
        ConnectorInstanceOption(
            ref="folder:0",
            label="All Files",
            hint="Box root",
        )
    ]
    offset = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        while len(options) < MAX_ROWS:
            page = await _box_get(
                client,
                "/folders/0/items",
                token,
                params={"fields": "id,type,name", "limit": 100, "offset": offset},
            )
            entries = page.get("entries") or []
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("type") != "folder":
                    continue
                folder_id = entry.get("id")
                name = entry.get("name") or "folder"
                if not isinstance(folder_id, str):
                    continue
                options.append(
                    ConnectorInstanceOption(
                        ref=f"folder:{folder_id}",
                        label=str(name),
                        hint="Box folder",
                    )
                )
                if len(options) >= MAX_ROWS:
                    break
            total = page.get("total_count")
            if not entries or (isinstance(total, int) and offset + len(entries) >= total):
                break
            offset += len(entries)
    return options


__all__ = ["list_box_folders"]
