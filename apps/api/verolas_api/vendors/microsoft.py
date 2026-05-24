"""Microsoft Graph adapter.

Covers SharePoint sites + document libraries, OneDrive drives, and
Teams teams + channels. All four use the same Microsoft client id /
secret (Microsoft Entra app registration), so the token refresh
helper is shared.

Each fetcher takes the decrypted installation credentials, refreshes
the access token if needed, hits Graph, and returns
`ConnectorInstanceOption` rows the project bind picker renders.

Pagination: Graph returns `@odata.nextLink` on long pages. We follow
the link until we have <= 200 rows, which is more than enough for
the picker. The full-resource sync workers in a later PR walk the
whole link chain.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from verolas_api.connector_instances import ConnectorInstanceOption, register

GRAPH_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
MAX_ROWS = 200


async def _ensure_fresh_token(credentials: dict[str, Any]) -> str:
    """Return a usable access token, refreshing via refresh_token if needed."""
    access = credentials.get("access_token")
    refresh = credentials.get("refresh_token")
    if isinstance(access, str) and access and not credentials.get("_force_refresh"):
        return access
    if not isinstance(refresh, str) or not refresh:
        raise RuntimeError("Microsoft installation has no refresh_token; reinstall the connector.")

    client_id = os.environ.get("MICROSOFT_GRAPH_CLIENT_ID")
    client_secret = os.environ.get("MICROSOFT_GRAPH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("MICROSOFT_GRAPH_CLIENT_ID / _SECRET are not configured.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            GRAPH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Microsoft refresh failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict) or "access_token" not in payload:
        raise RuntimeError("Microsoft refresh returned no access_token.")
    return str(payload["access_token"])


async def _graph_get(path: str, token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Graph GET {path} failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Graph GET {path} returned non-object payload.")
    return payload


async def _walk(path: str, token: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    next_path: str | None = path
    while next_path and len(rows) < MAX_ROWS:
        page = await _graph_get(next_path, token)
        values = page.get("value") or []
        if isinstance(values, list):
            for entry in values:
                if isinstance(entry, dict):
                    rows.append(entry)
        next_link = page.get("@odata.nextLink")
        if isinstance(next_link, str) and next_link.startswith(GRAPH_BASE):
            next_path = next_link[len(GRAPH_BASE) :]
        else:
            next_path = None
    return rows[:MAX_ROWS]


@register("ms-sharepoint")
async def list_sharepoint_libraries(
    credentials: dict[str, Any],
) -> list[ConnectorInstanceOption]:
    """Return SharePoint document libraries across the tenant's sites."""
    token = await _ensure_fresh_token(credentials)
    sites = await _walk("/sites?search=*", token)
    options: list[ConnectorInstanceOption] = []
    for site in sites:
        site_id = site.get("id")
        site_name = site.get("displayName") or site.get("name") or "Site"
        if not isinstance(site_id, str):
            continue
        drives = await _walk(f"/sites/{site_id}/drives", token)
        for drive in drives:
            drive_id = drive.get("id")
            drive_name = drive.get("name") or "Documents"
            if not isinstance(drive_id, str):
                continue
            options.append(
                ConnectorInstanceOption(
                    ref=f"site:{site_id}/drive:{drive_id}",
                    label=f"{site_name} / {drive_name}",
                    hint=drive.get("webUrl"),
                )
            )
            if len(options) >= MAX_ROWS:
                return options
    return options


@register("ms-onedrive")
async def list_onedrive_drives(
    credentials: dict[str, Any],
) -> list[ConnectorInstanceOption]:
    """Return the user's OneDrive root + any shared drives they can read."""
    token = await _ensure_fresh_token(credentials)
    me = await _graph_get("/me/drive", token)
    options: list[ConnectorInstanceOption] = []
    if isinstance(me, dict) and isinstance(me.get("id"), str):
        options.append(
            ConnectorInstanceOption(
                ref=f"drive:{me['id']}",
                label=str(me.get("name") or "My OneDrive"),
                hint=me.get("webUrl"),
            )
        )
    shared = await _walk("/me/drives", token)
    for drive in shared:
        drive_id = drive.get("id")
        if not isinstance(drive_id, str):
            continue
        options.append(
            ConnectorInstanceOption(
                ref=f"drive:{drive_id}",
                label=str(drive.get("name") or "Shared drive"),
                hint=drive.get("webUrl"),
            )
        )
    return options[:MAX_ROWS]


@register("ms-teams")
async def list_teams_channels(
    credentials: dict[str, Any],
) -> list[ConnectorInstanceOption]:
    """Return joined teams + their channels."""
    token = await _ensure_fresh_token(credentials)
    teams = await _walk("/me/joinedTeams", token)
    options: list[ConnectorInstanceOption] = []
    for team in teams:
        team_id = team.get("id")
        team_name = team.get("displayName") or "Team"
        if not isinstance(team_id, str):
            continue
        channels = await _walk(f"/teams/{team_id}/channels", token)
        for channel in channels:
            channel_id = channel.get("id")
            channel_name = channel.get("displayName") or "Channel"
            if not isinstance(channel_id, str):
                continue
            options.append(
                ConnectorInstanceOption(
                    ref=f"team:{team_id}/channel:{channel_id}",
                    label=f"{team_name} / {channel_name}",
                    hint=channel.get("webUrl"),
                )
            )
            if len(options) >= MAX_ROWS:
                return options
    return options


__all__ = [
    "list_onedrive_drives",
    "list_sharepoint_libraries",
    "list_teams_channels",
]
