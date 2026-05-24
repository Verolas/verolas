"""Agent run schemas: the lifecycle that produces every Verolas deliverable.

Every artefact in Verolas (a calc package, a drawing set, a permit pack)
is the output of an agent run. The run carries the brief, the plan, the
live progress, the citations, and the produced artefacts so a reviewer
can pivot from any artefact back to the exact run that produced it.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentRunStatus(StrEnum):
    """Matches the agent_run_status Postgres enum."""

    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRunTrigger(StrEnum):
    """How the run was kicked off."""

    MANUAL = "manual"
    SCHEDULE = "schedule"
    EVENT = "event"


class AgentRunPlanStep(BaseModel):
    """One step in the agent's plan."""

    model_config = ConfigDict(extra="forbid")

    label: str
    status: str = Field(default="pending", description="pending, in_progress, done, skipped")
    detail: str | None = None


class AgentRunCreate(BaseModel):
    """Inbound shape for POST /v1/orgs/{slug}/projects/{id}/runs."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1, max_length=80)
    brief: str = Field(min_length=1, max_length=4000)


class AgentRunOut(BaseModel):
    """Outbound shape for a single agent run."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    org_id: UUID
    agent_id: str
    agent_name: str
    tier: int
    status: AgentRunStatus
    trigger: AgentRunTrigger
    triggered_by_user_id: UUID | None
    brief: str
    plan: list[AgentRunPlanStep]
    current_step: int
    progress_percent: int
    result: dict[str, Any]
    cost_micro_usd: int
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
