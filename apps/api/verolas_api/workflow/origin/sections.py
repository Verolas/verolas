"""Section library for the Origin grid engine.

A tiny but real catalogue of beam and column sections per structural
system. Capacities here are simplified single-number ratings, derived
from the relevant code with conservative reductions, suitable for a
concept-stage shortlist; final sizing belongs to the engineer's full
analysis in the next workflow (Statik).

Conventions:
- `moment_capacity_kNm` is the design moment capacity M_Rd, simplified
  to a single value per section (no axis distinction). For steel
  beams this is approximately fy * Wpl / gamma_M0. For RC beams it
  comes from a typical concrete-rebar layout. For glulam from
  GL24h tabulated values.
- `axial_capacity_kN` is N_Rd for columns under typical buckling
  (L_eff = 3 m storey height, intermediate slenderness). For RC
  columns it's a typical squat-column rating with code reductions;
  not slender-column buckling.
- `unit_cost_eur_per_m` is a market-typical rate (EU 2026) including
  fabrication + erection. Engineer overrides per project.
- `self_weight_kg_per_m` is the bare section weight; for RC it
  includes typical reinforcement.

The catalogue is intentionally short: 3-4 sections per role per
system. The engine picks the smallest section that passes the check.
A real production library would have hundreds of sections and is a
future swap-in.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

SystemId = Literal["rc_flat_slab", "steel_mrf", "clt_hybrid"]
MemberRole = Literal["beam", "column"]


class Section(BaseModel):
    """One entry in the section catalogue."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    system_id: SystemId
    role: MemberRole
    material: str  # display string for the PDF / DXF
    moment_capacity_kNm: float = 0.0
    axial_capacity_kN: float = 0.0
    self_weight_kg_per_m: float
    unit_cost_eur_per_m: float
    # Sort key. Smaller value = lighter section. Used so the sizer
    # walks the catalogue from lightest to heaviest.
    rank: int


# RC flat-slab system: column and slab-band beams in concrete.
# Column sizes refer to square RC columns with typical longitudinal
# rebar (8 phi 20 in C25/30). N_Rd ~ A_c * f_cd + A_s * f_yd.
# Beam entries represent slab bands across spans up to 9 m.
_RC_SECTIONS: tuple[Section, ...] = (
    Section(
        name="RC 300x300 (C25/30)",
        system_id="rc_flat_slab",
        role="column",
        material="Concrete C25/30, rebar B500B",
        axial_capacity_kN=1450.0,
        self_weight_kg_per_m=225.0,
        unit_cost_eur_per_m=380.0,
        rank=1,
    ),
    Section(
        name="RC 400x400 (C25/30)",
        system_id="rc_flat_slab",
        role="column",
        material="Concrete C25/30, rebar B500B",
        axial_capacity_kN=2600.0,
        self_weight_kg_per_m=400.0,
        unit_cost_eur_per_m=540.0,
        rank=2,
    ),
    Section(
        name="RC 500x500 (C25/30)",
        system_id="rc_flat_slab",
        role="column",
        material="Concrete C25/30, rebar B500B",
        axial_capacity_kN=4100.0,
        self_weight_kg_per_m=625.0,
        unit_cost_eur_per_m=720.0,
        rank=3,
    ),
    Section(
        name="RC band 1200x240 (C25/30)",
        system_id="rc_flat_slab",
        role="beam",
        material="Concrete C25/30 + rebar B500B",
        moment_capacity_kNm=420.0,
        self_weight_kg_per_m=720.0,
        unit_cost_eur_per_m=620.0,
        rank=1,
    ),
    Section(
        name="RC band 1600x260 (C25/30)",
        system_id="rc_flat_slab",
        role="beam",
        material="Concrete C25/30 + rebar B500B",
        moment_capacity_kNm=680.0,
        self_weight_kg_per_m=1040.0,
        unit_cost_eur_per_m=820.0,
        rank=2,
    ),
    Section(
        name="RC band 2000x300 (C25/30)",
        system_id="rc_flat_slab",
        role="beam",
        material="Concrete C25/30 + rebar B500B",
        moment_capacity_kNm=950.0,
        self_weight_kg_per_m=1500.0,
        unit_cost_eur_per_m=1100.0,
        rank=3,
    ),
)

# Steel MRF system: standard European profiles.
# HEB columns + IPE beams in S355. Capacities use Eurocode 3 plastic
# resistance with gamma_M0 = 1.0.
_STEEL_SECTIONS: tuple[Section, ...] = (
    Section(
        name="HEB 200 (S355)",
        system_id="steel_mrf",
        role="column",
        material="Structural steel S355",
        axial_capacity_kN=1900.0,
        self_weight_kg_per_m=61.3,
        unit_cost_eur_per_m=240.0,
        rank=1,
    ),
    Section(
        name="HEB 240 (S355)",
        system_id="steel_mrf",
        role="column",
        material="Structural steel S355",
        axial_capacity_kN=2750.0,
        self_weight_kg_per_m=83.2,
        unit_cost_eur_per_m=300.0,
        rank=2,
    ),
    Section(
        name="HEB 260 (S355)",
        system_id="steel_mrf",
        role="column",
        material="Structural steel S355",
        axial_capacity_kN=3300.0,
        self_weight_kg_per_m=93.0,
        unit_cost_eur_per_m=340.0,
        rank=3,
    ),
    Section(
        name="HEB 320 (S355)",
        system_id="steel_mrf",
        role="column",
        material="Structural steel S355",
        axial_capacity_kN=4900.0,
        self_weight_kg_per_m=127.0,
        unit_cost_eur_per_m=460.0,
        rank=4,
    ),
    Section(
        name="IPE 240 (S355)",
        system_id="steel_mrf",
        role="beam",
        material="Structural steel S355",
        moment_capacity_kNm=125.0,
        self_weight_kg_per_m=30.7,
        unit_cost_eur_per_m=140.0,
        rank=1,
    ),
    Section(
        name="IPE 300 (S355)",
        system_id="steel_mrf",
        role="beam",
        material="Structural steel S355",
        moment_capacity_kNm=219.0,
        self_weight_kg_per_m=42.2,
        unit_cost_eur_per_m=180.0,
        rank=2,
    ),
    Section(
        name="IPE 360 (S355)",
        system_id="steel_mrf",
        role="beam",
        material="Structural steel S355",
        moment_capacity_kNm=361.0,
        self_weight_kg_per_m=57.1,
        unit_cost_eur_per_m=230.0,
        rank=3,
    ),
    Section(
        name="IPE 450 (S355)",
        system_id="steel_mrf",
        role="beam",
        material="Structural steel S355",
        moment_capacity_kNm=617.0,
        self_weight_kg_per_m=77.6,
        unit_cost_eur_per_m=310.0,
        rank=4,
    ),
)

# CLT-hybrid: glulam beams + glulam columns + thin steel core for
# lateral stability (the steel goes onto the BoQ separately). Glulam
# capacities approximated from GL24h tables; densities ~470 kg/m^3.
_CLT_SECTIONS: tuple[Section, ...] = (
    Section(
        name="Glulam GL24h 240x240",
        system_id="clt_hybrid",
        role="column",
        material="Glulam GL24h",
        axial_capacity_kN=900.0,
        self_weight_kg_per_m=27.1,
        unit_cost_eur_per_m=220.0,
        rank=1,
    ),
    Section(
        name="Glulam GL24h 320x320",
        system_id="clt_hybrid",
        role="column",
        material="Glulam GL24h",
        axial_capacity_kN=1700.0,
        self_weight_kg_per_m=48.1,
        unit_cost_eur_per_m=320.0,
        rank=2,
    ),
    Section(
        name="Glulam GL24h 400x400",
        system_id="clt_hybrid",
        role="column",
        material="Glulam GL24h",
        axial_capacity_kN=2700.0,
        self_weight_kg_per_m=75.2,
        unit_cost_eur_per_m=430.0,
        rank=3,
    ),
    Section(
        name="Glulam GL24h 200x360",
        system_id="clt_hybrid",
        role="beam",
        material="Glulam GL24h",
        moment_capacity_kNm=72.0,
        self_weight_kg_per_m=33.8,
        unit_cost_eur_per_m=230.0,
        rank=1,
    ),
    Section(
        name="Glulam GL24h 240x440",
        system_id="clt_hybrid",
        role="beam",
        material="Glulam GL24h",
        moment_capacity_kNm=130.0,
        self_weight_kg_per_m=49.6,
        unit_cost_eur_per_m=310.0,
        rank=2,
    ),
    Section(
        name="Glulam GL24h 280x560",
        system_id="clt_hybrid",
        role="beam",
        material="Glulam GL24h",
        moment_capacity_kNm=230.0,
        self_weight_kg_per_m=73.7,
        unit_cost_eur_per_m=430.0,
        rank=3,
    ),
)


_ALL_SECTIONS: Final[tuple[Section, ...]] = _RC_SECTIONS + _STEEL_SECTIONS + _CLT_SECTIONS


def sections_for(system_id: SystemId, role: MemberRole) -> list[Section]:
    """Return the candidate sections for `system_id` and `role`, sorted lightest first."""
    candidates = [s for s in _ALL_SECTIONS if s.system_id == system_id and s.role == role]
    return sorted(candidates, key=lambda s: s.rank)


def smallest_passing_beam(system_id: SystemId, required_moment_kNm: float) -> Section | None:
    """Return the lightest beam section whose M_Rd >= required_moment_kNm."""
    for section in sections_for(system_id, "beam"):
        if section.moment_capacity_kNm >= required_moment_kNm:
            return section
    return None


def smallest_passing_column(system_id: SystemId, required_axial_kN: float) -> Section | None:
    """Return the lightest column section whose N_Rd >= required_axial_kN."""
    for section in sections_for(system_id, "column"):
        if section.axial_capacity_kN >= required_axial_kN:
            return section
    return None


def heaviest(system_id: SystemId, role: MemberRole) -> Section:
    """Return the largest section in the catalogue. Used as fallback when no section passes."""
    sections = sections_for(system_id, role)
    if not sections:
        raise ValueError(f"No sections for {system_id}/{role}")
    return sections[-1]


__all__ = [
    "MemberRole",
    "Section",
    "SystemId",
    "heaviest",
    "sections_for",
    "smallest_passing_beam",
    "smallest_passing_column",
]
