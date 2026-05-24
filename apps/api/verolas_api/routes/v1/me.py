"""GET /v1/me: current account + memberships, sourced from app.account_view."""

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
    organization_locale: str
    organization_region: str
    role: MembershipRole


class MeOut(BaseModel):
    """Outbound shape for /v1/me."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID | None
    keycloak_subject: str
    email: EmailStr | None
    name: str | None
    memberships: list[MembershipSummary]
    locale_override: str | None
    created_at: datetime | None


@router.get("/", response_model=MeOut)
@sla_tier(1)
async def get_me(conn: BootstrapConn, auth: CurrentAuth) -> MeOut:
    """Return the caller's local user record plus their org memberships."""
    cur = await conn.execute(
        "SELECT app.account_view(%s)",
        (auth.claims.keycloak_subject,),
    )
    row = await cur.fetchone()
    payload = row[0] if row else None

    if not payload or payload.get("user") is None:
        return MeOut(
            user_id=None,
            keycloak_subject=auth.claims.keycloak_subject,
            email=auth.claims.email or None,
            name=None,
            memberships=[],
            locale_override=None,
            created_at=None,
        )

    user = payload["user"]
    memberships = [
        MembershipSummary(
            organization_id=m["organization_id"],
            organization_slug=m["organization_slug"],
            organization_name=m["organization_name"],
            organization_status=OrganizationStatus(m["organization_status"]),
            organization_locale=m.get("organization_locale") or "en-US",
            organization_region=m.get("organization_region") or "us",
            role=MembershipRole(m["role"]),
        )
        for m in payload.get("memberships", [])
    ]
    return MeOut(
        user_id=user["id"],
        keycloak_subject=auth.claims.keycloak_subject,
        email=user.get("email") or auth.claims.email or None,
        name=user.get("name"),
        memberships=memberships,
        locale_override=payload.get("locale_override"),
        created_at=user.get("created_at"),
    )


__all__: Annotated[list[str], "exported"] = ["router"]
