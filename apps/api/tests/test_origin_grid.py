"""Unit tests for the Origin parametric grid engine.

The engine is deterministic and dependency-free, so the assertions
focus on shape, internal consistency, and variant differentiation
rather than exact numerical equality.
"""

from __future__ import annotations

from verolas_api.workflow.origin.geometry import (
    Extents,
    Floor,
    Geometry,
    Point2D,
    Wall,
)
from verolas_api.workflow.origin.grid import (
    StructuralOption,
    generate_options,
)


def _floor(name: str, *, max_x: float, max_y: float, is_roof: bool = False) -> Floor:
    return Floor(
        key=name.lower().replace(" ", "_"),
        name=name,
        extents=Extents(min_x=0.0, min_y=0.0, max_x=max_x, max_y=max_y),
        walls=[
            Wall(id="w0", start=Point2D(x=0.0, y=0.0), end=Point2D(x=max_x, y=0.0)),
        ],
        is_roof=is_roof,
    )


def _geometry(floors: list[Floor]) -> Geometry:
    return Geometry(source_format="dxf", floors=floors)


def test_returns_empty_when_geometry_has_no_floors() -> None:
    assert generate_options(_geometry([])) == []


def test_generates_three_distinct_variants() -> None:
    geometry = _geometry(
        [
            _floor("Floor 1", max_x=20.0, max_y=15.0),
            _floor("Floor 2", max_x=20.0, max_y=15.0),
            _floor("Roof", max_x=20.0, max_y=15.0, is_roof=True),
        ]
    )
    options = generate_options(geometry)
    assert len(options) == 3
    variants = [o.variant for o in options]
    assert variants == ["optimized", "balanced", "conservative"]

    # No two variants should produce the same primary_structure (the
    # whole point is offering the engineer different systems).
    structures = {o.primary_structure for o in options}
    assert len(structures) == 3

    # All numerical fields populated.
    for opt in options:
        assert opt.bay_grid_m.x_m > 0
        assert opt.bay_grid_m.y_m > 0
        assert opt.prelim_load_kN_m2 > 0
        assert opt.boq_estimate_eur_m2 > 0
        assert opt.boq_total_eur > 0
        assert (
            0.99
            <= sum(
                (
                    opt.dcr_distribution.under_60_pct,
                    opt.dcr_distribution.between_60_80,
                    opt.dcr_distribution.between_80_100,
                    opt.dcr_distribution.over_100,
                )
            )
            <= 1.01
        )
        assert opt.constructibility.total_unique_sizes == (
            opt.constructibility.unique_beam_sizes + opt.constructibility.unique_column_sizes
        )
        assert opt.column_count > 0
        assert opt.gfa_m2 > 0


def test_optimized_uses_larger_bays_than_conservative() -> None:
    """The whole point of the three variants: span vs robustness."""
    geometry = _geometry(
        [
            _floor("Floor 1", max_x=40.0, max_y=24.0),
            _floor("Roof", max_x=40.0, max_y=24.0, is_roof=True),
        ]
    )
    options = generate_options(geometry)
    by_variant = {o.variant: o for o in options}

    opt_x = by_variant["optimized"].bay_grid_m.x_m
    cons_x = by_variant["conservative"].bay_grid_m.x_m

    # Optimized bay span should be larger (or at least no smaller) than
    # conservative; the rounding could match on small footprints but
    # never invert.
    assert opt_x >= cons_x


def test_optimized_has_higher_dcr_skew_than_conservative() -> None:
    geometry = _geometry(
        [
            _floor("Floor 1", max_x=30.0, max_y=20.0),
            _floor("Roof", max_x=30.0, max_y=20.0, is_roof=True),
        ]
    )
    options = generate_options(geometry)
    by_variant = {o.variant: o for o in options}

    optimized = by_variant["optimized"].dcr_distribution
    conservative = by_variant["conservative"].dcr_distribution

    # Optimized members work harder; the high-utilisation bins should
    # carry strictly more mass than in the Conservative variant.
    opt_hard = optimized.between_80_100 + optimized.over_100
    cons_hard = conservative.between_80_100 + conservative.over_100
    assert opt_hard > cons_hard


def test_takeoff_matches_system_choice() -> None:
    geometry = _geometry(
        [
            _floor("Floor 1", max_x=20.0, max_y=15.0),
            _floor("Roof", max_x=20.0, max_y=15.0, is_roof=True),
        ]
    )
    options = generate_options(geometry)
    by_variant = {o.variant: o for o in options}

    # RC flat slab option has concrete + rebar but no steel/CLT.
    rc = by_variant["optimized"].takeoff
    assert rc.concrete_m3 > 0
    assert rc.rebar_kg > 0
    assert rc.structural_steel_kg == 0
    assert rc.clt_m3 == 0

    # Steel MRF has structural steel + composite topping concrete.
    steel = by_variant["balanced"].takeoff
    assert steel.structural_steel_kg > 0
    assert steel.concrete_m3 > 0  # topping

    # CLT hybrid has CLT + glulam + a bit of steel for the core.
    clt = by_variant["conservative"].takeoff
    assert clt.clt_m3 > 0
    assert clt.glulam_m3 > 0
    assert clt.structural_steel_kg > 0


def test_uses_parameter_loads_when_provided() -> None:
    geometry = _geometry(
        [
            _floor("Floor 1", max_x=10.0, max_y=10.0),
            _floor("Roof", max_x=10.0, max_y=10.0, is_roof=True),
        ]
    )
    options_default = generate_options(geometry)
    options_heavy = generate_options(
        geometry,
        parameters={"dead_load_kN_m2": 8.0, "live_load_kN_m2": 5.0},
    )
    # Heavy parameter set bumps prelim_load_kN_m2 on every option.
    for default, heavy in zip(options_default, options_heavy, strict=True):
        assert heavy.prelim_load_kN_m2 > default.prelim_load_kN_m2


def test_notes_record_missing_parameters() -> None:
    geometry = _geometry(
        [
            _floor("Floor 1", max_x=10.0, max_y=10.0),
            _floor("Roof", max_x=10.0, max_y=10.0, is_roof=True),
        ]
    )
    options = generate_options(geometry, parameters=None)
    assert any("default" in note.lower() for note in options[0].notes)


def test_output_serializes_to_json_safely() -> None:
    geometry = _geometry([_floor("Floor 1", max_x=10.0, max_y=10.0)])
    options: list[StructuralOption] = generate_options(geometry)
    for option in options:
        payload = option.model_dump(mode="json")
        # Round-trip through Pydantic to make sure types stay clean.
        assert StructuralOption.model_validate(payload) == option
