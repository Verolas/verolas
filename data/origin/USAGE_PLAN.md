# Verolas Origin - Data Usage Plan

How each cached data source maps to engine modules, what we
extract, and which output field it ends up in. This document is
the contract between `data/origin/` and `apps/api/verolas_api/workflow/origin/`.

Two-column intent:
- **What the data gives us** (left, factual)
- **Where it lands in code / output** (right, instruction)

## 1. Section property catalogues

### EU steel - `arcelormittal.sections`

| What | Where |
|-|-|
| For each profile family (IPE, HEA, HEB, HEM, IPN, UPE, UPN, UAP, HD, HP): name, A [cm^2], h, b, t_w, t_f, r [mm], A_v [cm^2], I_y, I_z [cm^4], W_el_y, W_el_z, W_pl_y, W_pl_z [cm^3], i_y, i_z [cm], I_t, I_w [cm^6] | `origin/sections.py::load_european_steel_catalogue()` (new function added in P3.D5). Parses the XLSX with `openpyxl`, emits one `Section` per row. Replaces the 8 hand-coded HEB/IPE entries currently in `_STEEL_SECTIONS`. |
| Material grade defaults | Lookup table in `origin/materials.py::EU_STEEL_GRADES` (S235, S275, S355, S460). f_y values from EN 10025. |

### EU concrete + steel design equations - `pip.structuralcodes`

| What | Where |
|-|-|
| EC2 concrete cross-section solver: M_Rd, V_Rd, N_Rd given geometry + rebar + material | `origin/grid.py::_design_members()` calls `structuralcodes.codes.ec2_2023.crosssection_moment_capacity(...)` instead of looking up a flat catalogue value. Per-member moment and shear use real cross-section + rebar config from the AI options. |
| EC3 steel cross-section class + plastic resistance | `origin/sections.py::compute_steel_mrd(section, grade)` calls the EC3 solver. M_Rd now derived from W_pl_y and f_y_d (instead of hardcoded). |
| EC0 partial factors gamma_M0, gamma_M1, gamma_M2 | `origin/loads.py::EUROCODE_GAMMA_M`. |

### US steel - `aisc.shapes_v15`

| What | Where |
|-|-|
| W, HSS, HP, C, MC, L, WT, MT, ST, 2L, 2C, Pipe shapes with: A, d, bf, tf, tw, Z_x, Z_y, I_x, I_y, r_x, r_y, J, C_w | `origin/sections.py::load_aisc_catalogue()` (new function). Read XLSX with `openpyxl`, emit `Section` rows tagged with system_id == "steel_mrf" and jurisdiction == "us". |
| Capacity formulas (M_p, P_n, V_n) per AISC 360-22 Chapters E, F, G | Implemented directly in `origin/sections.py::compute_aisc_mp(section, fy)`. AISC 360-22 PDF is reference only. |

## 2. Cost catalogues

### Multi-region - `ddc.cwicr`

| What | Where |
|-|-|
| Berlin EUR rates: ~5,000 work items with unit (m, m2, kg, m3) and price | New module `origin/cost.py::BerlinCostCatalogue`. Loads `ddc-cwicr/repo/data/ddc_de_berlin.parquet` into a pandas DataFrame on startup. Lookups by material + unit. |
| US USD rates: similar shape | `origin/cost.py::USCostCatalogue`. Loads `ddc_usa_usd.parquet`. |
| Attribution: CC-BY-4.0 - must appear in PDF | `origin/export.py::_references_section()` includes the DDC string from MANIFEST.md. Required for every PDF. |

Wiring into the grid engine:

```python
# origin/grid.py - replace flat unit_cost_eur_per_m with:
cost_catalogue = get_cost_catalogue(jurisdiction, base_year=2024)
cost_per_m = cost_catalogue.lookup(section.material_class, "m")
boq_total += cost_per_m * member_length
```

### DE time-adjustment - `destatis.baupreisindex`

| What | Where |
|-|-|
| Wohngebäude (residential) construction price index, quarterly series | `origin/cost.py::DestatisIndex`. Reads the DBnomics CSV. `factor(base_year, target_year) -> float` multiplies catalogue prices to current date. |

### US validation - `nyc.dob_permits`

| What | Where |
|-|-|
| Sample of approved NYC permits with declared estimated_job_costs and GFA | Tests only - `apps/api/tests/origin/test_cost_us_sanity.py`. Asserts our $/ft^2 estimates fall within the empirical NYC range for a project type. |

## 3. Loads

### US - `asce7.hazard_tool`

| What | Where |
|-|-|
| Site-specific design wind speed V (mph), snow load P_g (psf), seismic SDS / SD1, design category | `origin/loads.py::UsLoads.fetch(address)` POSTs the address to https://asce7hazardtool.online/. Cached per (lat, lng) round-trip. |
| Output fields populated on the StructuralOption | `loads.wind_kn_m2`, `loads.snow_kn_m2`, `loads.seismic_sds`. |

### EU - code-defaults

EC1 wind / snow / seismic require map data. For P3 we ship
the default EN 1991-1-3 (snow) zone table embedded in code, and
default EN 1991-1-4 wind table per-country (DE, AT, CH, FR, IT,
ES, NL, BE, UK). Country selected from project metadata.

## 4. Reference + cross-check material

These don't drive code paths but back up the engineer's review:

| Source | Used as |
|-|-|
| `jrc.steel_examples` (JRC96658) | Test vectors. `tests/origin/test_steel_capacity_jrc.py` re-runs JRC worked examples and asserts our capacity result matches within 2%. |
| `jrc.concrete_examples` | Test vectors for `structuralcodes` integration. |
| `eurocodeapplied.tables` | Reference HTML snapshot. Tests parse the table and cross-check our ArcelorMittal-derived numbers. |
| `aisc.spec_360_22` (PDF) | Engineer reference only. Cited per-clause in code comments where capacity equations are implemented. |

## 5. Pluggable architecture sketch (target for P3 main PR)

```
apps/api/verolas_api/workflow/origin/
├── data_loader.py          # NEW. Reads sources.yaml; resolves
│                            #   source_id -> local file path.
├── sections.py             # Modified. load_european_steel_catalogue(),
│                            #   load_aisc_catalogue(), in addition to
│                            #   the legacy in-code catalogue (kept as
│                            #   fallback for CLT until P3.D11).
├── cost.py                 # NEW. BerlinCostCatalogue, USCostCatalogue,
│                            #   DestatisIndex, get_cost_catalogue().
├── loads.py                # NEW for US. UsLoads.fetch() against
│                            #   asce7hazardtool.online.
├── materials.py            # NEW. Material grade lookups: EU_STEEL_GRADES,
│                            #   US_STEEL_GRADES, EU_CONCRETE_GRADES.
├── grid.py                 # Modified to call structuralcodes for EC2,
│                            #   compute_aisc_mp for US steel, and the
│                            #   cost catalogues for BoQ.
└── export.py               # Modified. _references_section() pulls
                             #   attribution strings from MANIFEST.md +
                             #   sources.yaml, listing every source the
                             #   project's calculations touched.
```

## 6. Order of work (P3 sub-tasks beyond D1)

1. **D2 - D5**: cache the raw files on developer machines via
   fetch_all.sh. Manual sources still print instructions.
2. **D6**: add `structuralcodes`, `eurocodepy`, `FoundationDesign`
   to `apps/api/pyproject.toml` with version pins above.
3. **D11 (new)**: write `data_loader.py` + plug AISC + ArcelorMittal
   into `sections.py`. Acceptance: a new test
   `tests/origin/test_section_catalogue_loaded.py` confirms >100
   European sections and >200 US sections are available at runtime.
4. **D12 (new)**: write `cost.py` + plug DDC CWICR. Acceptance:
   `tests/origin/test_cost_berlin_eur.py` checks a known beam unit
   rate is within ±15% of catalogue Berlin median.
5. **D13 (new)**: write `loads.py` + plug ASCE 7-22 hazard tool.
   Acceptance: integration test against the live API for a fixed
   NYC address, skipped if offline.
6. **D14 (new)**: update `export.py::_references_section()` to emit
   the live attributions from sources.yaml. Acceptance: PDF audit
   confirms a "References" section with at least the DDC + AISC +
   structuralcodes lines on any output.

P4 (i18n) and P5 (per-country adapters) layer on top of this
foundation.
