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

from verolas_api.workflow.schema import EdgeDef, NodeDef, NodeKey, TemplateSpec

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


def _validate(spec: TemplateSpec) -> None:
    """Validate node keys, edge endpoints, entry keys, and acyclicity."""
    keys = {node.key for node in spec.definition.nodes}
    if len(keys) != len(spec.definition.nodes):
        raise ValueError(f"Template '{spec.slug}' has duplicate node keys")

    for edge in spec.definition.edges:
        if edge.from_key not in keys:
            raise ValueError(
                f"Template '{spec.slug}' edge from_key '{edge.from_key}' does not match any node"
            )
        if edge.to_key not in keys:
            raise ValueError(
                f"Template '{spec.slug}' edge to_key '{edge.to_key}' does not match any node"
            )
        if edge.from_key == edge.to_key:
            raise ValueError(f"Template '{spec.slug}' has self-loop on '{edge.from_key}'")

    inbound: dict[NodeKey, int] = {key: 0 for key in keys}
    for edge in spec.definition.edges:
        inbound[edge.to_key] += 1

    computed_entries = {key for key, count in inbound.items() if count == 0}
    declared_entries = set(spec.definition.entry_keys)
    if computed_entries != declared_entries:
        raise ValueError(
            f"Template '{spec.slug}' declared entry_keys "
            f"{sorted(declared_entries)} but graph entries are "
            f"{sorted(computed_entries)}"
        )

    _ensure_acyclic(spec.slug, spec.definition.nodes, spec.definition.edges)


def _ensure_acyclic(slug: str, nodes: list[NodeDef], edges: list[EdgeDef]) -> None:
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
            f"Template '{slug}' contains a cycle. Cycles are not supported "
            f"in v1; use a branch.iterate node once that kind is wired."
        )
