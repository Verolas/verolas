"""Pure-function tests for the workflow executor.

No DB. Tests cover state transition logic across the node kinds the
stage-2 surface supports (automated / manual / gate.review /
gate.approve). Branch and iteration kinds are not exercised here; they
land in a later stage.
"""

from __future__ import annotations

import pytest

from verolas_api.workflow.executor import (
    ExecutorError,
    NodeState,
    advance,
    apply_gate_decision,
    apply_manual_completion,
    compute_initial_node_states,
    derive_run_status,
    is_run_terminal,
)
from verolas_api.workflow.schema import (
    EdgeDef,
    NodeDef,
    NodeKind,
    NodeStatus,
    RunStatus,
    TemplateDefinition,
)

# Builders.


def _hello_definition() -> TemplateDefinition:
    return TemplateDefinition(
        nodes=[
            NodeDef(key="upload", kind=NodeKind.MANUAL, name="Upload"),
            NodeDef(key="review", kind=NodeKind.GATE_REVIEW, name="Review"),
            NodeDef(key="done", kind=NodeKind.AUTOMATED, name="Done"),
        ],
        edges=[
            EdgeDef(from_key="upload", to_key="review"),
            EdgeDef(from_key="review", to_key="done"),
        ],
        entry_keys=["upload"],
    )


def _initial_states(
    definition: TemplateDefinition,
) -> dict[str, NodeState]:
    statuses = compute_initial_node_states(definition)
    return {
        n.key: NodeState(key=n.key, kind=n.kind, status=statuses[n.key]) for n in definition.nodes
    }


def _set_state(
    states: dict[str, NodeState],
    key: str,
    *,
    status: NodeStatus | None = None,
    gate_decision: str | None = None,
) -> dict[str, NodeState]:
    old = states[key]
    states[key] = NodeState(
        key=old.key,
        kind=old.kind,
        status=status if status is not None else old.status,
        gate_decision=gate_decision if gate_decision is not None else old.gate_decision,
        outputs=old.outputs,
    )
    return states


# compute_initial_node_states.


def test_initial_state_marks_entry_node_ready() -> None:
    definition = _hello_definition()
    states = compute_initial_node_states(definition)
    assert states["upload"] is NodeStatus.READY
    assert states["review"] is NodeStatus.PENDING
    assert states["done"] is NodeStatus.PENDING


def test_initial_state_handles_parallel_entries() -> None:
    definition = TemplateDefinition(
        nodes=[
            NodeDef(key="a", kind=NodeKind.MANUAL, name="A"),
            NodeDef(key="b", kind=NodeKind.MANUAL, name="B"),
            NodeDef(key="c", kind=NodeKind.AUTOMATED, name="C"),
        ],
        edges=[
            EdgeDef(from_key="a", to_key="c"),
            EdgeDef(from_key="b", to_key="c"),
        ],
        entry_keys=["a", "b"],
    )
    states = compute_initial_node_states(definition)
    assert states["a"] is NodeStatus.READY
    assert states["b"] is NodeStatus.READY
    assert states["c"] is NodeStatus.PENDING


# advance.


def test_advance_on_fresh_run_emits_no_transitions_for_manual_entry() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    # The upload node is manual, READY from start. Advance should not
    # auto-complete it; it should sit waiting for the user.
    transitions = advance(definition, states)
    assert transitions == []


def test_advance_completes_automated_entry_node_immediately() -> None:
    definition = TemplateDefinition(
        nodes=[
            NodeDef(key="auto", kind=NodeKind.AUTOMATED, name="Auto"),
            NodeDef(key="done", kind=NodeKind.AUTOMATED, name="Done"),
        ],
        edges=[EdgeDef(from_key="auto", to_key="done")],
        entry_keys=["auto"],
    )
    states = _initial_states(definition)
    transitions = advance(definition, states)
    assert len(transitions) == 1
    t = transitions[0]
    assert t.node_key == "auto"
    assert t.new_status is NodeStatus.COMPLETED
    assert t.event_type == "node.completed"


def test_advance_promotes_downstream_node_when_upstream_completes() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    states = _set_state(states, "upload", status=NodeStatus.COMPLETED)
    transitions = advance(definition, states)
    keys = {t.node_key for t in transitions}
    assert keys == {"review"}
    assert transitions[0].new_status is NodeStatus.READY


def test_advance_joins_only_when_all_upstream_done() -> None:
    definition = TemplateDefinition(
        nodes=[
            NodeDef(key="a", kind=NodeKind.MANUAL, name="A"),
            NodeDef(key="b", kind=NodeKind.MANUAL, name="B"),
            NodeDef(key="join", kind=NodeKind.AUTOMATED, name="Join"),
        ],
        edges=[
            EdgeDef(from_key="a", to_key="join"),
            EdgeDef(from_key="b", to_key="join"),
        ],
        entry_keys=["a", "b"],
    )
    states = _initial_states(definition)
    # Only a is done.
    states = _set_state(states, "a", status=NodeStatus.COMPLETED)
    transitions = advance(definition, states)
    assert transitions == []

    # Both are done -> join should become READY, then immediately COMPLETED
    # (it is AUTOMATED).
    states = _set_state(states, "b", status=NodeStatus.COMPLETED)
    transitions = advance(definition, states)
    keys = {t.node_key: t.new_status for t in transitions}
    assert keys == {"join": NodeStatus.READY}


# apply_manual_completion.


def test_manual_completion_marks_node_completed() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    transitions = apply_manual_completion(states, "upload", outputs={"file_id": "abc"})
    assert len(transitions) == 1
    t = transitions[0]
    assert t.node_key == "upload"
    assert t.new_status is NodeStatus.COMPLETED
    assert t.outputs == {"file_id": "abc"}
    assert t.event_type == "node.completed"


def test_manual_completion_rejected_for_non_manual_kind() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    # The review node is a gate; should not accept a manual_done call.
    states = _set_state(states, "upload", status=NodeStatus.COMPLETED)
    states = _set_state(states, "review", status=NodeStatus.READY)
    with pytest.raises(ExecutorError, match="not manual"):
        apply_manual_completion(states, "review")


def test_manual_completion_rejected_when_not_ready() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    # Upload is initially READY, mark it COMPLETED so the next attempt fails.
    states = _set_state(states, "upload", status=NodeStatus.COMPLETED)
    with pytest.raises(ExecutorError, match="only READY"):
        apply_manual_completion(states, "upload")


# apply_gate_decision.


def test_gate_approved_completes_node() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    states = _set_state(states, "upload", status=NodeStatus.COMPLETED)
    states = _set_state(states, "review", status=NodeStatus.READY)
    transitions = apply_gate_decision(states, "review", "approved", note="ok")
    assert len(transitions) == 1
    t = transitions[0]
    assert t.node_key == "review"
    assert t.new_status is NodeStatus.COMPLETED
    assert t.gate_decision == "approved"
    assert t.event_type == "gate.approved"
    assert t.event_payload == {"note": "ok"}


def test_gate_rejected_fails_node() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    states = _set_state(states, "upload", status=NodeStatus.COMPLETED)
    states = _set_state(states, "review", status=NodeStatus.READY)
    transitions = apply_gate_decision(states, "review", "rejected")
    assert len(transitions) == 1
    assert transitions[0].new_status is NodeStatus.FAILED
    assert transitions[0].gate_decision == "rejected"


def test_gate_decision_must_be_approved_or_rejected() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    states = _set_state(states, "upload", status=NodeStatus.COMPLETED)
    states = _set_state(states, "review", status=NodeStatus.READY)
    with pytest.raises(ExecutorError, match="'approved' or 'rejected'"):
        apply_gate_decision(states, "review", "maybe")


def test_gate_decision_rejected_for_non_gate_node() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    with pytest.raises(ExecutorError, match="not a review or approve gate"):
        apply_gate_decision(states, "upload", "approved")


# is_run_terminal and derive_run_status.


def test_is_run_terminal_only_when_all_nodes_terminal() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    assert not is_run_terminal(states)
    for key in ("upload", "review", "done"):
        states = _set_state(states, key, status=NodeStatus.COMPLETED)
    assert is_run_terminal(states)


def test_derive_run_status_when_all_completed() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    for key in ("upload", "review", "done"):
        states = _set_state(states, key, status=NodeStatus.COMPLETED)
    assert derive_run_status(states) is RunStatus.COMPLETED


def test_derive_run_status_failed_when_any_node_failed_and_done() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    states = _set_state(states, "upload", status=NodeStatus.COMPLETED)
    states = _set_state(states, "review", status=NodeStatus.FAILED)
    states = _set_state(states, "done", status=NodeStatus.SKIPPED)
    assert derive_run_status(states) is RunStatus.FAILED


def test_derive_run_status_running_while_anything_pending_or_ready() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    assert derive_run_status(states) is RunStatus.RUNNING


# End-to-end driver: imitates what the DB layer's loop does.


def _drive_to_block(
    definition: TemplateDefinition, states: dict[str, NodeState]
) -> dict[str, NodeState]:
    for _ in range(64):
        transitions = advance(definition, states)
        if not transitions:
            return states
        for t in transitions:
            states = _set_state(
                states, t.node_key, status=t.new_status, gate_decision=t.gate_decision
            )
    raise AssertionError("advance did not stabilize")


def test_end_to_end_drive_blocks_at_manual_entry() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    states = _drive_to_block(definition, states)
    # No transitions because upload is manual and READY; user has to act.
    assert states["upload"].status is NodeStatus.READY
    assert states["review"].status is NodeStatus.PENDING


def test_end_to_end_drive_to_completion_with_user_actions() -> None:
    definition = _hello_definition()
    states = _initial_states(definition)
    states = _drive_to_block(definition, states)

    # User marks upload done.
    for t in apply_manual_completion(states, "upload"):
        states = _set_state(states, t.node_key, status=t.new_status)
    states = _drive_to_block(definition, states)
    assert states["review"].status is NodeStatus.READY

    # Reviewer approves the gate.
    for t in apply_gate_decision(states, "review", "approved"):
        states = _set_state(states, t.node_key, status=t.new_status, gate_decision=t.gate_decision)
    states = _drive_to_block(definition, states)

    # The automated terminal node completes immediately after the gate
    # clears.
    assert states["done"].status is NodeStatus.COMPLETED
    assert is_run_terminal(states)
    assert derive_run_status(states) is RunStatus.COMPLETED
