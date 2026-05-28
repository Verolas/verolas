"""Verify the DDC CWICR cost catalogue lookups.

cost.material_rate() must resolve to specific DDC resources that
match the values in the upstream catalog. If the picked row drifts
(DDC re-renumbers, renames, or removes the resource), these tests
catch it before a PDF report ships a misleading BoQ figure.
"""

from __future__ import annotations

import pytest

from verolas_api.workflow.origin import cost

# ---------------------------------------------------------------------
# EU (Berlin) picks.
# ---------------------------------------------------------------------


def test_eu_structural_steel_matches_ddc_berlin_walzstahl_row() -> None:
    quote = cost.material_rate("structural_steel", jurisdiction="eu")
    assert quote.currency == "EUR"
    assert quote.unit == "t"
    # Per the vendored DDC Berlin catalog the "Individuell gefertigte
    # Stahlkonstruktionen aus Walzstahl" row averages 4920.03 EUR/t.
    assert quote.rate == pytest.approx(4920.03, abs=0.5)
    assert quote.rate_per_kg == pytest.approx(4.92, abs=0.01)
    assert "Walzstahl" in quote.source_resource_name


def test_eu_reinforcing_steel_matches_ddc_berlin_bewehrungsstahl_row() -> None:
    quote = cost.material_rate("reinforcing_steel", jurisdiction="eu")
    assert quote.currency == "EUR"
    assert quote.unit == "t"
    assert quote.rate == pytest.approx(1659.32, abs=0.5)
    assert "Bewehrungsstahl" in quote.source_resource_name


def test_eu_glulam_softwood_matches_ddc_berlin_schnittholz_row() -> None:
    quote = cost.material_rate("glulam_softwood", jurisdiction="eu")
    assert quote.currency == "EUR"
    assert quote.unit == "m3"
    assert quote.rate == pytest.approx(504.65, abs=0.5)
    assert quote.rate_per_m3 == pytest.approx(504.65, abs=0.5)
    assert "Schnittholz" in quote.source_resource_name


# ---------------------------------------------------------------------
# US picks.
# ---------------------------------------------------------------------


def test_us_structural_steel_matches_ddc_usa_auxiliary_metal_row() -> None:
    quote = cost.material_rate("structural_steel", jurisdiction="us")
    assert quote.currency == "USD"
    assert quote.unit == "ton"
    assert quote.rate == pytest.approx(2574.21, abs=0.5)
    assert quote.rate_per_kg == pytest.approx(2.5742, abs=0.001)
    assert "Auxiliary metal structures" in quote.source_resource_name


def test_us_reinforcing_steel_matches_ddc_usa_a_i_row() -> None:
    quote = cost.material_rate("reinforcing_steel", jurisdiction="us")
    assert quote.currency == "USD"
    assert quote.unit == "ton"
    assert quote.rate == pytest.approx(840.32, abs=0.5)


def test_us_glulam_softwood_matches_ddc_usa_edged_softwood_row() -> None:
    quote = cost.material_rate("glulam_softwood", jurisdiction="us")
    assert quote.currency == "USD"
    assert quote.unit == "CY"
    assert quote.rate == pytest.approx(244.11, abs=0.5)
    # 1 CY = 0.7645549 m^3, so 244.11 USD/CY ≈ 319.3 USD/m^3.
    assert quote.rate_per_m3 == pytest.approx(319.28, abs=0.5)


# ---------------------------------------------------------------------
# Quote shape + provenance.
# ---------------------------------------------------------------------


def test_quote_carries_provenance_fields() -> None:
    quote = cost.material_rate("structural_steel", jurisdiction="eu")
    assert quote.source_resource_code  # non-empty DDC resource code
    assert quote.source_resource_name
    assert quote.source_region  # DDC parent_collection short-code


def test_attribution_string_is_present() -> None:
    assert "CC-BY-4.0" in cost.CWICR_ATTRIBUTION
    assert "DDC CWICR" in cost.CWICR_ATTRIBUTION


def test_us_structural_steel_rate_per_kg_within_market_range() -> None:
    """Sanity check: US rolled-steel material rate should be 2-4 USD/kg."""
    quote = cost.material_rate("structural_steel", jurisdiction="us")
    assert 2.0 < quote.rate_per_kg < 4.0


def test_eu_structural_steel_rate_per_kg_within_market_range() -> None:
    """EU rolled-steel material rate should be 4-7 EUR/kg."""
    quote = cost.material_rate("structural_steel", jurisdiction="eu")
    assert 4.0 < quote.rate_per_kg < 7.0


# ---------------------------------------------------------------------
# sections.py picks the DDC rate (not the old 1.80 placeholder).
# ---------------------------------------------------------------------


def test_eu_steel_sections_use_ddc_rate_not_placeholder() -> None:
    from verolas_api.workflow.origin.sections import sections_for

    beams = sections_for("steel_mrf", "beam", jurisdiction="eu")
    heb200 = next(b for b in beams if b.name.startswith("HEB200"))
    # HEB200 mass 61.3 kg/m at 4.92 EUR/kg = 301.6 EUR/m.
    assert heb200.unit_cost_eur_per_m == pytest.approx(301.6, abs=1.0)


def test_us_steel_sections_use_us_ddc_rate() -> None:
    from verolas_api.workflow.origin.sections import sections_for

    beams = sections_for("steel_mrf", "beam", jurisdiction="us")
    # W360X51 is ~51 kg/m. At 2.5742 USD/kg DDC rate = ~131.3 USD/m.
    target = next(b for b in beams if b.name.startswith("W360X51"))
    assert target.unit_cost_eur_per_m == pytest.approx(131.3, abs=2.0)
