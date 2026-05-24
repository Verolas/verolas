"""The Verolas agent catalog.

Each entry describes one agent the platform can run on a project. The
catalog is in code (not the DB) because agents are first-class product
units shipped as part of the app release, not user-configurable rows.
A future Enterprise tier may let firms register custom agents on top.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """Static description of one agent in the catalog."""

    id: str
    name: str
    tier: int
    blurb: str
    region_tags: tuple[str, ...] = ()
    default_plan: tuple[str, ...] = ()


AGENTS: dict[str, AgentSpec] = {
    spec.id: spec
    for spec in (
        # Tier 3 — Co-pilot (judgment-augmented)
        AgentSpec(
            id="structural-calc",
            name="Structural Calc Agent",
            tier=3,
            blurb="ULS + SLS calc package per EN 1990-1999 with code-compliance summary.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
            default_plan=(
                "Validate inputs and load cases",
                "Resolve load combinations under active code",
                "Run member sizing and capacity checks",
                "Run punching shear and serviceability checks",
                "Assemble calc package and code-compliance matrix",
                "Sign artefacts and append to audit chain",
            ),
        ),
        AgentSpec(
            id="fea-runner",
            name="FEA Runner",
            tier=3,
            blurb="Invokes RFEM / SOFiSTiK / SAP2000 / ETABS and returns parsed results.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
            default_plan=(
                "Convert geometry to native FEA format",
                "Submit run to the FEA engine",
                "Parse results and reconcile against design loads",
                "Return summary and persist raw run files",
            ),
        ),
        AgentSpec(
            id="code-compliance-reviewer",
            name="Code Compliance Reviewer",
            tier=3,
            blurb="Clause-by-clause compliance walk for any element + load case.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
            default_plan=(
                "Enumerate clauses applicable to the element class",
                "Apply National Annex parameters",
                "Run each clause check and record pass/fail/cite",
                "Produce compliance matrix and reviewer report",
            ),
        ),
        # Tier 2 — Drafting
        AgentSpec(
            id="reinforcement-drafter",
            name="Reinforcement Drafter",
            tier=2,
            blurb="Code-compliant rebar drawings + bar schedule from a calc package.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us"),
            default_plan=(
                "Read calc package and load takedowns",
                "Place primary and secondary reinforcement per clauses",
                "Generate DWG with DIN/ACI layering",
                "Produce bar schedule XLSX",
            ),
        ),
        AgentSpec(
            id="formwork-planner",
            name="Formwork Planner",
            tier=2,
            blurb="Formwork layouts per Peri / Doka / Symons systems.",
            region_tags=("de", "ch", "at", "fr", "us"),
        ),
        AgentSpec(
            id="geotech-report-author",
            name="Geotech Report Author",
            tier=2,
            blurb="Site investigation report per EN 1997-1 with foundation recommendations.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au"),
        ),
        # Tier 1 — Productivity
        AgentSpec(
            id="permit-pack-assembler",
            name="Permit Pack Assembler",
            tier=1,
            blurb="Assembles permit submission packs per jurisdiction.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
            default_plan=(
                "Pull latest signed deliverables",
                "Apply jurisdiction-specific template",
                "Generate stamp-ready PDF/A and checklist",
            ),
        ),
        AgentSpec(
            id="qto-generator",
            name="QTO Generator",
            tier=1,
            blurb="Quantity takeoff from the BIM model and drawings.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
        ),
        AgentSpec(
            id="cost-estimator",
            name="Cost Estimator",
            tier=1,
            blurb="BKI / RSMeans / Spon's-priced cost breakdown by assembly.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
        ),
        AgentSpec(
            id="hoai-fee-calculator",
            name="HOAI Fee Calculator",
            tier=1,
            blurb="Regional fee per HOAI / AIA / RIBA / ACEC / AS schedule.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
        ),
        AgentSpec(
            id="carbon-reporter",
            name="Carbon (LCA) Reporter",
            tier=1,
            blurb="Embodied carbon per EN 15978 with regional EPDs.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
        ),
        AgentSpec(
            id="drawing-standards-advisor",
            name="Drawing Standards Advisor",
            tier=1,
            blurb="Always-on lint: DIN 1356 / ISO 128 / ASME Y14 / AS 1100 conformance.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
        ),
        AgentSpec(
            id="calc-sanity-advisor",
            name="Calc-Sanity Advisor",
            tier=1,
            blurb="Always-on cross-check: column reactions reconcile with foundation loads.",
            region_tags=("de", "ch", "at", "fr", "nl", "be", "uk", "us", "au", "ca"),
        ),
    )
}


def lookup(agent_id: str) -> AgentSpec | None:
    """Return the catalog spec for an agent id, or None if unknown."""
    return AGENTS.get(agent_id)


__all__ = ["AGENTS", "AgentSpec", "lookup"]
