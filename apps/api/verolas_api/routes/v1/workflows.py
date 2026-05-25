"""Workflow HTTP API.

Three routers:

- `org_workflow_router` at /v1/orgs/{slug}/workflows for org-level
  reads (template gallery).
- `project_workflow_router` at /v1/orgs/{slug}/projects/{id}/workflows
  for project-scoped run lifecycle (create, list, fetch, advance,
  cancel).

The product surfaces these as a single "Workflows" pillar; the split
is purely about whose RLS context is needed and which path segment
makes sense in URL form.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from verolas_api.dependencies.org import DbOrgConn
from verolas_api.middleware import sla_tier
from verolas_api.workflow import runs as runs_service
from verolas_api.workflow.executor import ExecutorError
from verolas_api.workflow.runs import (
    RunNotFound,
    TemplateNotFound,
    WorkflowError,
)
from verolas_api.workflow.schema import RunView, TemplateView

org_workflow_router = APIRouter(
    prefix="/orgs/{org_slug}/workflows",
    tags=["workflows"],
)
project_workflow_router = APIRouter(
    prefix="/orgs/{org_slug}/projects/{project_id}/workflows",
    tags=["workflows"],
)


# Request bodies.


class WorkflowRunCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_slug: str = Field(min_length=1, max_length=64)


class WorkflowGateDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class WorkflowManualDoneBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outputs: dict[str, object] | None = None


class WorkflowNodeAdvanceBody(BaseModel):
    """Union of node-kind-specific actions.

    Exactly one of `gate` or `manual` should be populated, matching the
    node's kind. Routes validate this and dispatch accordingly.
    """

    model_config = ConfigDict(extra="forbid")

    gate: WorkflowGateDecisionBody | None = None
    manual: WorkflowManualDoneBody | None = None


# Helpers.


def _project_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id must be a UUID.",
        ) from exc


# Org-level routes.


@org_workflow_router.get("/templates", response_model=list[TemplateView])
@sla_tier(1)
async def list_workflow_templates(
    deps: DbOrgConn,
    jurisdiction: Annotated[str | None, Query(max_length=8)] = None,
) -> list[TemplateView]:
    """List templates visible to the caller's org plus Verolas globals."""
    conn, _ = deps
    return await runs_service.list_templates(conn, jurisdiction=jurisdiction)


# Project-level routes.


@project_workflow_router.post(
    "/runs",
    response_model=RunView,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(1)
async def create_workflow_run(
    project_id: Annotated[str, Path()],
    body: WorkflowRunCreateBody,
    deps: DbOrgConn,
) -> RunView:
    """Create a run for the project from a template slug.

    Runs the executor inline so automated entry nodes complete before
    the response. The returned RunView reflects post-inline state.
    """
    conn, ctx = deps
    pid = _project_id(project_id)
    try:
        return await runs_service.create_run(
            conn,
            org_id=ctx.organization_id,
            project_id=pid,
            template_slug=body.template_slug,
            started_by_user_id=ctx.user_id,
        )
    except TemplateNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@project_workflow_router.get("/runs", response_model=list[RunView])
@sla_tier(1)
async def list_workflow_runs(
    project_id: Annotated[str, Path()],
    deps: DbOrgConn,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RunView]:
    """List recent runs on this project."""
    conn, _ = deps
    pid = _project_id(project_id)
    return await runs_service.list_runs_for_project(conn, pid, limit=limit)


@project_workflow_router.get(
    "/runs/{run_id}",
    response_model=RunView,
)
@sla_tier(1)
async def get_workflow_run(
    project_id: Annotated[str, Path()],
    run_id: Annotated[UUID, Path()],
    deps: DbOrgConn,
) -> RunView:
    """Fetch a single run with its node list."""
    conn, _ = deps
    _ = _project_id(project_id)
    try:
        return await runs_service.get_run(conn, run_id=run_id)
    except RunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@project_workflow_router.post(
    "/runs/{run_id}/nodes/{node_key}/advance",
    response_model=RunView,
)
@sla_tier(1)
async def advance_workflow_node(
    project_id: Annotated[str, Path()],
    run_id: Annotated[UUID, Path()],
    node_key: Annotated[str, Path(min_length=1, max_length=64)],
    body: WorkflowNodeAdvanceBody,
    deps: DbOrgConn,
) -> RunView:
    """Advance a single node. Body shape depends on the node kind:

    - For gate.review or gate.approve: include `gate: {decision, note}`.
    - For manual: include `manual: {outputs}` (outputs optional).
    """
    conn, ctx = deps
    _ = _project_id(project_id)

    if (body.gate is None) == (body.manual is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Body must include exactly one of `gate` or `manual`.",
        )

    try:
        if body.gate is not None:
            return await runs_service.submit_gate_decision(
                conn,
                org_id=ctx.organization_id,
                run_id=run_id,
                node_key=node_key,
                decision=body.gate.decision,
                note=body.gate.note,
                actor_user_id=ctx.user_id,
            )
        assert body.manual is not None
        return await runs_service.mark_manual_done(
            conn,
            org_id=ctx.organization_id,
            run_id=run_id,
            node_key=node_key,
            outputs=body.manual.outputs,
            actor_user_id=ctx.user_id,
        )
    except RunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ExecutorError, WorkflowError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@project_workflow_router.post("/runs/{run_id}/cancel", response_model=RunView)
@sla_tier(1)
async def cancel_workflow_run(
    project_id: Annotated[str, Path()],
    run_id: Annotated[UUID, Path()],
    deps: DbOrgConn,
) -> RunView:
    """Cancel a run. Non-terminal nodes are marked skipped."""
    conn, ctx = deps
    _ = _project_id(project_id)
    try:
        return await runs_service.cancel_run(
            conn,
            org_id=ctx.organization_id,
            run_id=run_id,
            actor_user_id=ctx.user_id,
        )
    except RunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
