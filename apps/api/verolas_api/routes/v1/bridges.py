"""Verolas Bridge endpoints.

Two URL surfaces:

Admin (Keycloak-authenticated):

- `POST   /v1/orgs/{slug}/bridges`           enroll a new bridge
- `GET    /v1/orgs/{slug}/bridges`           list bridges for the org
- `DELETE /v1/orgs/{slug}/bridges/{id}`      revoke

The POST response includes a one-shot enrollment token. The api stores
only its hash; the plaintext is shown to the admin once and never
again, mirroring how PATs work on GitHub.

Bridge daemon (bridge token, not Keycloak):

- `GET    /v1/bridges/poll`                  pick up queued jobs
- `POST   /v1/bridges/jobs/{id}/result`      submit a finished job

Bridges authenticate with their long-lived token instead of an OIDC
bearer; see `verolas_api.dependencies.bridge`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from verolas_api.audit import record_activity
from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.bridge import (
    BridgeConn,
    format_token,
    mint_secret,
)
from verolas_api.dependencies.org import DbOrgConn
from verolas_api.middleware import sla_tier

admin_router = APIRouter(prefix="/orgs/{org_slug}/bridges", tags=["bridges"])

bridge_router = APIRouter(prefix="/bridges", tags=["bridges"])


class BridgeEnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    supported_tools: list[str] = Field(default_factory=list)


class BridgeEnrollResponse(BaseModel):
    """One-shot response. The plaintext `token` is shown to the admin once."""

    model_config = ConfigDict(extra="forbid")

    bridge_id: UUID
    name: str
    token: str
    api_base_url: str


class BridgeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    org_id: UUID
    name: str
    status: str
    supported_tools: list[str]
    hostname: str | None
    agent_version: str | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BridgePollOut(BaseModel):
    """Job payload returned to a bridge during a poll."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    class_id: str
    payload: dict[str, Any]
    project_id: UUID | None
    agent_run_id: UUID | None


class BridgeJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern=r"^(completed|failed|cancelled)$")
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=4000)


@admin_router.post(
    "",
    response_model=BridgeEnrollResponse,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(2)
async def enroll_bridge(
    body: BridgeEnrollRequest,
    dep: DbOrgConn,
    auth: CurrentAuth,
) -> BridgeEnrollResponse:
    """Create a bridge row and return the one-shot enrollment token."""
    _ = auth
    conn, ctx = dep

    secret, secret_hash = mint_secret()
    bridge_id = uuid4()
    await conn.execute(
        """
        INSERT INTO bridges (
            id, org_id, name, secret_hash,
            status, supported_tools, created_by_user_id
        ) VALUES (%s, %s, %s, %s, 'pending', %s::jsonb, %s)
        """,
        (
            bridge_id,
            ctx.organization_id,
            body.name.strip(),
            secret_hash,
            json.dumps(body.supported_tools),
            ctx.user_id,
        ),
    )
    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="bridge.enrolled",
        resource_type="bridge",
        resource_id=bridge_id,
        payload={"name": body.name, "supported_tools": body.supported_tools},
    )
    return BridgeEnrollResponse(
        bridge_id=bridge_id,
        name=body.name,
        token=format_token(bridge_id, secret),
        api_base_url=os.environ.get("API_PUBLIC_URL", "https://api.dev.verolas.com"),
    )


@admin_router.get("", response_model=list[BridgeOut])
@sla_tier(2)
async def list_bridges(dep: DbOrgConn) -> list[BridgeOut]:
    """List every bridge enrolled for the URL-scoped org."""
    conn, _ = dep
    cur = await conn.execute(
        """
        SELECT id, org_id, name, status, supported_tools,
               hostname, agent_version, last_seen_at,
               created_at, updated_at
        FROM bridges
        WHERE status <> 'revoked'
        ORDER BY created_at DESC
        """
    )
    rows = await cur.fetchall()
    return [
        BridgeOut(
            id=row[0],
            org_id=row[1],
            name=row[2],
            status=row[3],
            supported_tools=list(row[4] or []),
            hostname=row[5],
            agent_version=row[6],
            last_seen_at=row[7],
            created_at=row[8],
            updated_at=row[9],
        )
        for row in rows
    ]


@admin_router.delete("/{bridge_id}", status_code=status.HTTP_204_NO_CONTENT)
@sla_tier(2)
async def revoke_bridge(
    bridge_id: UUID,
    dep: DbOrgConn,
    auth: CurrentAuth,
) -> None:
    """Revoke a bridge. Pending jobs are cancelled atomically."""
    _ = auth
    conn, ctx = dep
    cur = await conn.execute(
        "UPDATE bridges SET status = 'revoked' WHERE id = %s RETURNING name",
        (bridge_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bridge not found.",
        )
    await conn.execute(
        "UPDATE bridge_jobs SET status = 'cancelled' WHERE bridge_id = %s AND status = 'queued'",
        (bridge_id,),
    )
    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="bridge.revoked",
        resource_type="bridge",
        resource_id=bridge_id,
        payload={"name": row[0]},
    )


@bridge_router.get("/poll", response_model=list[BridgePollOut])
@sla_tier(3)
async def poll_jobs(dep: BridgeConn) -> list[BridgePollOut]:
    """Bridge daemon endpoint: claim queued jobs, mark them in_progress."""
    conn, ctx = dep
    await conn.execute(
        "UPDATE bridges SET last_seen_at = now(), status = 'active' WHERE id = %s",
        (ctx.bridge_id,),
    )
    cur = await conn.execute(
        """
        UPDATE bridge_jobs
        SET status = 'in_progress', started_at = now()
        WHERE id IN (
            SELECT id FROM bridge_jobs
            WHERE bridge_id = %s AND status = 'queued'
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 10
        )
        RETURNING id, class_id, payload, project_id, agent_run_id
        """,
        (ctx.bridge_id,),
    )
    rows = await cur.fetchall()
    return [
        BridgePollOut(
            id=row[0],
            class_id=row[1],
            payload=row[2] or {},
            project_id=row[3],
            agent_run_id=row[4],
        )
        for row in rows
    ]


@bridge_router.post(
    "/jobs/{job_id}/result",
    status_code=status.HTTP_204_NO_CONTENT,
)
@sla_tier(3)
async def submit_result(
    job_id: UUID,
    body: BridgeJobResult,
    dep: BridgeConn,
) -> None:
    """Bridge daemon endpoint: finalise a job (completed/failed/cancelled)."""
    conn, ctx = dep
    cur = await conn.execute(
        """
        UPDATE bridge_jobs
        SET status = %s,
            result = %s::jsonb,
            error = %s,
            completed_at = now()
        WHERE id = %s AND bridge_id = %s
        RETURNING class_id, agent_run_id
        """,
        (
            body.status,
            json.dumps(body.result),
            body.error,
            job_id,
            ctx.bridge_id,
        ),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )
    await record_activity(
        conn,
        org_id=ctx.org_id,
        actor_user_id=ctx.created_by_user_id,
        action="bridge.job.completed",
        resource_type="bridge_job",
        resource_id=job_id,
        payload={
            "class_id": row[0],
            "status": body.status,
            "agent_run_id": str(row[1]) if row[1] else None,
        },
    )


__all__: Annotated[list[str], "exported"] = ["admin_router", "bridge_router"]
