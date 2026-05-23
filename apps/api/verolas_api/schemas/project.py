"""Project schemas.

Projects are the top level engineering container. The full project model
adds CAD files, deliverables, an HOAI Leistungsphase or RIBA stage, but the
skeleton tracks only the identifying fields. The full data model lands when
the project lifecycle workstream comes online.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Discipline(StrEnum):
    """Top level engineering discipline for the project."""

    STRUCTURAL = "structural"
    GEOTECH = "geotech"
    WATER = "water"
    TRANSPORT = "transport"
    REVIEW = "review"
    PRACTICE = "practice"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ProjectCreate(BaseModel):
    """Inbound shape for creating a new project."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    discipline: Discipline


class ProjectOut(BaseModel):
    """Outbound shape for reading project details."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    discipline: Discipline
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
