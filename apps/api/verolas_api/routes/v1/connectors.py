"""Connector endpoints.

Three URL surfaces:

- `GET  /v1/connectors/catalog`
  Static catalog of all connector classes the platform offers.

- `GET    /v1/orgs/{org_slug}/connectors/installations`
  `POST   /v1/orgs/{org_slug}/connectors/installations`
  `DELETE /v1/orgs/{org_slug}/connectors/installations/{installation_id}`
  `POST   /v1/orgs/{org_slug}/connectors/waitlist`
  Org-level install state: one row per org per class.

- `GET    /v1/orgs/{org_slug}/projects/{project_id}/connectors/bindings`
  `POST   /v1/orgs/{org_slug}/projects/{project_id}/connectors/bindings`
  `DELETE /v1/orgs/{org_slug}/projects/{project_id}/connectors/bindings/{binding_id}`
  Project-level bindings: which specific resource each project pulls
  from a given org installation.

OAuth redirect handling, token storage, and refresh schedules belong in
a follow-up PR; this PR ships the install/bind state-management layer.
"""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Path, status

from verolas_api.audit import record_activity
from verolas_api.connectors import CONNECTORS, lookup
from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.org import DbOrgConn
from verolas_api.middleware import sla_tier
from verolas_api.schemas.connector import (
    ConnectorBindingCreate,
    ConnectorBindingOut,
    ConnectorBindingStatus,
    ConnectorClassOut,
    ConnectorInstallationCreate,
    ConnectorInstallationOut,
    ConnectorInstallStatus,
    ConnectorWaitlistCreate,
    ConnectorWaitlistOut,
)

catalog_router = APIRouter(prefix="/connectors", tags=["connectors"])

org_router = APIRouter(prefix="/orgs/{org_slug}/connectors", tags=["connectors"])

project_router = APIRouter(
    prefix="/orgs/{org_slug}/projects/{project_id}/connectors",
    tags=["connectors"],
)


@catalog_router.get("/catalog", response_model=list[ConnectorClassOut])
@sla_tier(2)
async def list_catalog() -> list[ConnectorClassOut]:
    """Static catalog of every connector class the platform offers."""
    return [_class_to_out(spec) for spec in CONNECTORS.values()]


@org_router.get("/installations", response_model=list[ConnectorInstallationOut])
@sla_tier(1)
async def list_installations(dep: DbOrgConn) -> list[ConnectorInstallationOut]:
    """List every connector installation for the URL-scoped org."""
    conn, _ = dep
    cur = await conn.execute(
        """
        SELECT id, org_id, class_id, status, installed_by_user_id,
               scopes, oauth_account, last_sync_at, last_error,
               created_at, updated_at
        FROM connector_installations
        WHERE status <> 'uninstalled'
        ORDER BY created_at DESC
        """
    )
    rows = await cur.fetchall()
    return [_installation_to_out(row) for row in rows]


@org_router.post(
    "/installations",
    response_model=ConnectorInstallationOut,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(1)
async def install_connector(
    body: ConnectorInstallationCreate,
    dep: DbOrgConn,
    auth: CurrentAuth,
) -> ConnectorInstallationOut:
    """Create or revive an org-level installation of a connector class."""
    _ = auth
    spec = lookup(body.class_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connector class '{body.class_id}'.",
        )
    conn, ctx = dep

    # Tier C cannot be self-served; route to the waitlist endpoint.
    if spec.tier == "C" and spec.auth_method == "on_prem_agent":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"'{spec.name}' needs a partner agreement or the Verolas Bridge agent; "
                "use POST /connectors/waitlist."
            ),
        )

    install_id = uuid4()
    install_status = (
        ConnectorInstallStatus.INSTALLED
        if spec.auth_method == "internal"
        else ConnectorInstallStatus.PENDING
    )
    cur = await conn.execute(
        """
        INSERT INTO connector_installations (
            id, org_id, class_id, status, installed_by_user_id,
            scopes, oauth_account
        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        ON CONFLICT (org_id, class_id) DO UPDATE SET
            status              = EXCLUDED.status,
            installed_by_user_id = EXCLUDED.installed_by_user_id,
            scopes              = EXCLUDED.scopes,
            oauth_account       = EXCLUDED.oauth_account,
            last_error          = NULL
        RETURNING id, org_id, class_id, status, installed_by_user_id,
                  scopes, oauth_account, last_sync_at, last_error,
                  created_at, updated_at
        """,
        (
            install_id,
            ctx.organization_id,
            spec.id,
            install_status.value,
            ctx.user_id,
            json.dumps(list(body.scopes or spec.scopes)),
            json.dumps(body.oauth_account),
        ),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Install returned no row.",
        )

    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="connector.installed",
        resource_type="connector_installation",
        resource_id=row[0],
        payload={"class_id": spec.id, "tier": spec.tier, "auth_method": spec.auth_method},
    )
    return _installation_to_out(row)


@org_router.delete(
    "/installations/{installation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@sla_tier(1)
async def uninstall_connector(
    installation_id: UUID,
    dep: DbOrgConn,
    auth: CurrentAuth,
) -> None:
    """Mark an installation uninstalled. Bindings cascade via FK ON DELETE."""
    _ = auth
    conn, ctx = dep
    cur = await conn.execute(
        """
        UPDATE connector_installations
        SET status = 'uninstalled'
        WHERE id = %s
        RETURNING class_id
        """,
        (installation_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installation not found.",
        )
    # Bindings for this installation are no longer useful; remove them.
    await conn.execute(
        "DELETE FROM connector_bindings WHERE installation_id = %s",
        (installation_id,),
    )
    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="connector.uninstalled",
        resource_type="connector_installation",
        resource_id=installation_id,
        payload={"class_id": row[0]},
    )


@org_router.post(
    "/waitlist",
    response_model=ConnectorWaitlistOut,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(2)
async def waitlist_connector(
    body: ConnectorWaitlistCreate,
    dep: DbOrgConn,
    auth: CurrentAuth,
) -> ConnectorWaitlistOut:
    """Record org-level interest in a Tier C connector."""
    _ = auth
    spec = lookup(body.class_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown connector class '{body.class_id}'.",
        )
    conn, ctx = dep
    waitlist_id = uuid4()
    cur = await conn.execute(
        """
        INSERT INTO connector_waitlist (
            id, org_id, class_id, requested_by_user_id, note
        ) VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (org_id, class_id) DO UPDATE SET
            requested_by_user_id = EXCLUDED.requested_by_user_id,
            note = EXCLUDED.note
        RETURNING id, org_id, class_id, requested_by_user_id, note, created_at
        """,
        (
            waitlist_id,
            ctx.organization_id,
            spec.id,
            ctx.user_id,
            body.note,
        ),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Waitlist insert returned no row.",
        )
    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="connector.waitlist.requested",
        resource_type="connector_waitlist",
        resource_id=row[0],
        payload={"class_id": spec.id},
    )
    return ConnectorWaitlistOut(
        id=row[0],
        org_id=row[1],
        class_id=row[2],
        requested_by_user_id=row[3],
        note=row[4],
        created_at=row[5],
    )


@project_router.get("/bindings", response_model=list[ConnectorBindingOut])
@sla_tier(1)
async def list_bindings(
    dep: DbOrgConn,
    project_id: Annotated[UUID, Path()],
) -> list[ConnectorBindingOut]:
    """List every connector binding for the URL-scoped project."""
    conn, _ = dep
    cur = await conn.execute(
        """
        SELECT b.id, b.project_id, b.org_id, b.installation_id, i.class_id,
               b.instance_ref, b.instance_label, b.config, b.status,
               b.last_sync_at, b.created_by_user_id, b.created_at, b.updated_at
        FROM connector_bindings b
        JOIN connector_installations i ON i.id = b.installation_id
        WHERE b.project_id = %s
        ORDER BY b.created_at DESC
        """,
        (project_id,),
    )
    rows = await cur.fetchall()
    return [_binding_to_out(row) for row in rows]


@project_router.post(
    "/bindings",
    response_model=ConnectorBindingOut,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(1)
async def create_binding(
    body: ConnectorBindingCreate,
    dep: DbOrgConn,
    project_id: Annotated[UUID, Path()],
    auth: CurrentAuth,
) -> ConnectorBindingOut:
    """Bind one instance from an installation into the URL-scoped project."""
    _ = auth
    conn, ctx = dep

    # Confirm the installation exists, belongs to this org, and is usable.
    cur = await conn.execute(
        """
        SELECT id, class_id, status
        FROM connector_installations
        WHERE id = %s
        """,
        (body.installation_id,),
    )
    install = await cur.fetchone()
    if install is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installation not found.",
        )
    if install[2] not in ("installed", "pending"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Installation status '{install[2]}' cannot be bound.",
        )

    binding_id = uuid4()
    cur = await conn.execute(
        """
        INSERT INTO connector_bindings (
            id, project_id, org_id, installation_id, instance_ref,
            instance_label, config, status, created_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, 'active', %s)
        RETURNING id, project_id, org_id, installation_id,
                  instance_ref, instance_label, config, status,
                  last_sync_at, created_by_user_id, created_at, updated_at
        """,
        (
            binding_id,
            project_id,
            ctx.organization_id,
            body.installation_id,
            body.instance_ref,
            body.instance_label,
            json.dumps(body.config),
            ctx.user_id,
        ),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bind returned no row.",
        )
    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="connector.bound",
        resource_type="connector_binding",
        resource_id=row[0],
        payload={
            "class_id": install[1],
            "installation_id": str(body.installation_id),
            "project_id": str(project_id),
            "instance_ref": body.instance_ref,
        },
    )
    return _binding_to_out(
        (
            row[0],
            row[1],
            row[2],
            row[3],
            install[1],
            row[4],
            row[5],
            row[6],
            row[7],
            row[8],
            row[9],
            row[10],
            row[11],
        )
    )


@project_router.delete(
    "/bindings/{binding_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@sla_tier(1)
async def delete_binding(
    binding_id: UUID,
    dep: DbOrgConn,
    project_id: Annotated[UUID, Path()],
    auth: CurrentAuth,
) -> None:
    """Unbind an instance from the project."""
    _ = auth
    conn, ctx = dep
    cur = await conn.execute(
        """
        DELETE FROM connector_bindings
        WHERE id = %s AND project_id = %s
        RETURNING installation_id
        """,
        (binding_id, project_id),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Binding not found.",
        )
    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="connector.unbound",
        resource_type="connector_binding",
        resource_id=binding_id,
        payload={"project_id": str(project_id), "installation_id": str(row[0])},
    )


def _class_to_out(spec: Any) -> ConnectorClassOut:
    return ConnectorClassOut(
        id=spec.id,
        name=spec.name,
        vendor=spec.vendor,
        category=spec.category,
        tier=spec.tier,
        auth_method=spec.auth_method,
        blurb=spec.blurb,
        region_tags=list(spec.region_tags),
        scopes=list(spec.scopes),
        docs_url=spec.docs_url,
        instance_label=spec.instance_label,
    )


def _installation_to_out(row: Any) -> ConnectorInstallationOut:
    return ConnectorInstallationOut(
        id=row[0],
        org_id=row[1],
        class_id=row[2],
        status=ConnectorInstallStatus(row[3]),
        installed_by_user_id=row[4],
        scopes=list(row[5] or []),
        oauth_account=row[6] or {},
        last_sync_at=row[7],
        last_error=row[8],
        created_at=row[9],
        updated_at=row[10],
    )


def _binding_to_out(row: Any) -> ConnectorBindingOut:
    return ConnectorBindingOut(
        id=row[0],
        project_id=row[1],
        org_id=row[2],
        installation_id=row[3],
        class_id=row[4],
        instance_ref=row[5],
        instance_label=row[6],
        config=row[7] or {},
        status=ConnectorBindingStatus(row[8]),
        last_sync_at=row[9],
        created_by_user_id=row[10],
        created_at=row[11],
        updated_at=row[12],
    )


__all__: Annotated[list[str], "exported"] = [
    "catalog_router",
    "org_router",
    "project_router",
]
