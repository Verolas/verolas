"""v1 project routes, RLS scoped, audit logged."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from verolas_api.audit import record_activity
from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.db import DbConn
from verolas_api.middleware import sla_tier
from verolas_api.schemas import Discipline, ProjectOut, ProjectStatus

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreateBody(BaseModel):
    """Inbound shape for POST /v1/projects."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    discipline: Discipline


@router.get("/", response_model=list[ProjectOut])
@sla_tier(1)
async def list_projects(conn: DbConn, auth: CurrentAuth) -> list[ProjectOut]:
    """List projects visible to the caller (RLS scoped)."""
    _ = auth
    cur = await conn.execute(
        """
        SELECT id, org_id, name, discipline, status, created_at, updated_at
        FROM projects
        WHERE status <> 'deleted'
        ORDER BY created_at DESC
        """
    )
    rows = await cur.fetchall()
    return [
        ProjectOut(
            id=row[0],
            org_id=row[1],
            name=row[2],
            discipline=Discipline(row[3]),
            status=ProjectStatus(row[4]),
            created_at=row[5],
            updated_at=row[6],
        )
        for row in rows
    ]


@router.post(
    "/",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(1)
async def create_project(
    body: ProjectCreateBody,
    conn: DbConn,
    auth: CurrentAuth,
) -> ProjectOut:
    """Create a project in the caller's active org. Logs the act."""
    if auth.claims.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not have an active organisation.",
        )

    project_id = uuid4()
    cur = await conn.execute(
        """
        INSERT INTO projects (id, org_id, name, discipline)
        VALUES (%s, %s, %s, %s)
        RETURNING id, org_id, name, discipline, status, created_at, updated_at
        """,
        (project_id, auth.claims.org_id, body.name, body.discipline.value),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Insert returned no row.",
        )

    actor_id = _safe_uuid(auth.claims.keycloak_subject)
    await record_activity(
        conn,
        org_id=auth.claims.org_id,
        actor_user_id=actor_id,
        action="project.create",
        resource_type="project",
        resource_id=project_id,
        payload={"name": body.name, "discipline": body.discipline.value},
    )

    return ProjectOut(
        id=row[0],
        org_id=row[1],
        name=row[2],
        discipline=Discipline(row[3]),
        status=ProjectStatus(row[4]),
        created_at=row[5],
        updated_at=row[6],
    )


@router.get("/{project_id}", response_model=ProjectOut)
@sla_tier(1)
async def get_project(
    project_id: UUID,
    conn: DbConn,
    auth: CurrentAuth,
) -> ProjectOut:
    _ = auth
    cur = await conn.execute(
        """
        SELECT id, org_id, name, discipline, status, created_at, updated_at
        FROM projects
        WHERE id = %s AND status <> 'deleted'
        """,
        (project_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return ProjectOut(
        id=row[0],
        org_id=row[1],
        name=row[2],
        discipline=Discipline(row[3]),
        status=ProjectStatus(row[4]),
        created_at=row[5],
        updated_at=row[6],
    )


def _safe_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (ValueError, TypeError):
        return None


__all__: Annotated[list[str], "exported"] = ["router"]
