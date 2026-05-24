"""Manual sync trigger for a project's connector binding.

POST /v1/orgs/{slug}/projects/{project_id}/connectors/bindings/{id}/sync

Pulls the binding row, decrypts the installation's credentials,
dispatches to the right vendor sync engine, persists the new
delta cursor on the binding's `config` JSONB, and returns a
summary of what changed.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict

from verolas_api.audit import record_activity
from verolas_api.crypto import decrypt_credentials
from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.org import DbOrgConn
from verolas_api.middleware import sla_tier
from verolas_api.sync.dispatch import sync_binding

router = APIRouter(
    prefix="/orgs/{org_slug}/projects/{project_id}/connectors/bindings",
    tags=["connectors"],
)


class SyncSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files_added: int
    files_updated: int
    files_removed: int
    bytes_pulled: int
    notes: list[str]


@router.post(
    "/{binding_id}/sync",
    response_model=SyncSummary,
    status_code=status.HTTP_200_OK,
)
@sla_tier(3)
async def trigger_sync(
    binding_id: UUID,
    dep: DbOrgConn,
    request: Request,
    auth: CurrentAuth,
    project_id: Annotated[UUID, Path()],
) -> SyncSummary:
    """Run one sync pass for the given binding."""
    _ = auth
    conn, ctx = dep

    cur = await conn.execute(
        """
        SELECT b.id, b.project_id, i.class_id, i.credentials, b.instance_ref, b.config
        FROM connector_bindings b
        JOIN connector_installations i ON i.id = b.installation_id
        WHERE b.id = %s AND b.project_id = %s
        """,
        (binding_id, project_id),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Binding not found.",
        )
    _id, p_id, class_id, encrypted, instance_ref, config = row
    credentials = decrypt_credentials(encrypted)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stored credentials are unreadable; reinstall the connector.",
        )

    storage = getattr(request.app.state, "storage_service", None)
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not configured on the server.",
        )

    result = await sync_binding(
        class_id=class_id,
        conn=conn,
        binding_id=binding_id,
        project_id=p_id,
        org_id=ctx.organization_id,
        user_id=ctx.user_id,
        instance_ref=instance_ref,
        config=config or {},
        credentials=credentials,
        storage=storage,
    )

    new_config = dict(config or {})
    if result.next_cursor:
        new_config.setdefault(class_id.split("-", 1)[-1], {})["delta_link"] = result.next_cursor
    await conn.execute(
        """
        UPDATE connector_bindings
        SET config = %s::jsonb, last_sync_at = now()
        WHERE id = %s
        """,
        (__import__("json").dumps(new_config), binding_id),
    )

    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="connector.sync.completed",
        resource_type="connector_binding",
        resource_id=binding_id,
        payload={
            "class_id": class_id,
            "files_added": result.files_added,
            "files_updated": result.files_updated,
            "files_removed": result.files_removed,
            "bytes_pulled": result.bytes_pulled,
        },
    )

    return SyncSummary(
        files_added=result.files_added,
        files_updated=result.files_updated,
        files_removed=result.files_removed,
        bytes_pulled=result.bytes_pulled,
        notes=result.notes,
    )


__all__: Annotated[list[str], "exported"] = ["router"]
