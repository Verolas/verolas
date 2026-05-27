# Verolas Origin — Open Data Manifest

Every data source the Origin engine consumes, with citation,
license, attribution, acquisition recipe, and the engine module
that uses it. Files in subdirectories are local caches; the
canonical source-of-truth is the URL recorded here.

This folder is **gitignored** (see `.gitignore` at repo root). The
`scripts/fetch_all.sh` script reproduces the local cache from the
canonical URLs on any developer machine. Treat the local files as
ephemeral.

## Why this exists

Real engineering output requires traceable numbers. Every cost,
every section capacity, every load factor in the Origin PDF
report must trace back to a published source. This manifest is
the table of contents for those sources.

## Source priority

When two sources cover the same datum, priority is:

1. **Code or specification** (AISC 360-22, Eurocode JRC) — the
   legal document
2. **Manufacturer catalogue** (ArcelorMittal, AISC Shapes) — for
   geometric properties
3. **Industry-standard cost database** (DDC CWICR, Destatis) —
   for unit rates
4. **Computed values** via published Python packages
   (structuralcodes, eurocodepy) — for code-compliant equations

## Sources at a glance

| ID | Source | Region | License | Format | Role |
|---|---|---|---|---|---|
| aisc.shapes_v15 | AISC Shapes v15.0 (via ambaker1/aisc-csv MIT mirror) | US | MIT wrapper, AISC public-release data | XLSX + 2 CSVs | US section geometry |
| aisc.spec_360_22 | ANSI/AISC 360-22 Specification (manual click-through) | US | AISC public release | PDF | US steel design equations |
| jrc.steel_examples | JRC Design of Steel Buildings — Worked Examples (JRC96658) | EU | EC public-domain reuse | PDF | EU steel worked examples |
| jrc.concrete_examples | JRC Design of Concrete Buildings — Worked Examples (JRC89037) | EU | EC public-domain reuse | PDF | EU concrete worked examples |
| jrc.bridge_examples | JRC Bridge Design Worked Examples (EUR 25193) | EU | EC public-domain reuse | PDF | EU bridge / composite worked examples |
| jrc.seismic_examples | JRC EC8 Seismic Design Worked Examples (EUR 25204) | EU | EC public-domain reuse | PDF | EU seismic worked examples |
| eu-steel.eurocodepy | pcachim/eurocodepy data JSONs (I, CHS, RHS, SHS profiles) | EU | MIT | JSON | EU section geometry + EC3 pre-computed design resistance |
| arcelormittal.sections | ArcelorMittal European Sections catalogue (manual click-through) | EU | manufacturer commercial info | XLS | EU section geometry cross-check |
| pip.structuralcodes | `structuralcodes` PyPI (fib International) | Universal | MIT | Python pkg | EC2 concrete capacity equations |
| ddc.cwicr | DDC CWICR Open Construction Cost Database | 30 regions | CC-BY-4.0 (data); Apache-2.0 (code) | XLSX / Parquet / CSV / Qdrant | Cost catalogue (Berlin EUR + US USD) |
| destatis.baupreisindex | Destatis Baupreisindex (via DBnomics mirror) | DE | Datenlizenz Deutschland 2.0 | CSV | DE cost time-adjustment factor |
| nyc.dob_permits | NYC OpenData DOB Permit Issuance | NYC | NYC Open Data Public Domain | CSV | US cost real-project validation |
| eurocodeapplied.tables | EurocodeApplied IPE/HEA/HEB design properties | EU | website terms, free reference | HTML | EU section properties (cross-check) |
| asce7.hazard_tool | ASCE 7-22 Hazard Tool | US | ASCE web service | JSON API | US site-specific loads |

## Attribution requirements that ship in the PDF report

The Origin PDF report **must include** the following attribution
strings on the References page when the relevant data is used:

- **DDC CWICR**: "Cost basis derived from the DDC CWICR Open
  Construction Cost Database, distributed under CC-BY-4.0.
  https://github.com/datadrivenconstruction/OpenConstructionEstimate-DDC-CWICR"
- **AISC**: "Section properties: AISC Shapes Database v15.0
  (© American Institute of Steel Construction), redistributed via
  the ambaker1/aisc-csv MIT mirror. Capacities computed per
  ANSI/AISC 360-22."
- **eurocodepy**: "European steel section properties: Paulo Cachim
  / eurocodepy (MIT). Cross-referenced against EurocodeApplied
  tables and EN 10365:2017."
- **JRC Eurocode background**: "Eurocode interpretation guided by
  JRC Technical Reports, EU Commission Joint Research Centre,
  freely available at https://eurocodes.jrc.ec.europa.eu."
- **structuralcodes**: "Concrete capacity computations performed
  via the `structuralcodes` Python library, fib International
  Federation for Structural Concrete, MIT License."
- **ArcelorMittal**: "European section properties: ArcelorMittal
  Sections Catalogue, used as engineering reference."
- **Destatis**: "Construction cost time-adjustment: Statistisches
  Bundesamt (Destatis) Baupreisindex, Datenlizenz Deutschland 2.0."

## Detailed source records

### `aisc.shapes_v15`

- **Name**: AISC Shapes Database v15.0
- **Publisher**: American Institute of Steel Construction
- **Date**: 2017 (15th edition Manual companion), still current
- **URL**: https://www.aisc.org/publications/steel-construction-manual-resources/15th-ed-steel-construction-manual/shapes-database-v15.0/
- **Direct download**: link from the page above; requires AISC
  click-through (no login)
- **Format**: XLSX (~5 MB), US customary + metric in same workbook
- **Coverage**: every standard US shape (W, S, M, HP, C, MC, L,
  WT, MT, ST, 2L, 2C, HSS rectangular, HSS round, Pipe)
- **License**: AISC public release; AISC permits engineering use
  including in commercial software with citation
- **Consumed by**: `apps/api/verolas_api/workflow/origin/sections.py`
  US catalogue. We parse the XLSX, store the relevant columns
  (A, d, tw, bf, tf, Zx, Zy, Ix, Iy, rx, ry, J, Cw) as a
  Pydantic-typed catalogue at startup.
- **Citation in PDF**: "Section properties per AISC Shapes
  Database v15.0 (2017)."

### `aisc.spec_360_22`

- **Name**: ANSI/AISC 360-22 — Specification for Structural Steel Buildings
- **Publisher**: American Institute of Steel Construction
- **Date**: 2022
- **URL**: https://www.aisc.org/Specification-for-Structural-Steel-Buildings-ANSIAISC-360-22-Download
- **Format**: PDF (~10 MB)
- **License**: AISC public release; PDF is copyrighted but
  redistribution of computed results is fine. Internal reference
  for our equations.
- **Consumed by**: reference document. `origin/sections.py`
  capacity formulas reference specific clauses (e.g. "M_p per
  AISC 360-22 § F2.1", "P_n per AISC 360-22 § E3").
- **Citation in PDF**: "Capacities computed per ANSI/AISC 360-22
  (Sections F2, E3 as applicable)."

### `jrc.steel_examples`

- **Name**: Eurocodes: Background & Applications — Design of Steel Buildings — Worked Examples
- **JRC Report Number**: JRC96658
- **Publisher**: European Commission Joint Research Centre
- **Date**: 2015 (still authoritative for EC interpretation)
- **URL**: https://publications.jrc.ec.europa.eu/repository/handle/JRC96658
- **Format**: PDF (~15 MB)
- **License**: EC public-domain reuse, free download
- **Consumed by**: reference document for our Eurocode 3 (steel)
  capacity equations. Provides worked examples we use as test
  vectors.
- **Citation in PDF**: "Eurocode 3 worked examples: JRC Technical
  Report JRC96658, EU Commission, 2015."

### `jrc.concrete_examples`

- **Name**: Eurocodes: Background & Applications — Design of Concrete Buildings — Worked Examples (and related EC2 reports)
- **JRC Report Number**: JRC110624 / similar
- **Publisher**: EC JRC
- **Date**: various, 2014-2025
- **URL**: https://eurocodes.jrc.ec.europa.eu/learning-corner/publications
- **Format**: PDF (multiple, ~10-30 MB each)
- **License**: EC public-domain reuse
- **Consumed by**: reference for EC2 concrete equations + test
  vectors. Complements `structuralcodes` library.
- **Citation in PDF**: "Eurocode 2 worked examples: JRC Technical
  Reports, EU Commission."

### `arcelormittal.sections`

- **Name**: European Sections — Sales Program Brochure / Properties
- **Publisher**: ArcelorMittal Commercial Sections
- **Date**: current edition (annually refreshed)
- **URL**: https://sections.arcelormittal.com/ (registration may
  be required for the XLS) and
  https://constructalia.arcelormittal.com/en/products/european_sections
- **Format**: XLSX (~10 MB) and PDF brochures (~50 MB)
- **License**: free manufacturer commercial information; usable
  as engineering reference with citation
- **Consumed by**: `origin/sections.py` European catalogue.
  Provides A, h, b, tw, tf, r, A_v, I_y, I_z, W_y, W_z, W_pl_y,
  W_pl_z, i_y, i_z, I_t, I_w for IPE / HEA / HEB / HEM / HD / HP
  / IPN / UPE / UPN / UAP / UE.
- **Citation in PDF**: "European section properties:
  ArcelorMittal Sections Catalogue, EN 10365:2017."

### `pip.structuralcodes`

- **Name**: structuralcodes
- **Publisher**: fib — International Federation for Structural Concrete
- **PyPI**: https://pypi.org/project/structuralcodes/
- **GitHub**: https://github.com/fib-international/structuralcodes
- **Version pin**: latest stable; specify in pyproject.toml
- **License**: MIT
- **Consumed by**: `origin/grid.py` Eurocode 2 concrete sections.
  Replaces our hand-rolled RC capacity formulas with the fib
  reference implementation. Drop-in for `_pick_beam` and
  `_pick_column` when system_id == "rc_flat_slab" and
  jurisdiction is European.
- **Citation in PDF**: "Concrete member design per Eurocode 2 via
  the `structuralcodes` library (fib International, MIT License)."

### `pip.eurocodepy`

- **Name**: eurocodepy
- **PyPI**: https://pypi.org/project/eurocodepy/
- **License**: MIT
- **Consumed by**: utility module for load combinations (EC0) and
  action effects (EC1). Lower priority than structuralcodes but
  fills gaps for EC1 actions.

### `pip.foundation_design`

- **Name**: FoundationDesign
- **GitHub**: https://github.com/kunle009/FoundationDesign
- **License**: MIT
- **Consumed by**: future `origin/foundations.py` for footing /
  pile-cap sizing per EC2 + EC7. Not in P3 scope but pinned now.

### `ddc.cwicr`

- **Name**: DDC CWICR Open Construction Cost Database
- **Publisher**: DataDrivenConstruction.io
- **GitHub**: https://github.com/datadrivenconstruction/OpenConstructionEstimate-DDC-CWICR
- **License**: **CC-BY-4.0 for the DATA**; Apache-2.0 for the code
- **Format**: XLSX (~150-400 MB), Parquet (~55 MB), CSV (~1.3 GB),
  Qdrant vectors
- **Coverage**: 55,000+ work items, 27,000+ resources, 30
  regions; **specifically includes `ddc_de_berlin` (Berlin EUR)
  and `ddc_usa_usd` (US)**
- **Consumed by**: new `origin/cost.py` module. We load the
  Parquet files for Berlin + US into in-process pandas
  DataFrames at startup, look up unit rates per material/work
  item, multiply by the member-schedule quantities from the
  grid engine.
- **Attribution required in PDF (CC-BY-4.0)**: yes, explicit
  string + link to the GitHub repo.

### `destatis.baupreisindex`

- **Name**: Baupreisindex (Construction Price Index)
- **Publisher**: Statistisches Bundesamt (Destatis)
- **API root**: https://www-genesis.destatis.de/genesis/online
  (GENESIS-Online; free, registration required for full API
  but most series are publicly downloadable as CSV)
- **DBnomics mirror**: https://db.nomics.world/DESTATIS/61261BJ008
- **Format**: CSV / JSON API
- **License**: Datenlizenz Deutschland — Namensnennung 2.0 (open
  data licence; commercial use OK with attribution)
- **Consumed by**: `origin/cost.py` time-adjustment helper.
  DDC CWICR base costs are pegged to a base year; we apply the
  current Baupreisindex to project them forward.
- **Citation**: "Cost time-adjustment: Destatis Baupreisindex
  (Wohngebäude), © Statistisches Bundesamt 2026, dl-de/by-2.0."

### `nyc.dob_permits`

- **Name**: DOB Permit Issuance / DOB NOW Build Approved Permits
- **Publisher**: City of New York
- **URL**: https://data.cityofnewyork.us/Housing-Development/DOB-Permit-Issuance/ipu4-2q9a
- **Format**: CSV (~2 GB if full export); subset is enough
- **License**: NYC OpenData Public Domain
- **Consumed by**: `origin/cost.py` validation/test data only.
  Used to sanity-check DDC US estimates against real NYC project
  totals.

### `eurocodeapplied.tables`

- **URL**: https://eurocodeapplied.com/design/en1993/ipe-hea-heb-hem-design-properties
- **Format**: HTML tables; we save a snapshot for offline reference
- **License**: website terms; engineering reference use is fine
- **Consumed by**: cross-check reference vs ArcelorMittal data
  during testing

### `asce7.hazard_tool`

- **URL**: https://asce7hazardtool.online/
- **Format**: JSON API behind web form
- **License**: ASCE web service; ToS check required for SaaS use
- **Consumed by**: `origin/loads.py` (future) for US runs.
  Sends an address, receives the ASCE 7-22 design parameters
  (wind speed, snow load, seismic SDS/SD1, etc.)

## What we DO NOT have (still paid)

- **DIN EN ... /NA (German National Annex parameters)** — each
  document ~€100-220 from https://www.dinmedia.de. Required if a
  particular NA factor materially differs from the default EC
  value. Defer until first real German Bauamt submission.
- **AISC Steel Construction Manual 16th Edition** — ~$415 with
  design-aid tables. Not required because the spec + shapes are
  free; nice-to-have for connection design tables (Part 9).
- **BKI Baukosten Gebäude/Positionen** — replaced by DDC CWICR
  for v1. Re-evaluate if engineers tell us DDC numbers don't
  match their experience.
- **RSMeans** — replaced by DDC CWICR + NYC OpenData for v1.

## Re-fetching the cache

```bash
cd data/origin
./scripts/fetch_all.sh  # idempotent; redownloads only missing files
./scripts/validate_manifest.py  # checks sha256 sums
```

The Python loader (`apps/api/verolas_api/workflow/origin/data_loader.py`,
to be added in P3) reads `sources.yaml` and resolves to local
paths under `data/origin/{source_id}/`.
