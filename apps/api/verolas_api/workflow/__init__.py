"""Verolas Workflow engine.

A workflow is a directed graph of nodes that together carry a structural
engineering job from contract to handover. See the workflow bible for
the product narrative and country templates.

This package implements:

- `schema`: the Pydantic models for a Template, NodeDef, EdgeDef, plus
  the runtime state types (RunNode, RunEvent).
- `registry`: in-process registry of code-authored templates. Each
  template module under `verolas_api.workflow.templates` calls
  `register_template(...)` at import time.
- `sync`: at app startup, upsert the in-process registry into Postgres.
  New versions are minted only when the definition hash changes, so a
  no-op deploy produces no new row.
- `templates/`: the canonical Verolas-authored templates, one per file.

Templates are authored in code (this package). Firms can fork a code
template into a firm-owned template stored entirely in the DB. The
runtime never mutates a code-authored row; it only appends versions.

Call `bootstrap_workflow_templates()` once at app startup to import
every template module so the registrations run.
"""

from __future__ import annotations


def bootstrap_workflow_templates() -> None:
    """Import every template module so its registration runs."""
    from verolas_api.workflow.templates import (
        de_statik_genehmigungsplanung as _de_statik,
    )
    from verolas_api.workflow.templates import (
        hello as _hello,
    )

    _ = (_de_statik, _hello)


__all__ = ["bootstrap_workflow_templates"]
