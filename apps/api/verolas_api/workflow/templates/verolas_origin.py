"""Verolas template: Origin (greenfield structural concept design).

A four-node template that mirrors the way an AI-assisted concept design
service is sold to firms: the engineer submits a brief, the model
proposes a handful of structural options, the project lead picks one,
and a licensed engineer refines + seals the chosen option.

Designed to be run standalone (output: sealed_concept.pdf that becomes
the input to a downstream LP 4 Statik workflow), or embedded as a sub-
workflow once the engine supports nested templates in a later stage.

SLA labels live as integer params (sla_minutes / sla_business_days) so
the UI can render them as expected-vs-elapsed badges without baking
day numbers into node names.
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
            key="submit_project",
            kind=NodeKind.MANUAL,
            name="Submit project brief",
            description=(
                "Upload the brief, architect plans, code/jurisdiction "
                "targets, and performance constraints. The Verolas Origin "
                "AI generator reads the brief in the next step. Mark this "
                "node done once the upload is complete."
            ),
            params={
                "step": "submit",
                "sla_minutes": 30,
                "expected_outputs": ["brief_text", "jurisdiction", "building_type"],
            },
        ),
        NodeDef(
            key="ai_design",
            kind=NodeKind.AUTOMATED,
            name="AI proposes design options",
            description=(
                "Verolas Origin reads the brief and generates 3 to 5 "
                "structural concept options. Each option includes bay "
                "grid, slab type, primary structure, material, "
                "preliminary load takedown, BoQ estimate, and a "
                "sustainability note. The model is a design assistant; "
                "the engineer remains the responsible designer."
            ),
            params={
                "tool": "verolas.origin.generator",
                "sla_minutes": 5,
            },
        ),
        NodeDef(
            key="select_option",
            kind=NodeKind.GATE_REVIEW,
            name="Select an option",
            description=(
                "Bauherr or project lead picks which option proceeds to "
                "refinement. Approve to confirm the choice (record the "
                "option_id in the note); Reject to send the AI back for "
                "another round."
            ),
            params={
                "assignee_role": "project_lead",
                "sla_business_days": 1,
            },
        ),
        NodeDef(
            key="engineer_refine_seal",
            kind=NodeKind.MANUAL,
            name="Engineer refines and seals",
            description=(
                "Licensed structural engineer (Tragwerksplaner in DE, "
                "PE/SE in US, ingenieur structures in FR) reviews the "
                "selected option, refines geometry and member sizes, and "
                "applies their professional seal or qualified electronic "
                "signature. Output is the sealed concept design ready "
                "for the downstream Statik workflow."
            ),
            params={
                "step": "refine_and_seal",
                "sla_business_days": 5,
                "expected_outputs": ["sealed_concept_pdf_key"],
            },
        ),
    ]

    edges = [
        EdgeDef(from_key="submit_project", to_key="ai_design"),
        EdgeDef(from_key="ai_design", to_key="select_option"),
        EdgeDef(from_key="select_option", to_key="engineer_refine_seal"),
    ]

    definition = TemplateDefinition(
        nodes=nodes,
        edges=edges,
        entry_keys=["submit_project"],
    )

    return TemplateSpec(
        slug="verolas-origin",
        name="Verolas Origin: greenfield concept",
        description=(
            "AI-assisted structural concept design service. Submit a "
            "brief, get 3-5 viable structural options in minutes, pick "
            "one, and a licensed engineer refines and seals it within "
            "the agreed turnaround. The sealed output feeds downstream "
            "Statik workflows."
        ),
        jurisdiction=None,
        project_type="concept",
        definition=definition,
    )


register_template(_build())
