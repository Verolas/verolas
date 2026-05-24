"""POST /v1/onboarding: provision a fresh account in one transaction.

A new caller arrives with a verified Keycloak token but no row in
`users`, no organisation, no membership, no project. The wizard
collects firm name + primary discipline + first project name and posts
them here. This route writes everything in a single transaction with
RLS off so the chicken-and-egg (no tenancy yet, but tenancy is what
the policies require) is resolved cleanly.

Slug is derived from the firm name if not supplied. The audit chain
gets a `account.onboarded` entry plus the usual `project.create`.
"""

from __future__ import annotations

import json
import re
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.bootstrap import BootstrapConn
from verolas_api.middleware import sla_tier
from verolas_api.schemas import Discipline

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


class OnboardingBody(BaseModel):
    """Three-step wizard payload, posted in one shot after the last step."""

    model_config = ConfigDict(extra="forbid")

    organization_name: str = Field(min_length=1, max_length=120)
    organization_slug: str | None = Field(default=None, max_length=40)
    primary_discipline: Discipline
    first_project_name: str = Field(min_length=1, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)


class OnboardingResult(BaseModel):
    """Wire shape for a successful onboarding response."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    organization_id: UUID
    organization_slug: str
    organization_name: str
    project_id: UUID
    project_name: str
    discipline: Discipline


@router.post(
    "/",
    response_model=OnboardingResult,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(1)
async def onboard(
    body: OnboardingBody,
    conn: BootstrapConn,
    auth: CurrentAuth,
) -> OnboardingResult:
    """Create the user row, the first organisation, the owner membership, and the first project."""

    slug = _resolve_slug(body.organization_slug, body.organization_name)
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slug must be lowercase letters, digits, or hyphens; 1 to 40 characters.",
        )

    # Idempotency on the user side: if this Keycloak subject has already
    # onboarded, refuse rather than silently double-provisioning.
    cur = await conn.execute(
        "SELECT id FROM users WHERE keycloak_subject = %s",
        (auth.claims.keycloak_subject,),
    )
    existing = await cur.fetchone()
    if existing is not None:
        cur = await conn.execute(
            "SELECT 1 FROM memberships WHERE user_id = %s LIMIT 1",
            (existing[0],),
        )
        if await cur.fetchone() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Onboarding already complete for this account.",
            )

    user_uuid = _claims_subject_uuid(auth.claims.keycloak_subject)
    org_uuid = uuid4()
    membership_uuid = uuid4()
    project_uuid = uuid4()

    email = auth.claims.email or ""
    display_name = body.full_name or _name_from_email(email)

    await conn.execute(
        """
        INSERT INTO users (id, keycloak_subject, email, name, status)
        VALUES (%s, %s, %s, %s, 'active')
        ON CONFLICT (id) DO UPDATE
          SET keycloak_subject = EXCLUDED.keycloak_subject,
              email            = EXCLUDED.email,
              name             = COALESCE(users.name, EXCLUDED.name),
              status           = 'active'
        """,
        (user_uuid, auth.claims.keycloak_subject, email, display_name),
    )

    # Slug uniqueness: bail with a clear error if the desired slug is taken.
    cur = await conn.execute(
        "SELECT 1 FROM organizations WHERE slug = %s",
        (slug,),
    )
    if await cur.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workspace slug '{slug}' is taken; choose another.",
        )

    await conn.execute(
        """
        INSERT INTO organizations (id, name, slug, plan, status)
        VALUES (%s, %s, %s, 'free', 'active')
        """,
        (org_uuid, body.organization_name, slug),
    )

    await conn.execute(
        """
        INSERT INTO memberships (id, user_id, org_id, role)
        VALUES (%s, %s, %s, 'owner')
        """,
        (membership_uuid, user_uuid, org_uuid),
    )

    await conn.execute(
        """
        INSERT INTO projects (id, org_id, name, discipline)
        VALUES (%s, %s, %s, %s)
        """,
        (project_uuid, org_uuid, body.first_project_name, body.primary_discipline.value),
    )

    # Audit chain: one entry for the onboarding event, one for the first project.
    await conn.execute(
        """
        INSERT INTO activity_log (
            id, org_id, actor_user_id, action, resource_type, resource_id, payload
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            uuid4(),
            org_uuid,
            user_uuid,
            "account.onboarded",
            "organization",
            org_uuid,
            json.dumps(
                {
                    "organization_name": body.organization_name,
                    "slug": slug,
                    "primary_discipline": body.primary_discipline.value,
                }
            ),
        ),
    )
    await conn.execute(
        """
        INSERT INTO activity_log (
            id, org_id, actor_user_id, action, resource_type, resource_id, payload
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            uuid4(),
            org_uuid,
            user_uuid,
            "project.create",
            "project",
            project_uuid,
            json.dumps(
                {"name": body.first_project_name, "discipline": body.primary_discipline.value}
            ),
        ),
    )

    return OnboardingResult(
        user_id=user_uuid,
        organization_id=org_uuid,
        organization_slug=slug,
        organization_name=body.organization_name,
        project_id=project_uuid,
        project_name=body.first_project_name,
        discipline=body.primary_discipline,
    )


def _resolve_slug(supplied: str | None, name: str) -> str:
    if supplied:
        return supplied.strip().lower()
    base = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return base[:40] or "workspace"


def _claims_subject_uuid(subject: str) -> UUID:
    try:
        return UUID(subject)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token subject is not a UUID; cannot provision account.",
        ) from exc


def _name_from_email(email: str) -> str:
    local = email.split("@", 1)[0] if email else ""
    if not local:
        return "Account holder"
    pieces = re.split(r"[._-]+", local)
    return " ".join(p.capitalize() for p in pieces if p) or local


__all__: Annotated[list[str], "exported"] = ["router"]
