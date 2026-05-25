"""In-process registry of code-authored workflow templates.

Each template module under `verolas_api.workflow.templates` constructs a
`TemplateSpec` and calls `register_template(spec)` at import time. The
sync layer reads the registry on app startup and upserts rows into
`workflow_templates` + `workflow_template_versions`.

A template can be registered only once per slug; double registration is
a programming error (collision between two files).
"""

from __future__ import annotations

from typing import Final

from verolas_api.workflow.schema import (
    EdgeDef,
    GroupDef,
    NodeDef,
    NodeKey,
    TemplateDefinition,
    TemplateSpec,
)

_TEMPLATES: Final[dict[str, TemplateSpec]] = {}


def register_template(spec: TemplateSpec) -> None:
    """Register a Verolas-authored template. Idempotent within a process."""
    if spec.slug in _TEMPLATES:
        existing = _TEMPLATES[spec.slug]
        if existing == spec:
            return
        raise RuntimeError(
            f"Workflow template slug '{spec.slug}' is registered twice with different definitions."
        )
    _validate(spec)
    _TEMPLATES[spec.slug] = spec


def registered_templates() -> list[TemplateSpec]:
    """Return all registered templates in slug order."""
    return [_TEMPLATES[slug] for slug in sorted(_TEMPLATES)]


def clear_registry_for_tests() -> None:
    """Reset the registry. Tests only."""
    _TEMPLATES.clear()


def validate_definition(
    definition: TemplateDefinition,
    *,
    context: str = "definition",
) -> None:
    """Run the same invariants as register_template on a bare TemplateDefinition.

    Used by document-update paths so a project-scoped graph cannot drift
    into a state that breaks the executor (duplicate keys, dangling
    edges, mismatched entry_keys, cycles, dangling group_key). Pydantic
    only enforces shape; this enforces semantics.
    """
    _validate_graph(context, definition)


def _validate(spec: TemplateSpec) -> None:
    """Validate node keys, edge endpoints, entry keys, and acyclicity."""
    _validate_graph(f"Template '{spec.slug}'", spec.definition)


def _validate_graph(context: str, definition: TemplateDefinition) -> None:
    keys = {node.key for node in definition.nodes}
    if len(keys) != len(definition.nodes):
        raise ValueError(f"{context} has duplicate node keys")

    for edge in definition.edges:
        if edge.from_key not in keys:
            raise ValueError(f"{context} edge from_key '{edge.from_key}' does not match any node")
        if edge.to_key not in keys:
            raise ValueError(f"{context} edge to_key '{edge.to_key}' does not match any node")
        if edge.from_key == edge.to_key:
            raise ValueError(f"{context} has self-loop on '{edge.from_key}'")

    inbound: dict[NodeKey, int] = {key: 0 for key in keys}
    for edge in definition.edges:
        inbound[edge.to_key] += 1

    computed_entries = {key for key, count in inbound.items() if count == 0}
    declared_entries = set(definition.entry_keys)
    if computed_entries != declared_entries:
        raise ValueError(
            f"{context} declared entry_keys "
            f"{sorted(declared_entries)} but graph entries are "
            f"{sorted(computed_entries)}"
        )

    _ensure_acyclic(context, definition.nodes, definition.edges)
    _validate_groups(context, definition.nodes, definition.groups)


def _validate_groups(context: str, nodes: list[NodeDef], groups: list[GroupDef]) -> None:
    """Group keys must be unique, and every node group_key must resolve.

    Groups are pure UI structure (the executor never reads them), so we
    do not constrain how nodes connect across groups. We only enforce
    referential integrity so the canvas does not get a dangling
    group_key it cannot render.
    """
    group_keys = [g.key for g in groups]
    if len(set(group_keys)) != len(group_keys):
        raise ValueError(f"{context} has duplicate group keys")
    known = set(group_keys)
    for node in nodes:
        if node.group_key is not None and node.group_key not in known:
            raise ValueError(
                f"{context} node '{node.key}' references unknown group_key '{node.group_key}'"
            )


def _ensure_acyclic(context: str, nodes: list[NodeDef], edges: list[EdgeDef]) -> None:
    """Kahn's algorithm. We forbid cycles in v1 templates; loops come later."""
    adj: dict[NodeKey, list[NodeKey]] = {n.key: [] for n in nodes}
    indeg: dict[NodeKey, int] = {n.key: 0 for n in nodes}
    for edge in edges:
        adj[edge.from_key].append(edge.to_key)
        indeg[edge.to_key] += 1
    queue = [k for k, d in indeg.items() if d == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for target in adj[current]:
            indeg[target] -= 1
            if indeg[target] == 0:
                queue.append(target)
    if visited != len(nodes):
        raise ValueError(
            f"{context} contains a cycle. Cycles are not supported "
            f"in v1; use a branch.iterate node once that kind is wired."
        )
