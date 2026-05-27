"""Verify the steel catalogues load from vendored open-data files.

EU sections come from pcachim/eurocodepy's `i_profiles_euro.json`
(MIT). US W-shapes come from the AISC v15.0 SI sheet via the
ambaker1/aisc-csv MIT mirror. Capacities are computed at S355 and
A992 respectively; the hand-calculated values below pin the math
against the catalogue values published by each source.
"""

from __future__ import annotations

import pytest

from verolas_api.workflow.origin.sections import (
    Section,
    heaviest,
    sections_for,
    smallest_passing_beam,
    smallest_passing_column,
)

# ---------------------------------------------------------------------
# Catalogue size assertions. Catches accidental deletion of data files.
# ---------------------------------------------------------------------


def test_eu_steel_catalogue_has_full_family_coverage() -> None:
    beams = sections_for("steel_mrf", "beam", jurisdiction="eu")
    columns = sections_for("steel_mrf", "column", jurisdiction="eu")
    assert len(beams) >= 80, f"expected >=80 EU beams, got {len(beams)}"
    assert len(beams) == len(columns)
    # All four families must be present.
    families = {s.name[:3] for s in beams}
    assert {"IPE", "HEA", "HEB", "HEM"} <= families


def test_us_steel_catalogue_has_full_w_shape_coverage() -> None:
    beams = sections_for("steel_mrf", "beam", jurisdiction="us")
    columns = sections_for("steel_mrf", "column", jurisdiction="us")
    assert len(beams) >= 200, f"expected >=200 US W-shape beams, got {len(beams)}"
    assert len(beams) == len(columns)
    # Every entry starts with "W" - only W-shapes load from the v15 SI sheet.
    assert all(s.name.startswith("W") for s in beams)


def test_rank_is_monotonic_per_role() -> None:
    for jur in ("eu", "us"):
        beams = sections_for("steel_mrf", "beam", jurisdiction=jur)
        assert [s.rank for s in beams] == sorted(s.rank for s in beams)
        # The sort key is rank, and self_weight should also be monotonic
        # because we sort the source data by mass before assigning rank.
        weights = [s.self_weight_kg_per_m for s in beams]
        assert weights == sorted(weights)


# ---------------------------------------------------------------------
# Capacity math vs published catalogue values.
# ---------------------------------------------------------------------


def _section_by_name(name_prefix: str, jurisdiction: str, role: str) -> Section:
    sections = sections_for("steel_mrf", role, jurisdiction=jurisdiction)  # type: ignore[arg-type]
    matches = [s for s in sections if s.name.startswith(name_prefix)]
    assert matches, f"no section matching {name_prefix!r} in {jurisdiction} {role}"
    return matches[0]


def test_heb200_s355_moment_matches_hand_calc() -> None:
    """W_pl,y(HEB200) = 642.5 cm^3 -> M_pl,Rd(S355) = 228.1 kNm."""
    heb200 = _section_by_name("HEB200", "eu", "beam")
    assert heb200.moment_capacity_kNm == pytest.approx(228.1, abs=0.2)


def test_ipe300_s355_moment_matches_hand_calc() -> None:
    """W_pl,y(IPE300) = 628.4 cm^3 -> M_pl,Rd(S355) = 223.1 kNm."""
    ipe300 = _section_by_name("IPE300", "eu", "beam")
    assert ipe300.moment_capacity_kNm == pytest.approx(223.1, abs=0.2)


def test_heb200_column_buckling_is_within_curve_b_envelope() -> None:
    """HEB200 N_b,Rd at L=3 m: weak axis i_z=5.07 cm gives χ~0.74."""
    heb200 = _section_by_name("HEB200", "eu", "column")
    n_squash = 78.08 * 100 * 355 / 1000.0  # A * f_y in kN, no buckling
    assert 0.6 * n_squash < heb200.axial_capacity_kN < 0.85 * n_squash


def test_w360x44_a992_moment_matches_hand_calc() -> None:
    """Zx(W360X44) = 770 x 10^3 mm^3 -> M_p(A992) = 265.7 kNm."""
    w360x44 = _section_by_name("W360X44", "us", "beam")
    assert w360x44.moment_capacity_kNm == pytest.approx(265.7, abs=2.0)


# ---------------------------------------------------------------------
# Selection helpers honour jurisdiction.
# ---------------------------------------------------------------------


def test_smallest_passing_beam_default_eu() -> None:
    beam = smallest_passing_beam("steel_mrf", 250.0)
    assert beam is not None
    assert beam.jurisdiction == "eu"
    assert beam.moment_capacity_kNm >= 250.0


def test_smallest_passing_beam_us_returns_us_section() -> None:
    beam = smallest_passing_beam("steel_mrf", 250.0, jurisdiction="us")
    assert beam is not None
    assert beam.jurisdiction == "us"
    assert beam.name.startswith("W")
    assert beam.moment_capacity_kNm >= 250.0


def test_smallest_passing_column_returns_buckling_compliant_section() -> None:
    column = smallest_passing_column("steel_mrf", 2000.0)
    assert column is not None
    assert column.axial_capacity_kN >= 2000.0


def test_heaviest_eu_steel_is_hem_family() -> None:
    h = heaviest("steel_mrf", "beam")
    assert h.name.startswith("HEM")


def test_heaviest_us_steel_is_w_shape() -> None:
    h = heaviest("steel_mrf", "beam", jurisdiction="us")
    assert h.name.startswith("W")


# ---------------------------------------------------------------------
# RC + CLT catalogues are unaffected by jurisdiction.
# ---------------------------------------------------------------------


def test_rc_catalogue_unchanged() -> None:
    beams = sections_for("rc_flat_slab", "beam")
    columns = sections_for("rc_flat_slab", "column")
    assert len(beams) == 3
    assert len(columns) == 3


def test_clt_catalogue_unchanged() -> None:
    beams = sections_for("clt_hybrid", "beam")
    columns = sections_for("clt_hybrid", "column")
    assert len(beams) == 3
    assert len(columns) == 3


def test_jurisdiction_ignored_for_non_steel_systems() -> None:
    """RC + CLT have no jurisdiction split. Passing 'us' must not change result."""
    assert sections_for("rc_flat_slab", "beam") == sections_for(
        "rc_flat_slab", "beam", jurisdiction="us"
    )
