"""Pydantic schemas for workflow templates and runs.

The Template + NodeDef + EdgeDef trio is the serialized form that lives
in `workflow_template_versions.definition`. Run-time state mirrors
`workflow_run_nodes` and `workflow_run_events`. We keep these models
strictly compatible with the DB enums declared in the Alembic migration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NodeKind(StrEnum):
    """Execution kinds. Must match values referenced in run_nodes.kind."""

    AUTOMATED = "automated"
    GATE_REVIEW = "gate.review"
    GATE_APPROVE = "gate.approve"
    GATE_SIGNATURE = "gate.signature"
    MANUAL = "manual"
    EXTERNAL_WAIT = "external_wait"
    BRANCH_CONDITION = "branch.condition"
    BRANCH_ITERATE = "branch.iterate"
    SUBMISSION = "submission"
    NOTIFICATION = "notification"


class TemplateSource(StrEnum):
    """Matches the workflow_template_source enum in the migration."""

    CODE = "code"
    UI = "ui"


class RunStatus(StrEnum):
    """Matches workflow_run_status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(StrEnum):
    """Matches workflow_node_status."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


NodeKey = Annotated[
    str,
    Field(
        pattern=r"^[a-z][a-z0-9_]*$",
        min_length=1,
        max_length=64,
        description=(
            "Stable identifier inside a template. Snake case, ASCII. "
            "Stays constant across template versions whenever possible so "
            "diffs are readable."
        ),
    ),
]


class NodeDef(BaseModel):
    """One node in a template definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: NodeKey
    kind: NodeKind
    name: str
    description: str | None = None
    # Free-form parameters consumed by the executor for this node kind.
    # For gate.* nodes, this typically holds {"assignee_role": "..."}.
    # For automated nodes, it holds the tool reference and arguments.
    params: dict[str, Any] = Field(default_factory=dict)


class EdgeDef(BaseModel):
    """A directed edge between two nodes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_key: NodeKey
    to_key: NodeKey
    # Optional condition expression evaluated against run context. For
    # the stage-1 trivial template we do not exercise this; later stages
    # parse it. Left as a string so we do not commit to a syntax yet.
    condition: str | None = None


class TemplateDefinition(BaseModel):
    """The graph payload stored in workflow_template_versions.definition."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[NodeDef]
    edges: list[EdgeDef]
    # entry_keys names the nodes that have no inbound edges and start
    # in the READY state when a run is created. Computed by validators
    # at registration time; persisted so the executor does not need to
    # recompute on every start.
    entry_keys: list[NodeKey]

    def hash(self) -> str:
        """Stable hash of the serialized definition.

        Used by the sync layer to decide whether to mint a new version.
        Sorts keys to keep the hash deterministic across Python runs.
        """
        payload = self.model_dump(mode="json")
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


class TemplateSpec(BaseModel):
    """The full description a registered template emits to the sync layer.

    Distinct from `TemplateDefinition` so we can carry catalog metadata
    (slug, name, jurisdiction) alongside the graph payload.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    name: str
    description: str | None = None
    jurisdiction: str | None = Field(default=None, max_length=8)
    project_type: str | None = Field(default=None, max_length=64)
    definition: TemplateDefinition


# Run-time projections, used by the API layer when surfacing state.


class RunNodeView(BaseModel):
    """API projection of a workflow_run_nodes row."""

    id: UUID
    node_key: str
    kind: NodeKind
    status: NodeStatus
    assignee_user_id: UUID | None = None
    gate_decision: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunView(BaseModel):
    """API projection of a workflow_runs row.

    After stage 4, runs can be rooted in either a Verolas template or a
    project-scoped document. The display name resolves via the source:
    template.name if template-rooted, document.name if doc-rooted.
    """

    id: UUID
    project_id: UUID
    template_id: UUID | None = None
    template_version_id: UUID | None = None
    template_slug: str | None = None
    template_name: str | None = None
    document_id: UUID | None = None
    document_name: str | None = None
    display_name: str
    status: RunStatus
    started_by_user_id: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    nodes: list[RunNodeView] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TemplateView(BaseModel):
    """API projection of a workflow_templates row joined with its active version."""

    id: UUID
    org_id: UUID | None
    slug: str
    name: str
    description: str | None
    jurisdiction: str | None
    project_type: str | None
    source: TemplateSource
    active_version: int
    active_version_id: UUID
    node_count: int
    is_global: bool
    created_at: datetime
    updated_at: datetime


class DocumentView(BaseModel):
    """API projection of a workflow_documents row."""

    id: UUID
    org_id: UUID
    project_id: UUID
    folder: str
    name: str
    description: str | None
    source_template_id: UUID | None
    source_template_version_id: UUID | None
    definition: TemplateDefinition
    node_count: int
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
