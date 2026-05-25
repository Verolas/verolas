"""Dropbox adapter.

Lists top-level folders under the user's Dropbox root and any shared
team folders they have access to. Dropbox uses POST + JSON body for
its list endpoint rather than GET + query params, which is why this
adapter has its own `_dropbox_post` helper.

Dropbox issues refresh tokens only when `token_access_type=offline`
is sent on the authorize URL — that lives in the connector's OAuth
config under `extra_authorize_params`.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from verolas_api.connector_instances import ConnectorInstanceOption, register

DROPBOX_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
DROPBOX_API = "https://api.dropboxapi.com/2"
MAX_ROWS = 200


async def _ensure_fresh_token(credentials: dict[str, Any]) -> str:
    access = credentials.get("access_token")
    refresh = credentials.get("refresh_token")
    if isinstance(access, str) and access and not credentials.get("_force_refresh"):
        return access
    if not isinstance(refresh, str) or not refresh:
        raise RuntimeError("Dropbox installation has no refresh_token; reinstall the connector.")

    client_id = os.environ.get("DROPBOX_CLIENT_ID")
    client_secret = os.environ.get("DROPBOX_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("DROPBOX_CLIENT_ID / _SECRET are not configured.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            DROPBOX_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Dropbox refresh failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict) or "access_token" not in payload:
        raise RuntimeError("Dropbox refresh returned no access_token.")
    return str(payload["access_token"])


async def _dropbox_post(
    client: httpx.AsyncClient, path: str, token: str, body: dict[str, Any]
) -> dict[str, Any]:
    response = await client.post(
        f"{DROPBOX_API}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Dropbox POST {path} failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Dropbox POST {path} returned non-object payload.")
    return payload


@register("dropbox")
async def list_dropbox_folders(credentials: dict[str, Any]) -> list[ConnectorInstanceOption]:
    """Return top-level folders the user can read."""
    token = await _ensure_fresh_token(credentials)
    options: list[ConnectorInstanceOption] = [
        ConnectorInstanceOption(
            ref="folder:/",
            label="Dropbox root",
            hint="Top-level account",
        )
    ]
    cursor: str | None = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        while len(options) < MAX_ROWS:
            body: dict[str, Any] = (
                {"cursor": cursor} if cursor else {"path": "", "recursive": False, "limit": 100}
            )
            path = "/files/list_folder/continue" if cursor else "/files/list_folder"
            page = await _dropbox_post(client, path, token, body)
            for entry in page.get("entries") or []:
                if not isinstance(entry, dict) or entry.get(".tag") != "folder":
                    continue
                path_lower = entry.get("path_lower")
                name = entry.get("name") or "folder"
                if not isinstance(path_lower, str):
                    continue
                options.append(
                    ConnectorInstanceOption(
                        ref=f"folder:{path_lower}",
                        label=str(name),
                        hint=path_lower,
                    )
                )
                if len(options) >= MAX_ROWS:
                    break
            if not page.get("has_more"):
                break
            cursor = page.get("cursor")
            if not isinstance(cursor, str):
                break
    return options


__all__ = ["list_dropbox_folders"]
