"""Google Workspace adapter.

Covers Google Drive (shared drives + folders), Google Sheets, and
Gmail behind one Cloud Console OAuth client. The user grants the
combined scope set on the Drive install; subsequent Sheets/Gmail
installs reuse the same refresh_token line (Google's consent dance
returns a refresh_token only when `access_type=offline` + a fresh
consent is forced — both already set in the OAuth config).

Per-class fetchers:

- `google-drive`: list "My Drive" plus every shared drive the
  caller can reach.
- `google-sheets`: list spreadsheets via Drive API filtered by
  mimeType. Sheets API itself has no list endpoint; everything
  lives in Drive.
- `gmail`: return the caller's mailbox as a single option (Gmail
  is one-mailbox-per-account; binding selects WHICH account to
  send from).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from verolas_api.connector_instances import ConnectorInstanceOption, register

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_BASE = "https://www.googleapis.com/drive/v3"
GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"
MAX_ROWS = 200


async def _ensure_fresh_token(credentials: dict[str, Any]) -> str:
    """Return a usable access token, refreshing via refresh_token if needed."""
    access = credentials.get("access_token")
    refresh = credentials.get("refresh_token")
    if isinstance(access, str) and access and not credentials.get("_force_refresh"):
        return access
    if not isinstance(refresh, str) or not refresh:
        raise RuntimeError("Google installation has no refresh_token; reinstall the connector.")

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID / _SECRET are not configured.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Google refresh failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict) or "access_token" not in payload:
        raise RuntimeError("Google refresh returned no access_token.")
    return str(payload["access_token"])


async def _api_get(
    client: httpx.AsyncClient, url: str, token: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = await client.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        params=params,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Google GET {url} failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Google GET {url} returned non-object payload.")
    return payload


async def _list_drive_items(
    client: httpx.AsyncClient,
    token: str,
    *,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """List files via Drive API. q filters by Drive query syntax."""
    items: list[dict[str, Any]] = []
    page_token: str | None = None
    while len(items) < MAX_ROWS:
        params: dict[str, Any] = {
            "fields": "nextPageToken,files(id,name,mimeType,webViewLink)",
            "pageSize": 100,
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        if q:
            params["q"] = q
        if page_token:
            params["pageToken"] = page_token
        page = await _api_get(client, f"{DRIVE_BASE}/files", token, params=params)
        for f in page.get("files") or []:
            if isinstance(f, dict):
                items.append(f)
        next_page = page.get("nextPageToken")
        if not isinstance(next_page, str):
            break
        page_token = next_page
    return items[:MAX_ROWS]


@register("google-drive")
async def list_google_drives(credentials: dict[str, Any]) -> list[ConnectorInstanceOption]:
    """List shared drives + a 'My Drive' marker."""
    token = await _ensure_fresh_token(credentials)
    options: list[ConnectorInstanceOption] = [
        ConnectorInstanceOption(
            ref="drive:my",
            label="My Drive",
            hint="Personal Drive root",
        )
    ]
    async with httpx.AsyncClient(timeout=30.0) as client:
        page = await _api_get(
            client,
            f"{DRIVE_BASE}/drives",
            token,
            params={"pageSize": 100},
        )
        for d in page.get("drives") or []:
            if not isinstance(d, dict):
                continue
            drive_id = d.get("id")
            name = d.get("name") or "Shared drive"
            if not isinstance(drive_id, str):
                continue
            options.append(
                ConnectorInstanceOption(
                    ref=f"drive:{drive_id}",
                    label=str(name),
                    hint="Shared drive",
                )
            )
            if len(options) >= MAX_ROWS:
                break
    return options


@register("google-sheets")
async def list_google_spreadsheets(
    credentials: dict[str, Any],
) -> list[ConnectorInstanceOption]:
    """List spreadsheets the user can access."""
    token = await _ensure_fresh_token(credentials)
    options: list[ConnectorInstanceOption] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        files = await _list_drive_items(
            client,
            token,
            q="mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
        )
    for f in files:
        sheet_id = f.get("id")
        name = f.get("name") or "Spreadsheet"
        if not isinstance(sheet_id, str):
            continue
        options.append(
            ConnectorInstanceOption(
                ref=f"spreadsheet:{sheet_id}",
                label=str(name),
                hint=f.get("webViewLink"),
            )
        )
    return options


@register("gmail")
async def list_gmail_mailbox(credentials: dict[str, Any]) -> list[ConnectorInstanceOption]:
    """Return the user's Gmail mailbox as the single bindable option."""
    token = await _ensure_fresh_token(credentials)
    async with httpx.AsyncClient(timeout=15.0) as client:
        profile = await _api_get(client, f"{GMAIL_BASE}/users/me/profile", token)
    address = profile.get("emailAddress")
    if not isinstance(address, str):
        return []
    return [
        ConnectorInstanceOption(
            ref=f"mailbox:{address}",
            label=address,
            hint="Gmail mailbox",
        )
    ]


__all__ = [
    "list_gmail_mailbox",
    "list_google_drives",
    "list_google_spreadsheets",
]
