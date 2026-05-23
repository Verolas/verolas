"""Organization schemas."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


class OrganizationStatus(StrEnum):
    """Matches the organization_status Postgres enum."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class OrganizationCreate(BaseModel):
    """Inbound shape for creating a new organization."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=40)
    plan: str = Field(default="free", max_length=40)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "slug must be lowercase letters, digits, or hyphens; 1 to 40 characters"
            )
        return v


class OrganizationOut(BaseModel):
    """Outbound shape for reading organization details."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str
    status: OrganizationStatus
    created_at: datetime
    updated_at: datetime
