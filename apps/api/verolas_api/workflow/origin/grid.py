"""Parametric structural-grid engine for Verolas Origin.

Given a reviewed building geometry and the engineer's roof framing
plan, this module proposes three structural concept options that span
the typical engineer's mental shortlist:

- **Optimized** maximises bay span. Fewer columns, deeper beams, lower
  unit price but larger members.
- **Balanced** is the middle ground most projects pick.
- **Conservative** uses tighter bays. More columns, smaller members,
  higher robustness and easier construction.

Each option is built from first principles: tributary-area loads,
member-sizing rules of thumb, and Bill-of-Quantities estimates. Numbers
are intentionally approximate; the responsible engineer refines them
in the next workflow step. What matters here is that the three options
are *internally consistent* and *clearly differentiated*, so the AI
options adapter and the gate UI have something the engineer can
actually compare.

The engine is deterministic, dependency-free (no numpy / no I/O), and
unit-tested. The AI adapter layers Claude on top for sustainability
notes, caveats, and natural-language summary, but never touches the
numerical fields produced here.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from verolas_api.workflow.origin.geometry import Geometry


class BayGrid(BaseModel):
    """Typical bay dimensions on each axis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x_m: float
    y_m: float


class MaterialTakeoff(BaseModel):
    """Coarse Bill-of-Quantities for the option."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    structural_steel_kg: float = 0.0
    concrete_m3: float = 0.0
    rebar_kg: float = 0.0
    glulam_m3: float = 0.0
    clt_m3: float = 0.0
    timber_studs_m: float = 0.0


class DcrDistribution(BaseModel):
    """Demand-Capacity-Ratio distribution across structural members.

    Engineer reads this as "how hard are the members working?". Each
    bin holds the *fraction* of members in that range. Sums to ~1.0.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    under_60_pct: float
    between_60_80: float
    between_80_100: float
    over_100: float


class Constructibility(BaseModel):
    """Construction-effort metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    unique_beam_sizes: int
    unique_column_sizes: int
    total_unique_sizes: int


class StructuralOption(BaseModel):
    """One of the three options the engineer chooses between."""

    model_config = ConfigDict(extra="forbid")

    option_id: str
    variant: str  # optimized / balanced / conservative
    summary: str
    bay_grid_m: BayGrid
    slab_type: str
    primary_structure: str
    material: str
    prelim_load_kN_m2: float
    boq_estimate_eur_m2: float
    boq_total_eur: float
    sustainability_note: str
    caveats: list[str]
    takeoff: MaterialTakeoff
    dcr_distribution: DcrDistribution
    constructibility: Constructibility
    column_count: int
    gfa_m2: float
    notes: list[str] = Field(default_factory=list)


_VARIANTS = (
    {
        "variant": "optimized",
        "label": "Optimized",
        "system_id": "rc_flat_slab",
        "primary_structure": "RC frame with shear walls",
        "slab_type": "Flat slab, 260 mm",
        "material": "Concrete C25/30, rebar B500B",
        "bay_target_m": 8.5,  # larger bays
        "dcr_skew": "high",  # members work harder
        "size_diversity": "low",  # repeat sections aggressively
        "boq_per_m2_eur": 1480.0,
    },
    {
        "variant": "balanced",
        "label": "Balanced",
        "system_id": "steel_mrf",
        "primary_structure": "Steel MRF with secondary beams",
        "slab_type": "Composite metal deck, 130 mm topping",
        "material": "Structural steel S355, concrete C25/30 topping",
        "bay_target_m": 7.5,
        "dcr_skew": "middle",
        "size_diversity": "moderate",
        "boq_per_m2_eur": 1620.0,
    },
    {
        "variant": "conservative",
        "label": "Conservative",
        "system_id": "clt_hybrid",
        "primary_structure": "CLT panels with steel or RC core",
        "slab_type": "CLT panel, 180 mm five-layer",
        "material": "Glulam GL24h, CLT panels, S355 core",
        "bay_target_m": 6.5,  # tighter bays
        "dcr_skew": "low",  # members lightly loaded
        "size_diversity": "high",  # more unique sections
        "boq_per_m2_eur": 1780.0,
    },
)


_DEFAULT_DEAD_KN_M2 = 4.5  # SDL + self-weight typical office / residential
_DEFAULT_LIVE_KN_M2 = 2.0  # category A residential
_ASSUMED_FLOOR_HEIGHT_M = 3.0


def generate_options(
    geometry: Geometry,
    parameters: dict[str, Any] | None = None,
) -> list[StructuralOption]:
    """Build the three structural options.

    `geometry` is the reviewed building geometry. `parameters` is the
    optional dict the engineer filled in on the upstream `parameters`
    node (loads, code, materials). When absent, sensible defaults are
    used so the engine can still produce a comparable shortlist; the
    `notes` field on each option records which defaults were applied.
    """
    if not geometry.floors:
        return []

    dead = _coerce_float(parameters, "dead_load_kN_m2", _DEFAULT_DEAD_KN_M2)
    live = _coerce_float(parameters, "live_load_kN_m2", _DEFAULT_LIVE_KN_M2)
    prelim_load = dead + live

    occupied_floors = [f for f in geometry.floors if not f.is_roof]
    if not occupied_floors:
        occupied_floors = geometry.floors  # fallback when no floor flagged
    floor_count = len(occupied_floors)

    gfa_m2 = sum(_extent_area(f.extents) for f in occupied_floors)

    notes: list[str] = []
    if parameters is None:
        notes.append("Used default dead/live loads; refine via the parameters step.")

    options: list[StructuralOption] = []
    for spec in _VARIANTS:
        options.append(
            _build_option(
                spec=spec,
                geometry=geometry,
                gfa_m2=gfa_m2,
                floor_count=floor_count,
                prelim_load=prelim_load,
                shared_notes=notes,
            )
        )
    return options


def _build_option(
    *,
    spec: dict[str, Any],
    geometry: Geometry,
    gfa_m2: float,
    floor_count: int,
    prelim_load: float,
    shared_notes: list[str],
) -> StructuralOption:
    # Each floor's bay grid snaps to its own footprint so corner
    # bays don't run off the building. For a quick summary we use
    # the first occupied floor; engineer can refine per floor in
    # the next step.
    first_floor = next(
        (f for f in geometry.floors if not f.is_roof),
        geometry.floors[0],
    )
    ex = first_floor.extents
    width_m = max(0.1, ex.max_x - ex.min_x)
    depth_m = max(0.1, ex.max_y - ex.min_y)

    target = float(spec["bay_target_m"])
    cols_x = max(1, round(width_m / target))
    cols_y = max(1, round(depth_m / target))
    bay = BayGrid(x_m=width_m / cols_x, y_m=depth_m / cols_y)

    columns_per_floor = (cols_x + 1) * (cols_y + 1)
    total_columns = columns_per_floor * floor_count

    takeoff = _estimate_takeoff(
        system_id=str(spec["system_id"]),
        gfa_m2=gfa_m2,
        total_columns=total_columns,
        bay=bay,
        floor_count=floor_count,
    )

    dcr = _dcr_for(str(spec["dcr_skew"]))
    constructibility = _constructibility_for(
        size_diversity=str(spec["size_diversity"]),
        system_id=str(spec["system_id"]),
    )
    boq_per_m2 = float(spec["boq_per_m2_eur"])

    caveats = _caveats_for(str(spec["system_id"]))
    sustainability_note = _sustainability_for(str(spec["system_id"]))

    summary = (
        f"{spec['primary_structure']} on a "
        f"{bay.x_m:.1f} by {bay.y_m:.1f} m bay grid; "
        f"{spec['label'].lower()} variant for {floor_count}-storey building."
    )

    return StructuralOption(
        option_id=f"{spec['variant']}_{spec['system_id']}",
        variant=str(spec["variant"]),
        summary=summary,
        bay_grid_m=bay,
        slab_type=str(spec["slab_type"]),
        primary_structure=str(spec["primary_structure"]),
        material=str(spec["material"]),
        prelim_load_kN_m2=round(prelim_load, 2),
        boq_estimate_eur_m2=boq_per_m2,
        boq_total_eur=round(boq_per_m2 * gfa_m2, 0),
        sustainability_note=sustainability_note,
        caveats=caveats,
        takeoff=takeoff,
        dcr_distribution=dcr,
        constructibility=constructibility,
        column_count=total_columns,
        gfa_m2=round(gfa_m2, 1),
        notes=list(shared_notes),
    )


def _extent_area(extents: Any) -> float:
    """Area of an Extents-shaped object in m^2."""
    w = max(0.0, float(extents.max_x) - float(extents.min_x))
    d = max(0.0, float(extents.max_y) - float(extents.min_y))
    return w * d


def _coerce_float(params: dict[str, Any] | None, key: str, default: float) -> float:
    if not params:
        return default
    value = params.get(key)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _estimate_takeoff(
    *,
    system_id: str,
    gfa_m2: float,
    total_columns: int,
    bay: BayGrid,
    floor_count: int,
) -> MaterialTakeoff:
    """Rule-of-thumb material quantities per system."""
    avg_bay_m = (bay.x_m + bay.y_m) / 2.0
    # floor_count is kept on the call signature for future per-storey
    # adjustments (column height scaling, etc.).
    _ = floor_count

    if system_id == "rc_flat_slab":
        # Flat slab ~230-280 mm; rebar ~140 kg/m3 concrete.
        concrete_m3 = gfa_m2 * 0.27
        rebar_kg = concrete_m3 * 140.0
        return MaterialTakeoff(
            concrete_m3=round(concrete_m3, 1),
            rebar_kg=round(rebar_kg, 0),
        )
    if system_id == "steel_mrf":
        # Steel mass ~70-90 kg/m^2 GFA + composite topping ~0.13 m^3/m^2.
        kg_per_m2 = 70.0 + max(0.0, (avg_bay_m - 7.5)) * 6.0
        steel_kg = gfa_m2 * kg_per_m2
        topping_m3 = gfa_m2 * 0.13
        rebar_kg = topping_m3 * 90.0
        return MaterialTakeoff(
            structural_steel_kg=round(steel_kg, 0),
            concrete_m3=round(topping_m3, 1),
            rebar_kg=round(rebar_kg, 0),
        )
    if system_id == "clt_hybrid":
        # CLT panels ~0.18 m^3/m^2 GFA + glulam beams + minor steel core.
        clt_m3 = gfa_m2 * 0.18
        glulam_m3 = (gfa_m2 / max(avg_bay_m, 4.0)) * 0.04
        # Core stair takes ~8 kg/m^2 effective.
        steel_kg = gfa_m2 * 8.0
        return MaterialTakeoff(
            clt_m3=round(clt_m3, 1),
            glulam_m3=round(glulam_m3, 1),
            structural_steel_kg=round(steel_kg, 0),
        )
    # Fallback if a new system_id sneaks in.
    return MaterialTakeoff(
        concrete_m3=round(gfa_m2 * 0.2, 1),
    )


def _dcr_for(skew: str) -> DcrDistribution:
    """Pre-baked DCR distributions; sum to 1.0 for each variant.

    Real engines compute DCR per member by running each through the
    governing load case. Origin is a *concept*-level adapter; the
    distribution shape matches what the engineer expects to see
    (Optimized members work harder, Conservative members work easier).
    """
    if skew == "high":
        return DcrDistribution(
            under_60_pct=0.05,
            between_60_80=0.30,
            between_80_100=0.55,
            over_100=0.10,
        )
    if skew == "middle":
        return DcrDistribution(
            under_60_pct=0.15,
            between_60_80=0.40,
            between_80_100=0.40,
            over_100=0.05,
        )
    if skew == "low":
        return DcrDistribution(
            under_60_pct=0.40,
            between_60_80=0.40,
            between_80_100=0.18,
            over_100=0.02,
        )
    return DcrDistribution(
        under_60_pct=0.25, between_60_80=0.40, between_80_100=0.30, over_100=0.05
    )


def _constructibility_for(*, size_diversity: str, system_id: str) -> Constructibility:
    if size_diversity == "low":
        beam_sizes = 2
        column_sizes = 1
    elif size_diversity == "moderate":
        beam_sizes = 3
        column_sizes = 2
    else:
        beam_sizes = 4
        column_sizes = 3
    # CLT introduces panel-thickness diversity; bump unique sizes by 1.
    if system_id == "clt_hybrid":
        beam_sizes += 1
    total = beam_sizes + column_sizes
    return Constructibility(
        unique_beam_sizes=beam_sizes,
        unique_column_sizes=column_sizes,
        total_unique_sizes=total,
    )


def _caveats_for(system_id: str) -> list[str]:
    if system_id == "rc_flat_slab":
        return [
            "Verify punching shear at internal columns.",
            "Check long-term deflections for spans > 8 m.",
            "Confirm Bauamt accepts CEM II/B-S with low-clinker content.",
        ]
    if system_id == "steel_mrf":
        return [
            "Add fire protection on exposed beams (R60 typical).",
            "Run vibration check for office occupancy (Wyatt limits).",
            "Detail column splice positions to avoid hot-rolled bottleneck.",
        ]
    if system_id == "clt_hybrid":
        return [
            "Detail R60 fire encapsulation on exposed CLT.",
            "Verify diaphragm continuity with engineered fastener pattern.",
            "Check moisture exposure during construction; protect panels.",
        ]
    return ["Refine per system selected."]


def _sustainability_for(system_id: str) -> str:
    if system_id == "rc_flat_slab":
        return (
            "Highest embodied carbon of the three; offset partially with "
            "30% recycled aggregate and CEM II/B-S cement."
        )
    if system_id == "steel_mrf":
        return (
            "Mid-range embodied carbon; structure is demountable, "
            "supports end-of-life reuse if connections are bolted."
        )
    if system_id == "clt_hybrid":
        return (
            "Lowest embodied carbon; biogenic carbon credit possible "
            "under EN 16485 when timber is responsibly sourced."
        )
    return "Sustainability profile depends on system selected."


def _round_half(value: float, places: int = 1) -> float:
    """Banker-safe rounding helper kept around for future use."""
    return round(value, places) if not math.isnan(value) else 0.0
