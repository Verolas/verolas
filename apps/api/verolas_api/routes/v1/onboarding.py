"""POST /v1/onboarding: one-shot account provisioning via app.onboard_account.

The wizard collects firm name + primary discipline + first project name
and posts everything here. The Postgres function does the writes in a
single transaction so the chicken-and-egg between RLS and "no tenancy
yet" is resolved there instead of needing a privileged DB role.
"""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.bootstrap import BootstrapConn
from verolas_api.middleware import sla_tier
from verolas_api.schemas import Discipline

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


VALID_REGIONS = {
    "de",
    "ch",
    "at",
    "fr",
    "nl",
    "be",
    "uk",
    "us",
    "au",
    "ca",
}

VALID_LOCALES = {
    "de-DE",
    "de-CH",
    "de-AT",
    "fr-FR",
    "nl-NL",
    "nl-BE",
    "en-US",
    "en-GB",
    "en-AU",
    "en-CA",
}


class OnboardingBody(BaseModel):
    """Three-step wizard payload, posted in one shot after the last step."""

    model_config = ConfigDict(extra="forbid")

    organization_name: str = Field(min_length=1, max_length=120)
    organization_slug: str | None = Field(default=None, max_length=40)
    primary_discipline: Discipline
    first_project_name: str = Field(min_length=1, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)
    region: str = Field(default="us", description="Two-letter region code")
    locale: str = Field(default="en-US", description="BCP-47 locale tag")


class OnboardingResult(BaseModel):
    """Wire shape for a successful onboarding response."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    organization_id: UUID
    organization_slug: str
    organization_name: str
    organization_region: str
    organization_locale: str
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
    """Provision the user, the first org, the owner membership, and the first project."""
    slug = _resolve_slug(body.organization_slug, body.organization_name)
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slug must be lowercase letters, digits, or hyphens; 1 to 40 characters.",
        )

    _validate_subject_uuid(auth.claims.keycloak_subject)

    if body.region not in VALID_REGIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown region '{body.region}'.",
        )
    if body.locale not in VALID_LOCALES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown locale '{body.locale}'.",
        )

    email = auth.claims.email or ""
    display_name = body.full_name or _name_from_email(email)

    try:
        cur = await conn.execute(
            "SELECT app.onboard_account(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                auth.claims.keycloak_subject,
                email,
                display_name,
                body.organization_name,
                slug,
                body.primary_discipline.value,
                body.first_project_name,
                body.region,
                body.locale,
            ),
        )
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workspace slug '{slug}' is taken; choose another.",
        ) from exc

    row = await cur.fetchone()
    if row is None or row[0] is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Onboarding returned no result.",
        )
    payload = row[0]

    return OnboardingResult(
        user_id=payload["user_id"],
        organization_id=payload["organization_id"],
        organization_slug=payload["organization_slug"],
        organization_name=payload["organization_name"],
        organization_region=payload["organization_region"],
        organization_locale=payload["organization_locale"],
        project_id=payload["project_id"],
        project_name=payload["project_name"],
        discipline=Discipline(payload["discipline"]),
    )


def _resolve_slug(supplied: str | None, name: str) -> str:
    if supplied:
        return supplied.strip().lower()
    base = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return base[:40] or "workspace"


def _validate_subject_uuid(subject: str) -> None:
    try:
        UUID(subject)
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
