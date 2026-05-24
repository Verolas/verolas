"""Agent run routes under /v1/orgs/{slug}/projects/{project_id}/runs.

Listing and creating runs. Real agent execution lands in a separate
worker; this routes layer owns the run record lifecycle (queued ->
running -> completed/failed) so the UI can render the dashboard and
the run-view page.
"""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict

from verolas_api.agents import AGENTS, lookup
from verolas_api.audit import record_activity
from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.org import DbOrgConn
from verolas_api.middleware import sla_tier
from verolas_api.schemas.agent_run import (
    AgentRunCreate,
    AgentRunOut,
    AgentRunPlanStep,
    AgentRunStatus,
    AgentRunTrigger,
)

router = APIRouter(prefix="/orgs/{org_slug}/projects/{project_id}/runs", tags=["runs"])


class AgentSummary(BaseModel):
    """Catalog entry exposed to the UI for the agents picker."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    tier: int
    blurb: str
    region_tags: list[str]


catalog_router = APIRouter(prefix="/orgs/{org_slug}/agents", tags=["agents"])


@catalog_router.get("/", response_model=list[AgentSummary])
@sla_tier(1)
async def list_agents() -> list[AgentSummary]:
    """The Verolas agent catalog (static for now)."""
    return [
        AgentSummary(
            id=spec.id,
            name=spec.name,
            tier=spec.tier,
            blurb=spec.blurb,
            region_tags=list(spec.region_tags),
        )
        for spec in AGENTS.values()
    ]


@router.get("/", response_model=list[AgentRunOut])
@sla_tier(1)
async def list_runs(
    dep: DbOrgConn,
    project_id: Annotated[UUID, Path()],
) -> list[AgentRunOut]:
    """List agent runs on the URL-scoped project, newest first."""
    conn, _ = dep
    cur = await conn.execute(
        """
        SELECT id, project_id, org_id, agent_id, agent_name, tier, status, trigger,
               triggered_by_user_id, brief, plan, current_step, progress_percent,
               result, cost_micro_usd, queued_at, started_at, finished_at,
               created_at, updated_at
        FROM agent_runs
        WHERE project_id = %s
        ORDER BY created_at DESC
        LIMIT 200
        """,
        (project_id,),
    )
    rows = await cur.fetchall()
    return [_row_to_out(row) for row in rows]


@router.post(
    "/",
    response_model=AgentRunOut,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(1)
async def create_run(
    body: AgentRunCreate,
    dep: DbOrgConn,
    project_id: Annotated[UUID, Path()],
    auth: CurrentAuth,
) -> AgentRunOut:
    """Queue an agent run on the URL-scoped project."""
    _ = auth
    spec = lookup(body.agent_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown agent: {body.agent_id}",
        )
    conn, ctx = dep

    run_id = uuid4()
    plan = [{"label": step, "status": "pending"} for step in spec.default_plan]
    cur = await conn.execute(
        """
        INSERT INTO agent_runs (
            id, project_id, org_id, agent_id, agent_name, tier, status, trigger,
            triggered_by_user_id, brief, plan, current_step, progress_percent
        ) VALUES (%s, %s, %s, %s, %s, %s, 'queued', 'manual', %s, %s, %s::jsonb, 0, 0)
        RETURNING id, project_id, org_id, agent_id, agent_name, tier, status, trigger,
                  triggered_by_user_id, brief, plan, current_step, progress_percent,
                  result, cost_micro_usd, queued_at, started_at, finished_at,
                  created_at, updated_at
        """,
        (
            run_id,
            project_id,
            ctx.organization_id,
            spec.id,
            spec.name,
            spec.tier,
            ctx.user_id,
            body.brief,
            json.dumps(plan),
        ),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Insert returned no row.",
        )

    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="agent.run.queued",
        resource_type="agent_run",
        resource_id=run_id,
        payload={"agent_id": spec.id, "tier": spec.tier, "brief": body.brief[:200]},
    )

    return _row_to_out(row)


@router.get("/{run_id}", response_model=AgentRunOut)
@sla_tier(1)
async def get_run(
    run_id: UUID,
    dep: DbOrgConn,
    project_id: Annotated[UUID, Path()],
) -> AgentRunOut:
    """Fetch a single run by id (scoped by org + project via RLS)."""
    conn, _ = dep
    cur = await conn.execute(
        """
        SELECT id, project_id, org_id, agent_id, agent_name, tier, status, trigger,
               triggered_by_user_id, brief, plan, current_step, progress_percent,
               result, cost_micro_usd, queued_at, started_at, finished_at,
               created_at, updated_at
        FROM agent_runs
        WHERE id = %s AND project_id = %s
        """,
        (run_id, project_id),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return _row_to_out(row)


def _row_to_out(row: Any) -> AgentRunOut:
    plan_raw = row[10] or []
    plan = [AgentRunPlanStep(**step) for step in plan_raw]
    return AgentRunOut(
        id=row[0],
        project_id=row[1],
        org_id=row[2],
        agent_id=row[3],
        agent_name=row[4],
        tier=row[5],
        status=AgentRunStatus(row[6]),
        trigger=AgentRunTrigger(row[7]),
        triggered_by_user_id=row[8],
        brief=row[9],
        plan=plan,
        current_step=row[11],
        progress_percent=row[12],
        result=row[13] or {},
        cost_micro_usd=row[14],
        queued_at=row[15],
        started_at=row[16],
        finished_at=row[17],
        created_at=row[18],
        updated_at=row[19],
    )


__all__: Annotated[list[str], "exported"] = ["router", "catalog_router"]
