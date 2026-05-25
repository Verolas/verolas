"""Slack adapter.

Lists public and private channels in the workspace the org installed
against. Slack OAuth tokens are workspace-scoped; the `team` field on
the token response identifies which workspace this install covers.

Slack v2 OAuth supports rotating refresh tokens. We follow the standard
refresh flow against the same `/oauth.v2.access` endpoint.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from verolas_api.connector_instances import ConnectorInstanceOption, register

SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_BASE = "https://slack.com/api"
MAX_ROWS = 200


async def _ensure_fresh_token(credentials: dict[str, Any]) -> str:
    access = credentials.get("access_token")
    refresh = credentials.get("refresh_token")
    if isinstance(access, str) and access and not credentials.get("_force_refresh"):
        return access
    if not isinstance(refresh, str) or not refresh:
        raise RuntimeError("Slack installation has no refresh_token; reinstall the connector.")

    client_id = os.environ.get("SLACK_CLIENT_ID")
    client_secret = os.environ.get("SLACK_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("SLACK_CLIENT_ID / _SECRET are not configured.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            SLACK_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    payload: Any = response.json()
    if not isinstance(payload, dict) or not payload.get("ok") or "access_token" not in payload:
        raise RuntimeError(f"Slack refresh failed: {payload}")
    return str(payload["access_token"])


async def _slack_get(
    client: httpx.AsyncClient,
    path: str,
    token: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.get(
        f"{SLACK_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        params=params,
    )
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Slack GET {path} returned non-object payload.")
    if not payload.get("ok"):
        raise RuntimeError(f"Slack GET {path} failed: {payload.get('error')}")
    return payload


@register("slack")
async def list_slack_channels(credentials: dict[str, Any]) -> list[ConnectorInstanceOption]:
    """Return public + private channels the install has access to."""
    token = await _ensure_fresh_token(credentials)
    options: list[ConnectorInstanceOption] = []
    cursor: str | None = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        while len(options) < MAX_ROWS:
            params: dict[str, Any] = {
                "types": "public_channel,private_channel",
                "limit": 100,
                "exclude_archived": True,
            }
            if cursor:
                params["cursor"] = cursor
            page = await _slack_get(client, "/conversations.list", token, params=params)
            for channel in page.get("channels") or []:
                if not isinstance(channel, dict):
                    continue
                channel_id = channel.get("id")
                name = channel.get("name") or channel.get("name_normalized") or "channel"
                if not isinstance(channel_id, str):
                    continue
                options.append(
                    ConnectorInstanceOption(
                        ref=f"channel:{channel_id}",
                        label=f"#{name}",
                        hint="private" if channel.get("is_private") else "public",
                    )
                )
                if len(options) >= MAX_ROWS:
                    break
            cursor = (page.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
    return options


__all__ = ["list_slack_channels"]
