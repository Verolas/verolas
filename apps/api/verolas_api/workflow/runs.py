"""Database operations for workflow templates and runs.

Stage-2 surface: list templates, create a run, fetch a run, advance a
manual node, submit a gate decision, cancel a run. Every state change
goes through the executor in `executor.py`, applies the returned
transitions inside a single transaction, and re-advances until the run
either reaches a terminal status or blocks on human input.

The DB layer is RLS-aware. Every connection is expected to have org
tenancy set via the `db_org_conn` dependency. Template SELECTs return
both global rows (org_id NULL) and the caller's org rows; writes are
restricted to the caller's org by the policies declared in the
workflow_engine migration.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from verolas_storage import PresignedUrlService

from verolas_api.settings import Settings
from verolas_api.workflow.adapters import get_adapter
from verolas_api.workflow.adapters.base import AdapterContext
from verolas_api.workflow.executor import (
    NodeState,
    Transition,
    advance,
    apply_gate_decision,
    apply_manual_completion,
    compute_initial_node_states,
    derive_run_status,
    is_run_terminal,
)
from verolas_api.workflow.schema import (
    NodeKey,
    NodeKind,
    NodeStatus,
    RunNodeView,
    RunStatus,
    RunView,
    TemplateDefinition,
    TemplateSource,
    TemplateView,
)


class WorkflowError(ValueError):
    """User-facing workflow-layer error; routes translate to 4xx."""


class TemplateNotFound(WorkflowError):
    pass


class RunNotFound(WorkflowError):
    pass


async def list_templates(
    conn: AsyncConnection, jurisdiction: str | None = None
) -> list[TemplateView]:
    """List Verolas-global and caller-org templates visible under RLS."""
    sql = """
        SELECT
            t.id, t.org_id, t.slug, t.name, t.description,
            t.jurisdiction, t.project_type, t.source,
            v.version, v.id AS active_version_id,
            jsonb_array_length(v.definition->'nodes') AS node_count,
            t.created_at, t.updated_at
        FROM workflow_templates t
        JOIN workflow_template_versions v
          ON v.template_id = t.id AND v.is_active
        WHERE (%s::text IS NULL OR t.jurisdiction = %s)
        ORDER BY (t.org_id IS NULL) DESC, t.jurisdiction NULLS FIRST, t.name
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(sql, (jurisdiction, jurisdiction))
        rows = await cur.fetchall()
    return [
        TemplateView(
            id=row["id"],
            org_id=row["org_id"],
            slug=row["slug"],
            name=row["name"],
            description=row["description"],
            jurisdiction=row["jurisdiction"],
            project_type=row["project_type"],
            source=TemplateSource(row["source"]),
            active_version=row["version"],
            active_version_id=row["active_version_id"],
            node_count=row["node_count"],
            is_global=row["org_id"] is None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


async def _resolve_template_by_slug(
    conn: AsyncConnection, slug: str
) -> tuple[UUID, UUID, TemplateDefinition]:
    """Find the active version of a template by slug. Returns IDs + definition."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT t.id AS template_id, v.id AS version_id, v.definition
            FROM workflow_templates t
            JOIN workflow_template_versions v
              ON v.template_id = t.id AND v.is_active
            WHERE t.slug = %s
            LIMIT 1
            """,
            (slug,),
        )
        row = await cur.fetchone()
    if row is None:
        raise TemplateNotFound(f"template {slug!r} not found")
    definition = TemplateDefinition.model_validate(row["definition"])
    return row["template_id"], row["version_id"], definition


async def create_run(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    project_id: UUID,
    template_slug: str,
    started_by_user_id: UUID,
    storage: PresignedUrlService | None = None,
    settings: Settings | None = None,
) -> RunView:
    """Create a new run for `project_id` from the named template.

    Hydrates the per-node rows, emits the run.started event, then runs
    the executor inline so any automated entry nodes complete before
    the API returns. The resulting RunView captures the state after
    the inline pass.
    """
    template_id, version_id, definition = await _resolve_template_by_slug(conn, template_slug)

    initial = compute_initial_node_states(definition)

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO workflow_runs (
                org_id, project_id, template_id, template_version_id,
                status, started_by_user_id, started_at
            )
            VALUES (%s, %s, %s, %s, 'running', %s, now())
            RETURNING id, created_at, updated_at, started_at
            """,
            (org_id, project_id, template_id, version_id, started_by_user_id),
        )
        run_row = await cur.fetchone()
        assert run_row is not None
        run_id = run_row["id"]

        for node_def in definition.nodes:
            await cur.execute(
                """
                INSERT INTO workflow_run_nodes (
                    org_id, run_id, node_key, kind, status, params
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    org_id,
                    run_id,
                    node_def.key,
                    node_def.kind.value,
                    initial[node_def.key].value,
                    json.dumps(dict(node_def.params)),
                ),
            )

        await _emit_event(
            cur,
            org_id=org_id,
            run_id=run_id,
            node_id=None,
            event_type="run.started",
            payload={
                "template_slug": template_slug,
                "template_version_id": str(version_id),
            },
            actor_user_id=started_by_user_id,
        )

    await _advance_until_blocked(
        conn,
        org_id=org_id,
        project_id=project_id,
        run_id=run_id,
        actor_user_id=started_by_user_id,
        storage=storage,
        settings=settings,
    )
    return await get_run(conn, run_id=run_id)


async def create_run_from_document(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    project_id: UUID,
    document_id: UUID,
    started_by_user_id: UUID,
    storage: PresignedUrlService | None = None,
    settings: Settings | None = None,
) -> RunView:
    """Create a run from a project-scoped workflow document.

    The document's current definition is snapshotted onto the run row
    (definition_snapshot) so the run remains immutable if the document
    is later edited. No template_version_id is set; the executor reads
    the snapshot.
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT id, definition FROM workflow_documents WHERE id = %s
            """,
            (document_id,),
        )
        doc_row = await cur.fetchone()
    if doc_row is None:
        raise RunNotFound(f"document {document_id} not found")
    definition = TemplateDefinition.model_validate(doc_row["definition"])

    if not definition.nodes:
        raise WorkflowError("document has no nodes; nothing to run")

    initial = compute_initial_node_states(definition)
    definition_payload = json.dumps(definition.model_dump(mode="json"))

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            INSERT INTO workflow_runs (
                org_id, project_id, document_id, definition_snapshot,
                status, started_by_user_id, started_at
            )
            VALUES (%s, %s, %s, %s::jsonb, 'running', %s, now())
            RETURNING id, created_at, updated_at, started_at
            """,
            (
                org_id,
                project_id,
                document_id,
                definition_payload,
                started_by_user_id,
            ),
        )
        run_row = await cur.fetchone()
        assert run_row is not None
        run_id = run_row["id"]

        for node_def in definition.nodes:
            await cur.execute(
                """
                INSERT INTO workflow_run_nodes (
                    org_id, run_id, node_key, kind, status, params
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    org_id,
                    run_id,
                    node_def.key,
                    node_def.kind.value,
                    initial[node_def.key].value,
                    json.dumps(dict(node_def.params)),
                ),
            )

        await _emit_event(
            cur,
            org_id=org_id,
            run_id=run_id,
            node_id=None,
            event_type="run.started",
            payload={"document_id": str(document_id)},
            actor_user_id=started_by_user_id,
        )

    await _advance_until_blocked(
        conn,
        org_id=org_id,
        project_id=project_id,
        run_id=run_id,
        actor_user_id=started_by_user_id,
        storage=storage,
        settings=settings,
    )
    return await get_run(conn, run_id=run_id)


async def get_run(conn: AsyncConnection, run_id: UUID) -> RunView:
    """Fetch a run with its node list. Raises RunNotFound if missing.

    Runs may be rooted in either a Verolas template or a project document.
    LEFT JOIN both; the route layer resolves the display name from
    whichever side is populated.
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT r.id, r.project_id, r.template_id, r.template_version_id,
                   r.document_id,
                   r.status, r.started_by_user_id, r.started_at, r.completed_at,
                   r.created_at, r.updated_at,
                   t.slug AS template_slug, t.name AS template_name,
                   d.name AS document_name
            FROM workflow_runs r
            LEFT JOIN workflow_templates t ON t.id = r.template_id
            LEFT JOIN workflow_documents d ON d.id = r.document_id
            WHERE r.id = %s
            """,
            (run_id,),
        )
        run_row = await cur.fetchone()
        if run_row is None:
            raise RunNotFound(f"run {run_id} not found")

        await cur.execute(
            """
            SELECT id, node_key, kind, status, assignee_user_id, gate_decision,
                   inputs, outputs, params, error, started_at, completed_at
            FROM workflow_run_nodes
            WHERE run_id = %s
            ORDER BY created_at
            """,
            (run_id,),
        )
        node_rows = await cur.fetchall()

    nodes = [
        RunNodeView(
            id=row["id"],
            node_key=row["node_key"],
            kind=NodeKind(row["kind"]),
            status=NodeStatus(row["status"]),
            assignee_user_id=row["assignee_user_id"],
            gate_decision=row["gate_decision"],
            inputs=row["inputs"] or {},
            outputs=row["outputs"] or {},
            params=row["params"] or {},
            error=row["error"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
        for row in node_rows
    ]
    display_name = run_row["document_name"] or run_row["template_name"] or "Workflow run"
    return RunView(
        id=run_row["id"],
        project_id=run_row["project_id"],
        template_id=run_row["template_id"],
        template_version_id=run_row["template_version_id"],
        template_slug=run_row["template_slug"],
        template_name=run_row["template_name"],
        document_id=run_row["document_id"],
        document_name=run_row["document_name"],
        display_name=display_name,
        status=RunStatus(run_row["status"]),
        started_by_user_id=run_row["started_by_user_id"],
        started_at=run_row["started_at"],
        completed_at=run_row["completed_at"],
        nodes=nodes,
        created_at=run_row["created_at"],
        updated_at=run_row["updated_at"],
    )


async def list_runs_for_project(
    conn: AsyncConnection, project_id: UUID, *, limit: int = 50
) -> list[RunView]:
    """List the most recent runs for a project. Ordered newest first."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT id FROM workflow_runs
            WHERE project_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (project_id, limit),
        )
        ids = [row["id"] for row in await cur.fetchall()]
    out: list[RunView] = []
    for run_id in ids:
        out.append(await get_run(conn, run_id=run_id))
    return out


async def mark_manual_done(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    run_id: UUID,
    node_key: str,
    actor_user_id: UUID,
    outputs: dict[str, Any] | None = None,
    storage: PresignedUrlService | None = None,
    settings: Settings | None = None,
    project_id: UUID | None = None,
) -> RunView:
    """Mark a MANUAL node done, then re-advance the run."""
    _definition, states = await _load_run_state(conn, run_id)
    transitions = apply_manual_completion(states, node_key, outputs=outputs)
    await _apply_transitions(
        conn,
        org_id=org_id,
        run_id=run_id,
        transitions=transitions,
        actor_user_id=actor_user_id,
    )
    pid = project_id or await _project_id_for_run(conn, run_id)
    await _advance_until_blocked(
        conn,
        org_id=org_id,
        project_id=pid,
        run_id=run_id,
        actor_user_id=actor_user_id,
        storage=storage,
        settings=settings,
    )
    return await get_run(conn, run_id=run_id)


async def submit_gate_decision(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    run_id: UUID,
    node_key: str,
    decision: str,
    note: str | None,
    actor_user_id: UUID,
    storage: PresignedUrlService | None = None,
    settings: Settings | None = None,
    project_id: UUID | None = None,
) -> RunView:
    """Process an approve/reject decision on a gate node."""
    _, states = await _load_run_state(conn, run_id)
    transitions = apply_gate_decision(states, node_key, decision, note=note)
    await _apply_transitions(
        conn,
        org_id=org_id,
        run_id=run_id,
        transitions=transitions,
        actor_user_id=actor_user_id,
    )
    if decision == "rejected":
        # Today a rejected gate fails the whole run. Branch-back-to-
        # upstream policies arrive when branch.condition lands.
        await _finalize_run_status(
            conn,
            run_id=run_id,
            org_id=org_id,
            actor_user_id=actor_user_id,
            forced=RunStatus.FAILED,
        )
    else:
        pid = project_id or await _project_id_for_run(conn, run_id)
        await _advance_until_blocked(
            conn,
            org_id=org_id,
            project_id=pid,
            run_id=run_id,
            actor_user_id=actor_user_id,
            storage=storage,
            settings=settings,
        )
    return await get_run(conn, run_id=run_id)


async def cancel_run(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    run_id: UUID,
    actor_user_id: UUID,
) -> RunView:
    """Mark the run cancelled. Skip any non-terminal nodes."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            UPDATE workflow_run_nodes
            SET status = 'skipped',
                completed_at = COALESCE(completed_at, now())
            WHERE run_id = %s
              AND status NOT IN ('completed', 'failed', 'skipped')
            RETURNING id, node_key
            """,
            (run_id,),
        )
        skipped = await cur.fetchall()
        for row in skipped:
            await _emit_event(
                cur,
                org_id=org_id,
                run_id=run_id,
                node_id=row["id"],
                event_type="node.skipped",
                payload={"reason": "run_cancelled", "node_key": row["node_key"]},
                actor_user_id=actor_user_id,
            )
        await cur.execute(
            """
            UPDATE workflow_runs
            SET status = 'cancelled', completed_at = now()
            WHERE id = %s
            """,
            (run_id,),
        )
        await _emit_event(
            cur,
            org_id=org_id,
            run_id=run_id,
            node_id=None,
            event_type="run.cancelled",
            payload={},
            actor_user_id=actor_user_id,
        )
    return await get_run(conn, run_id=run_id)


async def _advance_until_blocked(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    project_id: UUID,
    run_id: UUID,
    actor_user_id: UUID,
    storage: PresignedUrlService | None = None,
    settings: Settings | None = None,
) -> None:
    """Drive the run forward until it blocks on human input or completes.

    Each loop iteration:
    1. Dispatches adapters for any READY automated nodes whose
       `params.tool` matches a registered adapter. Adapters can either
       complete the node (status=completed, outputs recorded) or fail
       it (status=failed, error recorded).
    2. Calls the pure executor's `advance` to promote downstream PENDING
       nodes whose upstream just completed, and to placeholder-complete
       any AUTOMATED node that has no `tool` param.

    The loop breaks when neither step produced transitions. Bounded
    iteration so a buggy template cannot infinite-loop.
    """
    for _ in range(1024):
        # Step 1: adapter dispatch.
        dispatch_transitions = await _dispatch_ready_adapters(
            conn,
            org_id=org_id,
            project_id=project_id,
            run_id=run_id,
            storage=storage,
            settings=settings,
        )
        if dispatch_transitions:
            await _apply_transitions(
                conn,
                org_id=org_id,
                run_id=run_id,
                transitions=dispatch_transitions,
                actor_user_id=actor_user_id,
            )

        # Step 2: pure executor pass.
        definition, states = await _load_run_state(conn, run_id)
        transitions = advance(definition, states)
        if transitions:
            await _apply_transitions(
                conn,
                org_id=org_id,
                run_id=run_id,
                transitions=transitions,
                actor_user_id=actor_user_id,
            )

        if not dispatch_transitions and not transitions:
            break

    await _finalize_run_status(conn, run_id=run_id, org_id=org_id, actor_user_id=actor_user_id)


async def _dispatch_ready_adapters(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    project_id: UUID,
    run_id: UUID,
    storage: PresignedUrlService | None,
    settings: Settings | None = None,
) -> list[Transition]:
    """Run any registered adapters for READY automated nodes.

    For each such node:
    - If `params.tool` is unset, skip (the executor placeholder pass
      will handle it).
    - If `params.tool` is set but no adapter is registered, emit a
      placeholder completion with an event noting the missing adapter.
    - If a registered adapter exists, gather upstream node outputs and
      invoke `adapter.run(ctx, inputs)`. Translate the result into a
      completed or failed transition.

    Returns the list of transitions to apply; the caller emits them via
    `_apply_transitions` and re-loads run state before the next pass.
    """
    definition, states = await _load_run_state(conn, run_id)
    transitions: list[Transition] = []

    # Build upstream-key lookup once.
    upstream_keys: dict[NodeKey, list[NodeKey]] = {n.key: [] for n in definition.nodes}
    for edge in definition.edges:
        upstream_keys[edge.to_key].append(edge.from_key)

    # Map node_key -> NodeDef for params + lookups.
    node_def_by_key = {n.key: n for n in definition.nodes}

    # Load all completed-or-similar nodes' outputs in one query so we
    # can hand them to adapters as inputs.
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT id, node_key, status, outputs FROM workflow_run_nodes
            WHERE run_id = %s
            """,
            (run_id,),
        )
        rows = await cur.fetchall()

    outputs_by_key = {r["node_key"]: (r["outputs"] or {}) for r in rows}
    node_id_by_key = {r["node_key"]: r["id"] for r in rows}

    for node_key, state in states.items():
        if state.status is not NodeStatus.READY:
            continue
        if state.kind is not NodeKind.AUTOMATED:
            continue
        node_def = node_def_by_key[node_key]
        tool = node_def.params.get("tool")
        if not tool:
            # Pure executor placeholder path; nothing to dispatch.
            continue

        adapter = get_adapter(tool)
        if adapter is None:
            transitions.append(
                Transition(
                    node_key=node_key,
                    new_status=NodeStatus.COMPLETED,
                    event_type="node.completed",
                    event_payload={
                        "reason": "adapter_missing_placeholder",
                        "tool": tool,
                    },
                )
            )
            continue

        # Run the adapter. Inputs are upstream node outputs by node_key.
        inputs = {ukey: outputs_by_key.get(ukey, {}) for ukey in upstream_keys[node_key]}
        ctx = AdapterContext(
            org_id=org_id,
            project_id=project_id,
            run_id=run_id,
            node_id=node_id_by_key[node_key],
            node_key=node_key,
            params=dict(node_def.params),
            storage=storage,
            settings=settings,
        )
        try:
            result = await adapter.run(ctx, inputs)
        except Exception as exc:
            transitions.append(
                Transition(
                    node_key=node_key,
                    new_status=NodeStatus.FAILED,
                    event_type="node.failed",
                    event_payload={"tool": tool, "exception": str(exc)},
                )
            )
            continue

        if result.succeeded:
            payload = {
                "tool": tool,
                "artifacts": [
                    {
                        "storage_key": a.storage_key,
                        "content_type": a.content_type,
                        "size_bytes": a.size_bytes,
                        "label": a.label,
                    }
                    for a in result.artifacts
                ],
            }
            transitions.append(
                Transition(
                    node_key=node_key,
                    new_status=NodeStatus.COMPLETED,
                    event_type="node.completed",
                    event_payload=payload,
                    outputs=result.outputs,
                )
            )
        else:
            transitions.append(
                Transition(
                    node_key=node_key,
                    new_status=NodeStatus.FAILED,
                    event_type="node.failed",
                    event_payload={"tool": tool, "error": result.error},
                )
            )

    return transitions


async def _project_id_for_run(conn: AsyncConnection, run_id: UUID) -> UUID:
    """Resolve the project_id for a run. Used by code paths that did not
    receive it explicitly (mark_manual_done, submit_gate_decision)."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT project_id FROM workflow_runs WHERE id = %s",
            (run_id,),
        )
        row = await cur.fetchone()
    if row is None:
        raise RunNotFound(f"run {run_id} not found")
    pid = row["project_id"]
    assert isinstance(pid, UUID)
    return pid


async def _finalize_run_status(
    conn: AsyncConnection,
    *,
    run_id: UUID,
    org_id: UUID,
    actor_user_id: UUID | None,
    forced: RunStatus | None = None,
) -> None:
    """Set the run-level status based on its nodes, emit a terminal event if so."""
    _, states = await _load_run_state(conn, run_id)
    if forced is not None:
        new_status = forced
    elif is_run_terminal(states):
        new_status = derive_run_status(states)
    else:
        new_status = RunStatus.RUNNING

    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE workflow_runs
            SET status = %s,
                completed_at = CASE
                    WHEN %s IN ('completed','failed','cancelled')
                    THEN COALESCE(completed_at, now())
                    ELSE completed_at
                END
            WHERE id = %s
              AND status != %s
            """,
            (new_status.value, new_status.value, run_id, new_status.value),
        )
        if cur.rowcount > 0 and new_status in (
            RunStatus.COMPLETED,
            RunStatus.FAILED,
        ):
            await _emit_event_lowlevel(
                cur,
                org_id=org_id,
                run_id=run_id,
                node_id=None,
                event_type=f"run.{new_status.value}",
                payload={},
                actor_user_id=actor_user_id,
            )


async def _load_run_state(
    conn: AsyncConnection, run_id: UUID
) -> tuple[TemplateDefinition, dict[NodeKey, NodeState]]:
    """Pull the workflow definition and per-node runtime state from the DB.

    The definition source depends on the run's root: template-rooted runs
    use the pinned template version; document-rooted runs use the
    snapshot taken at run-create time. COALESCE picks whichever is set.
    """
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT COALESCE(v.definition, r.definition_snapshot) AS definition
            FROM workflow_runs r
            LEFT JOIN workflow_template_versions v
              ON v.id = r.template_version_id
            WHERE r.id = %s
            """,
            (run_id,),
        )
        row = await cur.fetchone()
        if row is None or row["definition"] is None:
            raise RunNotFound(f"run {run_id} not found")
        definition = TemplateDefinition.model_validate(row["definition"])

        await cur.execute(
            """
            SELECT node_key, kind, status, gate_decision, outputs
            FROM workflow_run_nodes
            WHERE run_id = %s
            """,
            (run_id,),
        )
        node_rows = await cur.fetchall()

    states: dict[NodeKey, NodeState] = {}
    for n in node_rows:
        states[n["node_key"]] = NodeState(
            key=n["node_key"],
            kind=NodeKind(n["kind"]),
            status=NodeStatus(n["status"]),
            gate_decision=n["gate_decision"],
            outputs=n["outputs"],
        )
    return definition, states


async def _apply_transitions(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    run_id: UUID,
    transitions: list[Transition],
    actor_user_id: UUID | None,
) -> None:
    """Apply executor-emitted transitions to the DB. One event per transition."""
    if not transitions:
        return
    async with conn.cursor(row_factory=dict_row) as cur:
        for t in transitions:
            extra_sql = ""
            params: list[Any] = [t.new_status.value]
            if t.gate_decision is not None:
                extra_sql += ", gate_decision = %s"
                params.append(t.gate_decision)
            if t.outputs is not None:
                extra_sql += ", outputs = %s::jsonb"
                params.append(json.dumps(t.outputs))
            if t.new_status is NodeStatus.RUNNING:
                extra_sql += ", started_at = COALESCE(started_at, now())"
            if t.new_status in (
                NodeStatus.COMPLETED,
                NodeStatus.FAILED,
                NodeStatus.SKIPPED,
            ):
                extra_sql += (
                    ", started_at = COALESCE(started_at, now())"
                    ", completed_at = COALESCE(completed_at, now())"
                )

            params.extend([run_id, t.node_key])
            await cur.execute(
                f"""
                UPDATE workflow_run_nodes
                SET status = %s {extra_sql}
                WHERE run_id = %s AND node_key = %s
                RETURNING id
                """,
                params,
            )
            row = await cur.fetchone()
            assert row is not None, f"node {t.node_key} not found for transition"
            node_id = row["id"]

            await _emit_event(
                cur,
                org_id=org_id,
                run_id=run_id,
                node_id=node_id,
                event_type=t.event_type,
                payload=t.event_payload,
                actor_user_id=actor_user_id,
            )


async def _emit_event(
    cur: Any,
    *,
    org_id: UUID,
    run_id: UUID,
    node_id: UUID | None,
    event_type: str,
    payload: dict[str, Any],
    actor_user_id: UUID | None,
) -> None:
    """Append one row to workflow_run_events."""
    await cur.execute(
        """
        INSERT INTO workflow_run_events
            (org_id, run_id, node_id, event_type, payload, actor_user_id)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s)
        """,
        (org_id, run_id, node_id, event_type, json.dumps(payload), actor_user_id),
    )


# Same signature, kept under a different name so the type checker
# treats it as the explicit "this is a non-dict_row cursor" variant
# used by _finalize_run_status.
_emit_event_lowlevel = _emit_event
