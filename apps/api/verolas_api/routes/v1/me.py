"""GET /v1/me: the current account + the organisations it belongs to.

This route runs with auth but no tenancy context, because it has to work
before the caller has any organisations (the onboarding screen calls it
right after sign-in to decide where to send the user). The query reads
the user by Keycloak subject and joins memberships with their org rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, EmailStr

from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.bootstrap import BootstrapConn
from verolas_api.middleware import sla_tier
from verolas_api.schemas import MembershipRole, OrganizationStatus

router = APIRouter(prefix="/me", tags=["me"])


class MembershipSummary(BaseModel):
    """Org + role pair shown in /v1/me."""

    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    organization_slug: str
    organization_name: str
    organization_status: OrganizationStatus
    role: MembershipRole


class MeOut(BaseModel):
    """Outbound shape for /v1/me."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID | None
    keycloak_subject: str
    email: EmailStr | None
    name: str | None
    memberships: list[MembershipSummary]
    created_at: datetime | None


@router.get("/", response_model=MeOut)
@sla_tier(1)
async def get_me(conn: BootstrapConn, auth: CurrentAuth) -> MeOut:
    """Return the caller's local user record plus their org memberships."""
    cur = await conn.execute(
        """
        SELECT id, email, name, created_at
        FROM users
        WHERE keycloak_subject = %s
        """,
        (auth.claims.keycloak_subject,),
    )
    user_row = await cur.fetchone()

    if user_row is None:
        return MeOut(
            user_id=None,
            keycloak_subject=auth.claims.keycloak_subject,
            email=auth.claims.email or None,
            name=None,
            memberships=[],
            created_at=None,
        )

    user_id, email, name, created_at = user_row

    cur = await conn.execute(
        """
        SELECT o.id, o.slug, o.name, o.status, m.role
        FROM memberships m
        JOIN organizations o ON o.id = m.org_id
        WHERE m.user_id = %s
        ORDER BY o.created_at ASC
        """,
        (user_id,),
    )
    rows = await cur.fetchall()
    memberships = [
        MembershipSummary(
            organization_id=row[0],
            organization_slug=row[1],
            organization_name=row[2],
            organization_status=OrganizationStatus(row[3]),
            role=MembershipRole(row[4]),
        )
        for row in rows
    ]

    return MeOut(
        user_id=user_id,
        keycloak_subject=auth.claims.keycloak_subject,
        email=email,
        name=name,
        memberships=memberships,
        created_at=created_at,
    )


__all__: Annotated[list[str], "exported"] = ["router"]
