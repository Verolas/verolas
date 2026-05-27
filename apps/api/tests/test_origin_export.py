"""Unit tests for the Origin export pipeline.

Each renderer is tested for byte-level sanity (file signature) plus
the structural assertion that what should be in the output is in fact
there. We never compare full bytes (the libraries change formatting
across versions); we assert presence and shape.
"""

from __future__ import annotations

import io

import ezdxf

from verolas_api.workflow.origin.export import (
    SealInfo,
    build_export_package,
    render_dxf,
    render_ifc,
    render_pdf,
)
from verolas_api.workflow.origin.geometry import (
    Column,
    Extents,
    Floor,
    Geometry,
    Opening,
    Point2D,
    Slab,
    Wall,
)


def _sample_geometry() -> Geometry:
    return Geometry(
        source_format="dxf",
        floors=[
            Floor(
                key="floor_1",
                name="Floor 1",
                elevation_m=0.0,
                extents=Extents(min_x=0.0, min_y=0.0, max_x=10.0, max_y=8.0),
                walls=[
                    Wall(
                        id="w0",
                        start=Point2D(x=0.0, y=0.0),
                        end=Point2D(x=10.0, y=0.0),
                    ),
                    Wall(
                        id="w1",
                        start=Point2D(x=10.0, y=0.0),
                        end=Point2D(x=10.0, y=8.0),
                    ),
                ],
                openings=[
                    Opening(
                        id="o0",
                        center=Point2D(x=5.0, y=0.0),
                        width_m=0.9,
                        kind="door",
                    )
                ],
                slabs=[
                    Slab(
                        id="s0",
                        polygon=[
                            Point2D(x=0.0, y=0.0),
                            Point2D(x=10.0, y=0.0),
                            Point2D(x=10.0, y=8.0),
                            Point2D(x=0.0, y=8.0),
                            Point2D(x=0.0, y=0.0),
                        ],
                    )
                ],
                columns=[
                    Column(id="c0", center=Point2D(x=5.0, y=4.0), size_m=(0.3, 0.3)),
                ],
            ),
            Floor(
                key="floor_2",
                name="Roof",
                elevation_m=3.0,
                extents=Extents(min_x=0.0, min_y=0.0, max_x=10.0, max_y=8.0),
                is_roof=True,
            ),
        ],
    )


def _sample_detail_layout() -> dict[str, object]:
    return {
        "option_id": "balanced_steel_mrf",
        "variant": "balanced",
        "primary_structure": "Steel MRF with secondary beams",
        "bay_grid_m": {"x_m": 5.0, "y_m": 4.0},
        "default_sizes": {"column": "HEB 260 (S355)", "beam": "IPE 360 (S355)"},
        "floors": [
            {
                "floor_key": "floor_1",
                "name": "Floor 1",
                "extents": {"min_x": 0.0, "min_y": 0.0, "max_x": 10.0, "max_y": 8.0},
                "is_roof": False,
                "columns": [
                    {
                        "id": "floor_1_col_0_0",
                        "floor_key": "floor_1",
                        "center": {"x": 0.0, "y": 0.0},
                        "size": "HEB 260 (S355)",
                        "dcr": "between_60_80",
                    },
                    {
                        "id": "floor_1_col_1_0",
                        "floor_key": "floor_1",
                        "center": {"x": 5.0, "y": 0.0},
                        "size": "HEB 260 (S355)",
                        "dcr": "between_80_100",
                    },
                ],
                "beams": [
                    {
                        "id": "floor_1_beam_ew_0_0",
                        "floor_key": "floor_1",
                        "start": {"x": 0.0, "y": 0.0},
                        "end": {"x": 5.0, "y": 0.0},
                        "orientation": "east_west",
                        "size": "IPE 360 (S355)",
                        "dcr": "between_60_80",
                    }
                ],
                "slabs": [],
            }
        ],
    }


def _sample_seal() -> SealInfo:
    return SealInfo(
        engineer_name="Dr. M. Mustermann",
        registration_number="LBO-DE-123456",
        jurisdiction="DE",
        date_iso="2026-05-26",
        statement="Concept design sealed under HOAI LP2.",
    )


def test_render_dxf_produces_per_floor_layouts() -> None:
    geometry = _sample_geometry()
    dxf_bytes = render_dxf(geometry, _sample_detail_layout())
    assert isinstance(dxf_bytes, bytes)
    text = dxf_bytes.decode("utf-8")
    assert text.startswith("  0\nSECTION")  # DXF group code 0 + SECTION

    # Round-trip through ezdxf to confirm the file is valid + has the
    # paper-space layouts we expect.
    doc = ezdxf.read(io.StringIO(text))  # type: ignore[attr-defined]
    layout_names = set(doc.layouts.names())
    assert "Floor 1" in layout_names
    assert "Roof" in layout_names

    # Layers we declared must exist.
    layer_names = {layer.dxf.name for layer in doc.layers}
    for required in ("WALL", "SLAB", "COLUMN_GEOM", "COLUMN_DETAIL", "BEAM", "OPENING"):
        assert required in layer_names


def test_render_dxf_handles_missing_detail_layout() -> None:
    """No detail layout => DXF still has walls + slabs, no detail layers used."""
    geometry = _sample_geometry()
    dxf_bytes = render_dxf(geometry, None)
    text = dxf_bytes.decode("utf-8")
    # Walls + slabs render through LWPOLYLINE entities.
    assert "LWPOLYLINE" in text


def test_render_pdf_starts_with_pdf_magic_and_has_seal_name() -> None:
    pdf_bytes = render_pdf(
        project_id="11111111-1111-1111-1111-111111111111",
        run_id="22222222-2222-2222-2222-222222222222",
        chosen_option={
            "option_id": "balanced_steel_mrf",
            "variant": "balanced",
            "primary_structure": "Steel MRF with secondary beams",
            "bay_grid_m": {"x_m": 7.5, "y_m": 8.0},
            "slab_type": "Composite metal deck, 130 mm topping",
            "material": "S355 + C25/30 topping",
            "prelim_load_kN_m2": 6.0,
            "boq_estimate_eur_m2": 1620,
            "boq_total_eur": 320000,
            "sustainability_note": "Demountable; mid-range embodied carbon.",
            "caveats": ["Fire protection on exposed beams.", "Vibration check."],
            "takeoff": {
                "structural_steel_kg": 12500,
                "concrete_m3": 145,
                "rebar_kg": 8200,
                "clt_m3": 0,
                "glulam_m3": 0,
            },
            "dcr_distribution": {
                "under_60_pct": 0.15,
                "between_60_80": 0.40,
                "between_80_100": 0.40,
                "over_100": 0.05,
            },
        },
        geometry=_sample_geometry(),
        detail_layout=_sample_detail_layout(),
        roof_framing={"coverage": {"coverage_pct": 98.0}},
        seal=_sample_seal(),
    )
    assert pdf_bytes.startswith(b"%PDF-")
    # Engineer name must reach the PDF text stream. PDF compresses
    # streams by default; reportlab keeps the metadata strings searchable.
    blob = pdf_bytes.decode("latin-1", errors="replace")
    assert "Mustermann" in blob or "M. Mustermann" in blob


def test_render_pdf_runs_without_chosen_option_or_detail() -> None:
    """Resilience: minimal upstream is enough to produce a valid PDF."""
    pdf_bytes = render_pdf(
        project_id="proj",
        run_id="run",
        chosen_option=None,
        geometry=_sample_geometry(),
        detail_layout=None,
        roof_framing=None,
        seal=_sample_seal(),
    )
    assert pdf_bytes.startswith(b"%PDF-")


def test_render_ifc_emits_ifc_header_and_storeys() -> None:
    ifc_bytes = render_ifc(_sample_geometry(), _sample_detail_layout())
    assert isinstance(ifc_bytes, bytes)
    text = ifc_bytes.decode("utf-8")
    # ISO 10303-21 STEP header.
    assert text.startswith("ISO-10303-21;")
    assert "IFCBUILDINGSTOREY" in text
    assert "IFCCOLUMN" in text


def test_attributions_always_include_ddc_cwicr_cost_basis() -> None:
    from verolas_api.workflow.origin.export import _attributions_for

    attrs = _attributions_for(None)
    assert any("DDC CWICR" in a for a in attrs)
    assert any("CC-BY-4.0" in a for a in attrs)


def test_attributions_skip_steel_when_chosen_option_is_concrete() -> None:
    from verolas_api.workflow.origin.export import _attributions_for

    chosen = {
        "primary_structure": "RC frame with shear walls",
        "member_schedule": [
            {"section": "RC band 1600x260 (C25/30)"},
            {"section": "RC 400x400 (C25/30)"},
        ],
    }
    attrs = _attributions_for(chosen)
    blob = " ".join(attrs)
    assert "DDC CWICR" in blob
    assert "eurocodepy" not in blob
    assert "Eurocode 3" not in blob
    assert "AISC" not in blob


def test_attributions_include_eu_sources_when_chosen_option_is_steel_mrf() -> None:
    from verolas_api.workflow.origin.export import _attributions_for

    chosen = {
        "primary_structure": "Steel MRF with secondary beams",
        "member_schedule": [
            {"section": "HEA220 (S355)"},
            {"section": "HEB240 (S355)"},
        ],
    }
    attrs = _attributions_for(chosen)
    blob = " ".join(attrs)
    assert "DDC CWICR" in blob
    assert "eurocodepy" in blob
    assert "Eurocode 3" in blob
    assert "AISC" not in blob


def test_attributions_include_aisc_when_us_w_shapes_in_schedule() -> None:
    from verolas_api.workflow.origin.export import _attributions_for

    chosen = {
        "primary_structure": "Steel MRF with secondary beams",
        "member_schedule": [{"section": "W360X51 (A992)"}],
    }
    attrs = _attributions_for(chosen)
    blob = " ".join(attrs)
    assert "AISC Shapes Database v15.0" in blob
    assert "ANSI/AISC 360-22" in blob


def test_render_pdf_metadata_carries_origin_title_and_engineer() -> None:
    """Author + title in the PDF dictionary stay searchable post-compression."""
    pdf_bytes = render_pdf(
        project_id="proj",
        run_id="run",
        chosen_option={
            "option_id": "balanced_steel_mrf",
            "primary_structure": "Steel MRF with secondary beams",
            "member_schedule": [{"section": "HEA220 (S355)"}],
        },
        geometry=_sample_geometry(),
        detail_layout=None,
        roof_framing=None,
        seal=_sample_seal(),
    )
    blob = pdf_bytes.decode("latin-1", errors="replace")
    # Title lives in the unfiltered PDF /Title slot; the engineer name
    # lives in /Author. The references section text itself sits inside
    # a compressed content stream, so we don't grep for it here — the
    # unit tests above cover the picker that determines what goes in.
    assert "Origin" in blob
    assert "Mustermann" in blob


def test_build_export_package_records_warnings_for_missing_inputs() -> None:
    geometry = _sample_geometry()
    result = build_export_package(
        project_id="proj",
        run_id="run",
        reviewed_geometry=geometry.model_dump(mode="json"),
        chosen_option=None,
        detail_layout=None,
        roof_framing=None,
        seal=_sample_seal(),
    )
    assert result.dxf_bytes.startswith(b"  0\nSECTION") or result.dxf_bytes.startswith(b"0\n")
    assert result.pdf_bytes.startswith(b"%PDF-")
    assert result.ifc_bytes.startswith(b"ISO-10303-21;")
    # Both missing inputs should produce two warnings.
    assert len(result.warnings) == 2
    joined = " ".join(result.warnings).lower()
    assert "ai_options" in joined
    assert "detail" in joined
