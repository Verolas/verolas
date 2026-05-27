"""Material cost catalogue backed by DDC CWICR open data.

The Origin engine bakes per-metre material costs into the section
library at module load. Those costs come from this module, which
reads a vendored slice of the DDC CWICR Open Construction Cost
Database (CC-BY-4.0):

- `de_berlin_catalog.csv` covers Berlin EUR resource rates.
- `us_usd_catalog.csv` covers United States USD resource rates.

Each entry in the CSV is a single named resource (a material or
labour line item) with average / min / max / median prices and a
usage count. We pin specific DDC entries per material class via the
`_PICKS_*` tables below; the choice deliberately uses readable name
substrings rather than DDC resource codes so future changes are
easier to review.

Citations the Origin PDF must surface whenever this module
contributes to the BoQ:

    Cost basis derived from the DDC CWICR Open Construction Cost
    Database (CC-BY-4.0).
    https://github.com/datadrivenconstruction/OpenConstructionEstimate-DDC-CWICR
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Final, Literal

MaterialClass = Literal[
    "structural_steel",
    "reinforcing_steel",
    "glulam_softwood",
]
Jurisdiction = Literal["eu", "us"]


@dataclass(frozen=True, slots=True)
class CostQuote:
    """One looked-up cost figure plus its DDC provenance."""

    material_class: MaterialClass
    jurisdiction: Jurisdiction
    rate: float
    currency: str
    unit: str  # the DDC source unit (`t`, `ton`, `m3`, `CY`, ...)
    rate_per_kg: float  # normalised mass rate; 0 when the source unit is volumetric
    rate_per_m3: float  # normalised volume rate; 0 when the source unit is mass-based
    source_resource_code: str
    source_resource_name: str
    source_region: str


# Picks per material class. Each row identifies one DDC catalog row
# by a contiguous substring of `resource_name`. The picker filters to
# `type == "Material"` and chooses the row with the highest
# `usage_count` so we land on the most common variant.
#
# Be conservative when changing these: every figure that ships in the
# Origin BoQ ultimately traces back through this table.
_PICKS_EU: Final[dict[MaterialClass, str]] = {
    "structural_steel": "Individuell gefertigte Stahlkonstruktionen aus Walzstahl",
    "reinforcing_steel": "Warmgewalzter Bewehrungsstahl mit periodischem Profil",
    "glulam_softwood": "Schnittholz aus Nadelholz",
}

_PICKS_US: Final[dict[MaterialClass, str]] = {
    "structural_steel": (
        "Auxiliary metal structures predominantly made of thick-gauge steel"
    ),
    "reinforcing_steel": "Hot-rolled smooth reinforcing steel, class A-I",
    "glulam_softwood": "Edged softwood timber",
}

# Unit-to-mass conversions. The DDC catalog reports steel as `t` for
# DE and `ton` for US — both are metric tonnes in this dataset (see
# the DDC dictionary `DATA_DICTIONARY.md`). Volumetric units use the
# US-customary CY (cubic yard) for the US catalogue.
_KG_PER_UNIT: Final[dict[str, float]] = {
    "t": 1000.0,
    "ton": 1000.0,
}
_M3_PER_UNIT: Final[dict[str, float]] = {
    "m3": 1.0,
    "CY": 0.7645549,  # 1 cubic yard in cubic metres
}


def _catalog_path(jurisdiction: Jurisdiction) -> Path:
    base = resources.files("verolas_api").joinpath("data/origin/ddc-cwicr")
    filename = "de_berlin_catalog.csv" if jurisdiction == "eu" else "us_usd_catalog.csv"
    return Path(str(base.joinpath(filename)))


def _load_catalog(jurisdiction: Jurisdiction) -> list[dict[str, str]]:
    with _catalog_path(jurisdiction).open() as fh:
        return list(csv.DictReader(fh))


def _find_row(
    rows: list[dict[str, str]],
    name_substring: str,
) -> dict[str, str]:
    """Return the highest-usage Material row whose name contains `name_substring`."""
    matches = [
        r
        for r in rows
        if r.get("type") == "Material" and name_substring in (r.get("name") or "")
    ]
    if not matches:
        raise LookupError(
            f"DDC catalog has no Material row matching {name_substring!r}"
        )

    def _usage(row: dict[str, str]) -> int:
        value = row.get("usage_count") or "0"
        try:
            return int(float(value))
        except ValueError:
            return 0

    return max(matches, key=_usage)


def _quote_from_row(
    row: dict[str, str],
    material_class: MaterialClass,
    jurisdiction: Jurisdiction,
) -> CostQuote:
    rate = float(row["price_avg"])
    unit = row["unit"]
    currency = row["currency"]
    kg_per_unit = _KG_PER_UNIT.get(unit, 0.0)
    m3_per_unit = _M3_PER_UNIT.get(unit, 0.0)
    rate_per_kg = rate / kg_per_unit if kg_per_unit else 0.0
    rate_per_m3 = rate / m3_per_unit if m3_per_unit else 0.0
    return CostQuote(
        material_class=material_class,
        jurisdiction=jurisdiction,
        rate=rate,
        currency=currency,
        unit=unit,
        rate_per_kg=rate_per_kg,
        rate_per_m3=rate_per_m3,
        source_resource_code=row.get("resource_code", "") or "",
        source_resource_name=row["name"],
        source_region=row.get("parent_collection", "") or "",
    )


def material_rate(
    material_class: MaterialClass,
    *,
    jurisdiction: Jurisdiction = "eu",
) -> CostQuote:
    """Return the DDC CWICR rate for `material_class` in `jurisdiction`.

    Cached per (material_class, jurisdiction) — DDC files don't change
    at runtime, and parsing the CSV on every call is wasteful.
    """
    return _quote_cache[(material_class, jurisdiction)]


def _build_cache() -> dict[tuple[MaterialClass, Jurisdiction], CostQuote]:
    cache: dict[tuple[MaterialClass, Jurisdiction], CostQuote] = {}
    eu_rows = _load_catalog("eu")
    us_rows = _load_catalog("us")
    for material_class, name_substring in _PICKS_EU.items():
        cache[(material_class, "eu")] = _quote_from_row(
            _find_row(eu_rows, name_substring),
            material_class,
            "eu",
        )
    for material_class, name_substring in _PICKS_US.items():
        cache[(material_class, "us")] = _quote_from_row(
            _find_row(us_rows, name_substring),
            material_class,
            "us",
        )
    return cache


_quote_cache: Final[dict[tuple[MaterialClass, Jurisdiction], CostQuote]] = _build_cache()


# Attribution string the Origin PDF references page must surface
# whenever any cost from this module is used in the BoQ.
CWICR_ATTRIBUTION: Final[str] = (
    "Cost basis derived from the DDC CWICR Open Construction Cost "
    "Database (CC-BY-4.0). "
    "https://github.com/datadrivenconstruction/OpenConstructionEstimate-DDC-CWICR"
)


__all__ = [
    "CWICR_ATTRIBUTION",
    "CostQuote",
    "Jurisdiction",
    "MaterialClass",
    "material_rate",
]
