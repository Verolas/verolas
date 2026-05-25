"""Pure execution logic for workflow runs.

The executor decides what should happen to a run given its current state
and a transition trigger. It is pure functions over typed data, free of
DB or HTTP concerns. The DB layer in `runs.py` calls these functions,
applies the returned transitions, and persists the resulting state.

Why pure? Two reasons. First, the executor is heavily unit tested
without spinning up Postgres. Second, when stage 6 introduces real
tool calls for automated nodes, the executor stays the same shape and
the tool-runner just hooks in at a single point.

Today's automated nodes are placeholders. They complete immediately as
soon as they become READY. That keeps the engine end-to-end-runnable
before any vendor adapter exists, which is the whole point of stage 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from verolas_api.workflow.schema import (
    NodeDef,
    NodeKey,
    NodeKind,
    NodeStatus,
    RunStatus,
    TemplateDefinition,
)


@dataclass(frozen=True, slots=True)
class NodeState:
    """Just the runtime fields of a run node that the executor cares about."""

    key: NodeKey
    kind: NodeKind
    status: NodeStatus
    gate_decision: str | None = None
    outputs: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class Transition:
    """One state change the executor is asking the persistence layer to apply.

    Persistence side records an event for every transition, updates the
    node row's status (and gate_decision / outputs when applicable), and
    then re-invokes the executor if the run is still active.
    """

    node_key: NodeKey
    new_status: NodeStatus
    event_type: str
    event_payload: dict[str, Any]
    gate_decision: str | None = None
    outputs: dict[str, Any] | None = None


def compute_initial_node_states(
    definition: TemplateDefinition,
) -> dict[NodeKey, NodeStatus]:
    """Starting status for every node in a fresh run.

    Entry nodes (no inbound edges) start READY because the executor can
    pick them up immediately. Everything else starts PENDING and gets
    promoted as upstream nodes finish.
    """
    entry_set = set(definition.entry_keys)
    return {
        node.key: NodeStatus.READY if node.key in entry_set else NodeStatus.PENDING
        for node in definition.nodes
    }


def advance(definition: TemplateDefinition, nodes: dict[NodeKey, NodeState]) -> list[Transition]:
    """Compute all immediate transitions for the current state.

    Two passes:
    1. Promote PENDING nodes whose upstream nodes are all terminal (and
       non-failed) to READY.
    2. Complete READY automated nodes (stage-2 placeholder behaviour).

    The returned transitions are applied in order. The caller is
    expected to re-invoke advance after applying them, until no more
    transitions emerge or a non-automated READY node blocks progress.
    """
    transitions: list[Transition] = []

    node_by_key: dict[NodeKey, NodeDef] = {n.key: n for n in definition.nodes}
    upstream: dict[NodeKey, list[NodeKey]] = {n.key: [] for n in definition.nodes}
    for edge in definition.edges:
        upstream[edge.to_key].append(edge.from_key)

    # Pass 1: promote PENDING nodes whose upstream are all completed/skipped.
    for node_key, state in nodes.items():
        if state.status is not NodeStatus.PENDING:
            continue
        ups = upstream[node_key]
        if not ups:
            # No inbound edge; if it is still pending, that is a bug. Promote.
            transitions.append(
                Transition(
                    node_key=node_key,
                    new_status=NodeStatus.READY,
                    event_type="node.ready",
                    event_payload={"reason": "entry_node"},
                )
            )
            continue
        if all(nodes[u].status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED) for u in ups):
            transitions.append(
                Transition(
                    node_key=node_key,
                    new_status=NodeStatus.READY,
                    event_type="node.ready",
                    event_payload={"upstream": list(ups)},
                )
            )

    # Pass 2: automated nodes that are READY and have NO tool reference
    # in their params complete immediately as a placeholder. Nodes that
    # specify a tool are left for the runs service to dispatch to a
    # registered adapter; if no adapter is registered for that tool the
    # runs service still falls back to a placeholder completion so the
    # workflow never gets stuck.
    for node_key, state in nodes.items():
        if state.status is not NodeStatus.READY:
            continue
        node_def = node_by_key[node_key]
        if node_def.kind is NodeKind.AUTOMATED and not node_def.params.get("tool"):
            transitions.append(
                Transition(
                    node_key=node_key,
                    new_status=NodeStatus.COMPLETED,
                    event_type="node.completed",
                    event_payload={
                        "reason": "automated_placeholder",
                        "params": dict(node_def.params),
                    },
                )
            )

    return transitions


def apply_manual_completion(
    nodes: dict[NodeKey, NodeState],
    node_key: NodeKey,
    outputs: dict[str, Any] | None = None,
) -> list[Transition]:
    """User marks a MANUAL node done. Validated against current state."""
    state = nodes.get(node_key)
    if state is None:
        raise ExecutorError(f"unknown node {node_key!r}")
    if state.kind is not NodeKind.MANUAL:
        raise ExecutorError(
            f"node {node_key!r} is {state.kind.value}, not manual; cannot mark done"
        )
    if state.status is not NodeStatus.READY:
        raise ExecutorError(
            f"node {node_key!r} is {state.status.value}; only READY nodes can be marked done"
        )
    return [
        Transition(
            node_key=node_key,
            new_status=NodeStatus.COMPLETED,
            event_type="node.completed",
            event_payload={"reason": "manual_done"},
            outputs=outputs,
        )
    ]


def apply_gate_decision(
    nodes: dict[NodeKey, NodeState],
    node_key: NodeKey,
    decision: str,
    note: str | None = None,
) -> list[Transition]:
    """An approver acts on a gate.review or gate.approve node.

    decision must be 'approved' or 'rejected'. An approved gate
    transitions to COMPLETED. A rejected gate transitions to FAILED;
    the run-level effect (whether to fail the entire run or branch back
    to upstream) is decided by the persistence layer based on the
    template, not here.
    """
    state = nodes.get(node_key)
    if state is None:
        raise ExecutorError(f"unknown node {node_key!r}")
    if state.kind not in (NodeKind.GATE_REVIEW, NodeKind.GATE_APPROVE):
        raise ExecutorError(
            f"node {node_key!r} is {state.kind.value}, not a review or approve gate"
        )
    if state.status is not NodeStatus.READY:
        raise ExecutorError(
            f"node {node_key!r} is {state.status.value}; only READY gates accept decisions"
        )
    if decision not in ("approved", "rejected"):
        raise ExecutorError(f"decision must be 'approved' or 'rejected', got {decision!r}")

    if decision == "approved":
        return [
            Transition(
                node_key=node_key,
                new_status=NodeStatus.COMPLETED,
                event_type="gate.approved",
                event_payload={"note": note} if note else {},
                gate_decision="approved",
            )
        ]
    return [
        Transition(
            node_key=node_key,
            new_status=NodeStatus.FAILED,
            event_type="gate.rejected",
            event_payload={"note": note} if note else {},
            gate_decision="rejected",
        )
    ]


def is_run_terminal(nodes: dict[NodeKey, NodeState]) -> bool:
    """All nodes have reached a terminal status (completed / failed / skipped)."""
    return all(
        state.status in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED)
        for state in nodes.values()
    )


def derive_run_status(nodes: dict[NodeKey, NodeState]) -> RunStatus:
    """Project the run-level status from the node states.

    - All nodes completed -> COMPLETED
    - Any node failed and no nodes still progressing -> FAILED
    - Otherwise still running (or paused on a gate)
    """
    statuses = {state.status for state in nodes.values()}

    if NodeStatus.RUNNING in statuses:
        return RunStatus.RUNNING

    blocked = {NodeStatus.PENDING, NodeStatus.READY, NodeStatus.PAUSED}
    if statuses & blocked:
        # Still work to do; if anything READY is a gate, the run is
        # effectively paused on human input, but at the run-status
        # level we still report RUNNING.
        return RunStatus.RUNNING

    if NodeStatus.FAILED in statuses:
        return RunStatus.FAILED

    return RunStatus.COMPLETED


class ExecutorError(ValueError):
    """User-facing 4xx-style error from a workflow operation."""
