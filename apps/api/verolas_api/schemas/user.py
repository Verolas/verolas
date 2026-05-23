"""User and Membership schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserStatus(StrEnum):
    """Matches the user_status Postgres enum."""

    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class MembershipRole(StrEnum):
    """Matches the membership_role Postgres enum and the Keycloak realm roles."""

    OWNER = "owner"
    ADMIN = "admin"
    REVIEWER = "reviewer"
    ENGINEER = "engineer"
    VIEWER = "viewer"
    AUDITOR = "auditor"


class UserCreate(BaseModel):
    """Inbound shape for inviting a new user to the platform."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: str | None = Field(default=None, max_length=120)


class UserOut(BaseModel):
    """Outbound shape for reading user details."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    email: EmailStr
    name: str | None
    status: UserStatus
    mfa_enabled: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class Membership(BaseModel):
    """Membership of a user in an organization."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    user_id: UUID
    org_id: UUID
    role: MembershipRole
    invited_at: datetime | None
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime
