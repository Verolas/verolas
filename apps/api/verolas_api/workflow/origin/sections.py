"""Section library for the Origin grid engine.

EU steel sections (IPE / HEA / HEB / HEM) are loaded from a vendored
copy of pcachim/eurocodepy's `i_profiles_euro.json` (MIT). Capacities
are derived for grade S355 from the catalogue's S235 reference values.

US steel W-shapes are loaded from a vendored copy of the AISC Shapes
Database v15.0 SI sheet via the MIT-licensed ambaker1/aisc-csv mirror.
Capacities are computed at grade A992 (f_y = 345 MPa).

Reinforced-concrete and CLT-hybrid catalogues remain in code: those
will be replaced when the structuralcodes + CLT timber libraries land
in a later step. Cost figures here are placeholders pegged to per-mass
rates; the real cost lookup against DDC CWICR moves into `cost.py`.

Conventions:
- `moment_capacity_kNm` is the design moment capacity M_Rd, single
  major-axis value with gamma_M0 = 1.0 (EU: EC3 6.2.5; US: AISC F2.1).
- `axial_capacity_kN` is the design compressive resistance N_b,Rd
  including flexural buckling at an assumed effective length of 3 m
  (one storey). EC3 buckling curve 'b' / AISC E3 limit-state approach.
- `self_weight_kg_per_m` matches the catalogue mass per metre.
- `unit_cost_eur_per_m` is `self_weight_kg_per_m * STEEL_EUR_PER_KG`
  until the real cost adapter ships.
- `rank` is the sort key (lighter = lower); the sizer walks from
  lightest to heaviest and picks the first that passes.
"""

from __future__ import annotations

import csv
import json
import math
from importlib import resources
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from verolas_api.workflow.origin import cost

SystemId = Literal["rc_flat_slab", "steel_mrf", "clt_hybrid"]
MemberRole = Literal["beam", "column"]
Jurisdiction = Literal["eu", "us"]

# Steel grades used by the loaders. f_y in MPa.
_FY_S355_MPA: Final[float] = 355.0
_FY_A992_MPA: Final[float] = 345.0  # ASTM A992 grade 50

# Effective length assumed by the catalogue's `axial_capacity_kN`.
# One storey at our assumed floor height. Real values are recomputed
# per-member by the grid engine when richer geometry is available.
_COLUMN_LEFF_MM: Final[float] = 3000.0

# Elastic modulus for buckling slenderness. EC3 + AISC use 200 GPa.
_E_STEEL_MPA: Final[float] = 200_000.0

# EC3 buckling curve 'b' imperfection factor. Used as a conservative
# default across the catalogue; the actual curve depends on profile
# family + axis but 'b' covers most rolled sections we ship.
_ALPHA_EC3_CURVE_B: Final[float] = 0.34

# Steel rates per kg, sourced from DDC CWICR Open Construction Cost
# Database (CC-BY-4.0). The US rate stays denominated in USD until a
# proper currency field lands on Section; for now it is parked in the
# (misleadingly named) `unit_cost_eur_per_m` slot for US sections. EU
# values are EUR. See `verolas_api.workflow.origin.cost` for picks.
_EU_STEEL_RATE_PER_KG: Final[float] = cost.material_rate(
    "structural_steel", jurisdiction="eu"
).rate_per_kg
_US_STEEL_RATE_PER_KG: Final[float] = cost.material_rate(
    "structural_steel", jurisdiction="us"
).rate_per_kg


class Section(BaseModel):
    """One entry in the section catalogue."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    system_id: SystemId
    role: MemberRole
    material: str
    jurisdiction: Jurisdiction = "eu"
    moment_capacity_kNm: float = 0.0
    axial_capacity_kN: float = 0.0
    self_weight_kg_per_m: float
    unit_cost_eur_per_m: float
    rank: int


# ---------------------------------------------------------------------
# Concrete + CLT: hand-coded catalogues, unchanged from P0.
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# EC3 / AISC buckling helpers.
# ---------------------------------------------------------------------


def _euler_slenderness(fy_mpa: float) -> float:
    """λ1 = π sqrt(E / fy). Used to non-dimensionalise slenderness."""
    return math.pi * math.sqrt(_E_STEEL_MPA / fy_mpa)


def _chi_ec3(slenderness_norm: float, alpha: float = _ALPHA_EC3_CURVE_B) -> float:
    """Reduction factor χ per EN 1993-1-1 §6.3.1.2."""
    if slenderness_norm <= 0.2:
        return 1.0
    phi = 0.5 * (1.0 + alpha * (slenderness_norm - 0.2) + slenderness_norm**2)
    chi = 1.0 / (phi + math.sqrt(phi**2 - slenderness_norm**2))
    return min(chi, 1.0)


def _n_b_rd_kn(area_mm2: float, i_min_mm: float, fy_mpa: float) -> float:
    """Buckling resistance N_b,Rd in kN using EC3 curve 'b'."""
    lambda1 = _euler_slenderness(fy_mpa)
    slenderness_norm = (_COLUMN_LEFF_MM / i_min_mm) / lambda1
    chi = _chi_ec3(slenderness_norm)
    n_pl_rd = area_mm2 * fy_mpa / 1000.0  # kN
    return chi * n_pl_rd


# ---------------------------------------------------------------------
# Data file resolution.
# ---------------------------------------------------------------------


def _data_root() -> Path:
    """Path to the vendored origin data root inside the package."""
    return Path(str(resources.files("verolas_api").joinpath("data/origin")))


# ---------------------------------------------------------------------
# European I-profiles via eurocodepy.
# ---------------------------------------------------------------------


def _load_eu_i_profiles() -> tuple[Section, ...]:
    """Load IPE / HEA / HEB / HEM sections, grade S355, both roles."""
    json_path = _data_root() / "eu-steel" / "i_profiles_euro.json"
    with json_path.open() as fh:
        raw_entries = json.load(fh)

    sections: list[Section] = []
    column_rank = 0
    beam_rank = 0
    # Sort by self-weight so rank order is lightest-first.
    for entry in sorted(raw_entries, key=lambda d: float(d["m"])):
        name = str(entry["Section"])
        family = name[:3]  # 'IPE', 'HEA', 'HEB', 'HEM'

        # Catalogue units: cm for dims, cm² for A, cm⁴ for I, cm for i,
        # cm³ for W, kg/m for mass m, kN/kNm for N_pl_Rd / M_pl_Rd at S235.
        area_cm2 = float(entry["A"])
        mass_kg_m = float(entry["m"])
        wpl_y_cm3 = float(entry["Wpl_y"])
        iy_cm = float(entry["iy"])
        iz_cm = float(entry["iz"])

        material = f"Structural steel S355 ({family})"
        weight_per_m = mass_kg_m
        cost_per_m = mass_kg_m * _EU_STEEL_RATE_PER_KG

        # Plastic moment capacity at S355:
        # M_pl,Rd [kNm] = Wpl_y [cm³] * f_y [N/mm²] * 1e-3
        # cm³ -> mm³ ratio is 1000; f_y in N/mm² so [N·mm] then /1e6
        # combine: Wpl_y_cm3 * 1000 * fy / 1e6 = Wpl_y_cm3 * fy / 1000.
        m_pl_rd = wpl_y_cm3 * _FY_S355_MPA / 1000.0

        # Compression: buckling about the weaker axis.
        i_min_mm = min(iy_cm, iz_cm) * 10.0
        area_mm2 = area_cm2 * 100.0
        n_b_rd = _n_b_rd_kn(area_mm2, i_min_mm, _FY_S355_MPA)

        # Every section enters both as a beam and as a column. Different
        # rank counters so the lightest beam is rank 1 within beams, etc.
        beam_rank += 1
        sections.append(
            Section(
                name=f"{name} (S355)",
                system_id="steel_mrf",
                role="beam",
                material=material,
                jurisdiction="eu",
                moment_capacity_kNm=round(m_pl_rd, 1),
                self_weight_kg_per_m=weight_per_m,
                unit_cost_eur_per_m=round(cost_per_m, 1),
                rank=beam_rank,
            )
        )
        column_rank += 1
        sections.append(
            Section(
                name=f"{name} (S355)",
                system_id="steel_mrf",
                role="column",
                material=material,
                jurisdiction="eu",
                axial_capacity_kN=round(n_b_rd, 1),
                self_weight_kg_per_m=weight_per_m,
                unit_cost_eur_per_m=round(cost_per_m, 1),
                rank=column_rank,
            )
        )
    return tuple(sections)


# ---------------------------------------------------------------------
# US W-shapes via AISC v15.0 (ambaker1/aisc-csv mirror).
# ---------------------------------------------------------------------


def _load_us_w_shapes() -> tuple[Section, ...]:
    """Load AISC W-shapes, grade A992, both roles. Returns mass-sorted."""
    csv_path = _data_root() / "aisc" / "aisc-shapes-v15-si.csv"
    with csv_path.open() as fh:
        rows = list(csv.DictReader(fh))

    w_rows = [r for r in rows if r["Type"] == "W"]

    # CSV units (per AISC v15 SI sheet conventions):
    # A: mm², W: kg/m, Zx: 10³ mm³, ry: mm.
    def _num(value: str) -> float:
        s = value.strip()
        return float(s) if s else 0.0

    sections: list[Section] = []
    column_rank = 0
    beam_rank = 0
    for row in sorted(w_rows, key=lambda r: _num(r["W"])):
        label = row["AISC_Manual_Label"].strip()
        area_mm2 = _num(row["A"])
        mass_kg_m = _num(row["W"])
        zx_kmm3 = _num(row["Zx"])  # 10³ mm³
        rx_mm = _num(row["rx"])
        ry_mm = _num(row["ry"])
        if area_mm2 <= 0 or mass_kg_m <= 0 or zx_kmm3 <= 0:
            continue

        material = f"Structural steel A992 ({label})"
        cost_per_m = mass_kg_m * _US_STEEL_RATE_PER_KG

        # M_p = Zx * f_y, with Zx in 10³ mm³ and f_y in N/mm² gives
        # kN·mm; divide by 1000 for kN·m.
        m_p = zx_kmm3 * _FY_A992_MPA / 1000.0

        i_min_mm = min(rx_mm, ry_mm) if ry_mm > 0 and rx_mm > 0 else max(rx_mm, ry_mm)
        if i_min_mm <= 0:
            continue
        n_b_rd = _n_b_rd_kn(area_mm2, i_min_mm, _FY_A992_MPA)

        beam_rank += 1
        sections.append(
            Section(
                name=f"{label} (A992)",
                system_id="steel_mrf",
                role="beam",
                material=material,
                jurisdiction="us",
                moment_capacity_kNm=round(m_p, 1),
                self_weight_kg_per_m=mass_kg_m,
                unit_cost_eur_per_m=round(cost_per_m, 1),
                rank=beam_rank,
            )
        )
        column_rank += 1
        sections.append(
            Section(
                name=f"{label} (A992)",
                system_id="steel_mrf",
                role="column",
                material=material,
                jurisdiction="us",
                axial_capacity_kN=round(n_b_rd, 1),
                self_weight_kg_per_m=mass_kg_m,
                unit_cost_eur_per_m=round(cost_per_m, 1),
                rank=column_rank,
            )
        )
    return tuple(sections)


_EU_STEEL_SECTIONS: Final[tuple[Section, ...]] = _load_eu_i_profiles()
_US_STEEL_SECTIONS: Final[tuple[Section, ...]] = _load_us_w_shapes()

_ALL_SECTIONS: Final[tuple[Section, ...]] = (
    _RC_SECTIONS + _EU_STEEL_SECTIONS + _US_STEEL_SECTIONS + _CLT_SECTIONS
)


# ---------------------------------------------------------------------
# Public selection API. Signatures kept compatible with grid.py.
# ---------------------------------------------------------------------


def sections_for(
    system_id: SystemId,
    role: MemberRole,
    *,
    jurisdiction: Jurisdiction = "eu",
) -> list[Section]:
    """Return candidate sections sorted lightest-first.

    `jurisdiction` only affects the `steel_mrf` system: 'eu' returns the
    IPE/HEA/HEB/HEM family, 'us' returns AISC W-shapes. For RC and CLT
    the jurisdiction parameter is ignored (single catalogue).
    """
    candidates = [
        s
        for s in _ALL_SECTIONS
        if s.system_id == system_id
        and s.role == role
        and (system_id != "steel_mrf" or s.jurisdiction == jurisdiction)
    ]
    return sorted(candidates, key=lambda s: s.rank)


def smallest_passing_beam(
    system_id: SystemId,
    required_moment_kNm: float,
    *,
    jurisdiction: Jurisdiction = "eu",
) -> Section | None:
    """Lightest beam whose M_Rd >= required_moment_kNm."""
    for section in sections_for(system_id, "beam", jurisdiction=jurisdiction):
        if section.moment_capacity_kNm >= required_moment_kNm:
            return section
    return None


def smallest_passing_column(
    system_id: SystemId,
    required_axial_kN: float,
    *,
    jurisdiction: Jurisdiction = "eu",
) -> Section | None:
    """Lightest column whose N_b,Rd >= required_axial_kN."""
    for section in sections_for(system_id, "column", jurisdiction=jurisdiction):
        if section.axial_capacity_kN >= required_axial_kN:
            return section
    return None


def heaviest(
    system_id: SystemId,
    role: MemberRole,
    *,
    jurisdiction: Jurisdiction = "eu",
) -> Section:
    """Largest section in the catalogue. Fallback when nothing passes."""
    sections = sections_for(system_id, role, jurisdiction=jurisdiction)
    if not sections:
        raise ValueError(f"No sections for {system_id}/{role} ({jurisdiction})")
    return sections[-1]


# Attribution strings the Origin PDF must surface on the References
# page whenever the engine consumed the corresponding data source.
# Mirrors the strings in `data/origin/MANIFEST.md` so any update
# happens in one place per data source.

EUROCODEPY_ATTRIBUTION: Final[str] = (
    "European steel section properties (IPE / HEA / HEB / HEM): "
    "pcachim/eurocodepy (MIT). "
    "https://github.com/pcachim/eurocodepy"
)

AISC_SHAPES_ATTRIBUTION: Final[str] = (
    "US steel section properties: AISC Shapes Database v15.0 "
    "(© American Institute of Steel Construction), redistributed "
    "via the ambaker1/aisc-csv MIT mirror. "
    "https://github.com/ambaker1/aisc-csv"
)

EC3_DESIGN_CODE_ATTRIBUTION: Final[str] = (
    "EU steel member capacities computed per EN 1993-1-1 (Eurocode 3): "
    "M_pl,Rd from section 6.2.5 and N_b,Rd flexural buckling from "
    "section 6.3.1.2 with imperfection factor alpha = 0.34 (curve b)."
)

AISC_360_DESIGN_CODE_ATTRIBUTION: Final[str] = (
    "US steel member capacities computed per ANSI/AISC 360-22 (Sections F2 and E3 as applicable)."
)


__all__ = [
    "AISC_360_DESIGN_CODE_ATTRIBUTION",
    "AISC_SHAPES_ATTRIBUTION",
    "EC3_DESIGN_CODE_ATTRIBUTION",
    "EUROCODEPY_ATTRIBUTION",
    "Jurisdiction",
    "MemberRole",
    "Section",
    "SystemId",
    "heaviest",
    "sections_for",
    "smallest_passing_beam",
    "smallest_passing_column",
]
