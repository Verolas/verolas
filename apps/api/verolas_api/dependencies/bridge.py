"""Authentication for the Verolas Bridge agent.

Bridges are long-running daemons inside firms' networks, not human
users behind Keycloak. They authenticate with an opaque token issued
once at enrollment:

    Authorization: Bearer vbk_<bridge_uuid>_<secret>

The api looks up the bridge by uuid, verifies the secret with a
constant-time hash compare, and stamps `app.current_org_id` for RLS.
We don't set `app.current_user_id`: there is no user context. Bridge
endpoints that need to write audit log entries pass the bridge's
`created_by_user_id` as the actor.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from psycopg import AsyncConnection

from verolas_api.dependencies.db import get_pool

TOKEN_PREFIX = "vbk_"


@dataclass(frozen=True, slots=True)
class BridgeContext:
    """Resolved bridge for an authenticated bridge request."""

    bridge_id: UUID
    org_id: UUID
    name: str
    created_by_user_id: UUID | None


def mint_secret() -> tuple[str, str]:
    """Return (secret, secret_hash) for a fresh bridge enrollment."""
    secret = secrets.token_urlsafe(32)
    return secret, hashlib.sha256(secret.encode()).hexdigest()


def format_token(bridge_id: UUID, secret: str) -> str:
    """Compose the one-shot token a bridge install consumes."""
    return f"{TOKEN_PREFIX}{bridge_id}_{secret}"


def _parse_token(raw: str) -> tuple[UUID, str]:
    if not raw.startswith(TOKEN_PREFIX):
        raise ValueError("token must start with vbk_")
    payload = raw.removeprefix(TOKEN_PREFIX)
    bridge_part, _, secret = payload.partition("_")
    if not bridge_part or not secret:
        raise ValueError("token missing bridge id or secret")
    return UUID(bridge_part), secret


async def bridge_conn(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AsyncIterator[tuple[AsyncConnection, BridgeContext]]:
    """Resolve a bridge from its bearer token and yield a tenancy-scoped conn."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bridge token required.",
        )
    raw = authorization.split(" ", 1)[1].strip()
    try:
        bridge_id, secret = _parse_token(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed bridge token: {exc}",
        ) from exc

    expected_hash = hashlib.sha256(secret.encode()).hexdigest()
    pool = get_pool(request)
    async with pool.connection() as conn:
        async with conn.transaction():
            cur = await conn.execute(
                """
                SELECT id, org_id, name, secret_hash, status, created_by_user_id
                FROM bridges
                WHERE id = %s
                """,
                (bridge_id,),
            )
            row = await cur.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Bridge not found.",
                )
            stored_id, org_id, name, secret_hash, bridge_status, created_by_user_id = row
            if bridge_status == "revoked":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bridge has been revoked.",
                )
            if not hmac.compare_digest(secret_hash, expected_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Bridge token invalid.",
                )

            await conn.execute(
                "SET LOCAL app.current_org_id = %s",
                (str(org_id),),
            )

            yield (
                conn,
                BridgeContext(
                    bridge_id=stored_id,
                    org_id=org_id,
                    name=name,
                    created_by_user_id=created_by_user_id,
                ),
            )


BridgeConn = Annotated[tuple[AsyncConnection, BridgeContext], Depends(bridge_conn)]
