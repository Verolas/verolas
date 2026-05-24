"""Connector OAuth flow + per-class instance picker.

Three endpoints:

- `POST /v1/orgs/{slug}/connectors/oauth/start`
  Authenticated. Body: {class_id, redirect_after}. Mints a state token
  + PKCE verifier, persists them, returns the vendor authorize URL the
  browser should navigate to.

- `GET  /v1/connectors/oauth/callback?state=...&code=...`
  Unauthenticated by Bearer (the browser is mid-redirect with no
  session). The state value is the security boundary. Exchanges the
  code for tokens at the vendor, encrypts the result, upserts the
  installation, and redirects the browser back to `redirect_after`.

- `GET  /v1/orgs/{slug}/connectors/{class_id}/instances`
  Returns the list of instance options the project bind picker shows
  (SharePoint libraries, Slack channels, ACC hubs, ...). Dispatches to
  the per-class fetcher registry; classes with no registered fetcher
  return an empty list and the UI falls back to free-form input.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Path, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from verolas_api.audit import record_activity
from verolas_api.connector_instances import fetcher_for
from verolas_api.connector_oauth import oauth_config
from verolas_api.connectors import lookup
from verolas_api.crypto import decrypt_credentials, encrypt_credentials
from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.bootstrap import BootstrapConn
from verolas_api.dependencies.org import DbOrgConn
from verolas_api.middleware import sla_tier

oauth_router = APIRouter(prefix="/orgs/{org_slug}/connectors/oauth", tags=["connectors"])

# Sits at the catalog prefix because the browser callback is unauthenticated
# and does not carry an org slug in the URL (it comes back from a vendor).
callback_router = APIRouter(prefix="/connectors/oauth", tags=["connectors"])

instance_router = APIRouter(prefix="/orgs/{org_slug}/connectors", tags=["connectors"])

STATE_TTL = timedelta(minutes=10)


class OAuthStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_id: str = Field(min_length=1, max_length=80)
    redirect_after: str | None = Field(default=None, max_length=400)


class OAuthStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorize_url: str
    state: str


class InstanceOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str
    label: str
    hint: str | None = None


@oauth_router.post(
    "/start",
    response_model=OAuthStartResponse,
)
@sla_tier(2)
async def oauth_start(
    body: OAuthStartRequest,
    dep: DbOrgConn,
    auth: CurrentAuth,
    request: Request,
) -> OAuthStartResponse:
    """Begin an OAuth 2 PKCE dance for the given connector class."""
    _ = auth
    spec = lookup(body.class_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connector class '{body.class_id}'.",
        )
    if spec.auth_method != "oauth2_pkce":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{spec.name}' does not use OAuth 2; install via POST /installations.",
        )
    cfg = oauth_config(body.class_id)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"OAuth not configured for '{body.class_id}'.",
        )

    client_id = os.environ.get(cfg.client_id_env)
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vendor app not registered (set {cfg.client_id_env}).",
        )

    conn, ctx = dep
    state = secrets.token_urlsafe(32)
    pkce_verifier = secrets.token_urlsafe(64)
    pkce_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(pkce_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    expires_at = datetime.now(tz=UTC) + STATE_TTL

    await conn.execute(
        """
        INSERT INTO connector_oauth_state (
            state, org_id, user_id, class_id, pkce_verifier, redirect_after, expires_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            state,
            ctx.organization_id,
            ctx.user_id,
            spec.id,
            pkce_verifier,
            body.redirect_after,
            expires_at,
        ),
    )

    redirect_uri = _callback_url(request)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": " ".join(spec.scopes),
        "code_challenge": pkce_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    return OAuthStartResponse(
        authorize_url=f"{cfg.authorize_url}?{urlencode(params)}",
        state=state,
    )


@callback_router.get("/callback")
@sla_tier(2)
async def oauth_callback(
    conn: BootstrapConn,
    request: Request,
    state: str,
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Vendor returns the user here. Exchange code for tokens, upsert install."""
    cur = await conn.execute(
        """
        DELETE FROM connector_oauth_state
        WHERE state = %s
        RETURNING org_id, user_id, class_id, pkce_verifier, redirect_after, expires_at
        """,
        (state,),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown or expired state token.",
        )
    org_id, user_id, class_id, pkce_verifier, redirect_after, expires_at = row
    if expires_at < datetime.now(tz=UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token expired; restart the install.",
        )
    if error:
        return _redirect_back(redirect_after, f"oauth_error={error}")
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vendor returned neither `code` nor `error`.",
        )

    spec = lookup(class_id)
    cfg = oauth_config(class_id)
    if spec is None or cfg is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Connector class disappeared between start and callback.",
        )
    client_id = os.environ.get(cfg.client_id_env)
    client_secret = os.environ.get(cfg.client_secret_env)
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vendor app credentials missing on the server.",
        )

    token_payload = await _exchange_code(
        cfg.token_url,
        client_id,
        client_secret,
        code,
        pkce_verifier,
        _callback_url(request),
    )

    encrypted = encrypt_credentials(token_payload)
    oauth_account = {
        "scope": token_payload.get("scope"),
        "token_type": token_payload.get("token_type"),
        "account": token_payload.get("account") or token_payload.get("team"),
    }

    await conn.execute(
        """
        INSERT INTO connector_installations (
            id, org_id, class_id, status, installed_by_user_id,
            scopes, oauth_account, credentials, last_sync_at
        ) VALUES (
            gen_random_uuid(), %s, %s, 'installed', %s, %s::jsonb, %s::jsonb, %s::jsonb, now()
        )
        ON CONFLICT (org_id, class_id) DO UPDATE SET
            status              = 'installed',
            installed_by_user_id = EXCLUDED.installed_by_user_id,
            scopes              = EXCLUDED.scopes,
            oauth_account       = EXCLUDED.oauth_account,
            credentials         = EXCLUDED.credentials,
            last_error          = NULL,
            last_sync_at        = now()
        """,
        (
            org_id,
            class_id,
            user_id,
            json.dumps(list(spec.scopes)),
            json.dumps(oauth_account),
            json.dumps(encrypted),
        ),
    )

    cur2 = await conn.execute(
        "SELECT id FROM connector_installations WHERE org_id = %s AND class_id = %s",
        (org_id, class_id),
    )
    install_row = await cur2.fetchone()

    if install_row:
        await record_activity(
            conn,
            org_id=org_id,
            actor_user_id=user_id,
            action="connector.oauth.completed",
            resource_type="connector_installation",
            resource_id=install_row[0],
            payload={"class_id": class_id},
        )

    return _redirect_back(redirect_after, f"oauth=ok&class={class_id}")


@instance_router.get(
    "/{class_id}/instances",
    response_model=list[InstanceOption],
)
@sla_tier(2)
async def list_instances(
    dep: DbOrgConn,
    class_id: Annotated[str, Path(min_length=1, max_length=80)],
) -> list[InstanceOption]:
    """List available instance options for the project bind picker."""
    spec = lookup(class_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connector class '{class_id}'.",
        )

    fetcher = fetcher_for(class_id)
    if fetcher is None:
        # Free-form input on the UI for classes without a fetcher yet.
        return []

    conn, _ = dep
    cur = await conn.execute(
        """
        SELECT credentials
        FROM connector_installations
        WHERE class_id = %s AND status = 'installed'
        """,
        (class_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{spec.name}' is not installed for this org.",
        )
    creds = decrypt_credentials(row[0])
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stored credentials are unreadable; reinstall the connector.",
        )

    options = await fetcher(creds)
    return [InstanceOption(ref=o.ref, label=o.label, hint=o.hint) for o in options]


async def _exchange_code(
    token_url: str,
    client_id: str,
    client_secret: str,
    code: str,
    pkce_verifier: str,
    redirect_uri: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
                "code_verifier": pkce_verifier,
            },
            headers={"Accept": "application/json"},
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vendor token exchange failed ({response.status_code}): {response.text}",
        )
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Vendor returned a non-object token response.",
        )
    return payload


def _callback_url(request: Request) -> str:
    base = os.environ.get("API_PUBLIC_URL", str(request.base_url).rstrip("/"))
    return f"{base}/v1/connectors/oauth/callback"


def _redirect_back(redirect_after: str | None, query: str) -> RedirectResponse:
    target = redirect_after or os.environ.get("WEB_PUBLIC_URL") or "https://app.dev.verolas.com"
    sep = "&" if "?" in target else "?"
    return RedirectResponse(url=f"{target}{sep}{query}", status_code=302)


__all__: Annotated[list[str], "exported"] = [
    "callback_router",
    "instance_router",
    "oauth_router",
]
