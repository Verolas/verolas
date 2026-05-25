"""Tests for the workflow schema and registry validators."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from verolas_api.workflow import registry as registry_module
from verolas_api.workflow.registry import (
    clear_registry_for_tests,
    register_template,
    registered_templates,
)
from verolas_api.workflow.schema import (
    EdgeDef,
    NodeDef,
    NodeKind,
    TemplateDefinition,
    TemplateSpec,
)


def _simple_definition() -> TemplateDefinition:
    return TemplateDefinition(
        nodes=[
            NodeDef(key="start", kind=NodeKind.MANUAL, name="Start"),
            NodeDef(key="end", kind=NodeKind.AUTOMATED, name="End"),
        ],
        edges=[EdgeDef(from_key="start", to_key="end")],
        entry_keys=["start"],
    )


def _spec(slug: str = "demo") -> TemplateSpec:
    return TemplateSpec(
        slug=slug,
        name="Demo",
        description="Demo template.",
        jurisdiction=None,
        project_type=None,
        definition=_simple_definition(),
    )


@pytest.fixture(autouse=True)
def reset_registry() -> Iterator[None]:
    # The hello.py template registers at import time. Clear after each
    # test so we do not leak the demo registration into others.
    yield
    clear_registry_for_tests()


def test_template_definition_round_trip_and_hash_stable() -> None:
    spec = _spec()
    payload = spec.model_dump(mode="json")
    spec_again = TemplateSpec.model_validate(payload)
    assert spec == spec_again
    assert spec.definition.hash() == spec_again.definition.hash()


def test_template_hash_changes_when_node_added() -> None:
    spec_a = _spec()
    nodes = [
        *spec_a.definition.nodes,
        NodeDef(key="extra", kind=NodeKind.MANUAL, name="Extra"),
    ]
    spec_b = TemplateSpec(
        slug="demo",
        name="Demo",
        description=spec_a.description,
        jurisdiction=None,
        project_type=None,
        definition=TemplateDefinition(
            nodes=nodes,
            edges=[
                *spec_a.definition.edges,
                EdgeDef(from_key="end", to_key="extra"),
            ],
            entry_keys=["start"],
        ),
    )
    assert spec_a.definition.hash() != spec_b.definition.hash()


def test_register_template_succeeds_for_valid_graph() -> None:
    register_template(_spec())
    assert [t.slug for t in registered_templates()] == ["demo"]


def test_register_same_definition_twice_is_idempotent() -> None:
    spec = _spec()
    register_template(spec)
    register_template(spec)
    assert len(registered_templates()) == 1


def test_register_different_definition_for_existing_slug_raises() -> None:
    register_template(_spec())
    different = TemplateSpec(
        slug="demo",
        name="Demo",
        description="Different",
        jurisdiction=None,
        project_type=None,
        definition=_simple_definition(),
    )
    with pytest.raises(RuntimeError, match="registered twice"):
        register_template(different)


def test_duplicate_node_keys_rejected() -> None:
    definition = TemplateDefinition(
        nodes=[
            NodeDef(key="x", kind=NodeKind.MANUAL, name="X"),
            NodeDef(key="x", kind=NodeKind.AUTOMATED, name="X2"),
        ],
        edges=[],
        entry_keys=["x"],
    )
    spec = TemplateSpec(
        slug="dup",
        name="Dup",
        description=None,
        jurisdiction=None,
        project_type=None,
        definition=definition,
    )
    with pytest.raises(ValueError, match="duplicate node keys"):
        register_template(spec)


def test_edge_endpoint_must_reference_a_node() -> None:
    definition = TemplateDefinition(
        nodes=[NodeDef(key="a", kind=NodeKind.MANUAL, name="A")],
        edges=[EdgeDef(from_key="a", to_key="ghost")],
        entry_keys=["a"],
    )
    spec = TemplateSpec(
        slug="badedge",
        name="Bad",
        description=None,
        jurisdiction=None,
        project_type=None,
        definition=definition,
    )
    with pytest.raises(ValueError, match="to_key 'ghost'"):
        register_template(spec)


def test_declared_entry_keys_must_match_computed() -> None:
    definition = TemplateDefinition(
        nodes=[
            NodeDef(key="a", kind=NodeKind.MANUAL, name="A"),
            NodeDef(key="b", kind=NodeKind.AUTOMATED, name="B"),
        ],
        edges=[EdgeDef(from_key="a", to_key="b")],
        entry_keys=["b"],  # wrong, b has an inbound edge
    )
    spec = TemplateSpec(
        slug="badentry",
        name="Bad",
        description=None,
        jurisdiction=None,
        project_type=None,
        definition=definition,
    )
    with pytest.raises(ValueError, match="entry_keys"):
        register_template(spec)


def test_cycles_are_rejected() -> None:
    definition = TemplateDefinition(
        nodes=[
            NodeDef(key="a", kind=NodeKind.MANUAL, name="A"),
            NodeDef(key="b", kind=NodeKind.AUTOMATED, name="B"),
        ],
        # a -> b -> a forms a cycle.
        edges=[
            EdgeDef(from_key="a", to_key="b"),
            EdgeDef(from_key="b", to_key="a"),
        ],
        entry_keys=[],
    )
    spec = TemplateSpec(
        slug="cycle",
        name="Cycle",
        description=None,
        jurisdiction=None,
        project_type=None,
        definition=definition,
    )
    with pytest.raises(ValueError, match="cycle"):
        register_template(spec)


def test_self_loop_rejected() -> None:
    definition = TemplateDefinition(
        nodes=[NodeDef(key="a", kind=NodeKind.MANUAL, name="A")],
        edges=[EdgeDef(from_key="a", to_key="a")],
        entry_keys=["a"],
    )
    spec = TemplateSpec(
        slug="loop",
        name="Loop",
        description=None,
        jurisdiction=None,
        project_type=None,
        definition=definition,
    )
    with pytest.raises(ValueError, match="self-loop"):
        register_template(spec)


def test_hello_template_loads_and_validates() -> None:
    # Force a fresh import so register_template runs even if a prior
    # test already imported the module (Python caches imports).
    import importlib
    import sys

    sys.modules.pop("verolas_api.workflow.templates.hello", None)
    importlib.import_module("verolas_api.workflow.templates.hello")
    slugs = [t.slug for t in registered_templates()]
    assert "hello-workflow" in slugs
    hello = next(t for t in registered_templates() if t.slug == "hello-workflow")
    assert {n.key for n in hello.definition.nodes} == {
        "upload_brief",
        "review",
        "done",
    }
    assert hello.definition.entry_keys == ["upload_brief"]
    _ = registry_module
