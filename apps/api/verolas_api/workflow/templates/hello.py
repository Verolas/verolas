"""Hello Workflow: smoke-test template.

The simplest non-trivial template we can run end to end. Three nodes:

1. `upload_brief`: a manual node where the engineer drops a project brief
   PDF into Documents and marks the step done.
2. `review`: a review gate. A named teammate approves or rejects.
3. `done`: an automated node that closes the run; placeholder until we
   wire real output components.

Exists to validate the data model, the sync layer, the executor's gate
handling, and the UI's run view without any real engineering tool calls.
Once stage 4 lands the DE Statik LP 4 template we deprecate this one
into a "demo" tile in the gallery.
"""

from __future__ import annotations

from verolas_api.workflow.registry import register_template
from verolas_api.workflow.schema import (
    EdgeDef,
    NodeDef,
    NodeKind,
    TemplateDefinition,
    TemplateSpec,
)


def _build() -> TemplateSpec:
    nodes = [
        NodeDef(
            key="upload_brief",
            kind=NodeKind.MANUAL,
            name="Upload project brief",
            description=(
                "Drop the project brief PDF into Documents, then mark "
                "this step done. The brief sets the design intent that "
                "downstream nodes reference."
            ),
            params={"prompt": "Upload brief.pdf into Project Documents."},
        ),
        NodeDef(
            key="review",
            kind=NodeKind.GATE_REVIEW,
            name="Review brief",
            description=(
                "A named teammate confirms the brief is complete enough "
                "to proceed. Reject to send the run back to upload."
            ),
            params={"assignee_role": "project_lead"},
        ),
        NodeDef(
            key="done",
            kind=NodeKind.AUTOMATED,
            name="Close run",
            description=(
                "Placeholder closing node. Records a run completion "
                "event. Replaced by real Output components in later "
                "templates."
            ),
            params={"emit": "run.demo_completed"},
        ),
    ]
    edges = [
        EdgeDef(from_key="upload_brief", to_key="review"),
        EdgeDef(from_key="review", to_key="done"),
    ]
    definition = TemplateDefinition(
        nodes=nodes, edges=edges, entry_keys=["upload_brief"]
    )
    return TemplateSpec(
        slug="hello-workflow",
        name="Hello Workflow",
        description=(
            "Smoke-test template. Three nodes that exercise upload, "
            "review gate, and run completion. Use it to verify a project "
            "can launch a run end to end."
        ),
        jurisdiction=None,
        project_type=None,
        definition=definition,
    )


register_template(_build())
