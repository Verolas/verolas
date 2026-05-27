#!/usr/bin/env bash
# Verolas Origin — data acquisition script.
#
# Idempotent. Re-running is safe; existing files are skipped unless
# you pass --force.
#
# Usage:
#   ./fetch_all.sh           # download what is auto-fetchable
#   ./fetch_all.sh --force   # re-download everything
#   ./fetch_all.sh aisc      # only the AISC sources
#
# Sources behind ToS click-throughs or registration walls are
# documented inline; the script prints instructions and exits 0
# without failing the whole run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

FORCE=0
ONLY=""
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        --help|-h)
            sed -n '2,15p' "$0"
            exit 0
            ;;
        *) ONLY="$arg" ;;
    esac
done

should_skip() {
    local prefix="$1"
    [[ -n "$ONLY" && "$prefix" != "$ONLY" ]]
}

ensure_dir() {
    mkdir -p "$1"
}

fetch() {
    local url="$1"
    local dest="$2"
    if [[ -f "$dest" && $FORCE -eq 0 ]]; then
        echo "[skip] $dest already present"
        return 0
    fi
    ensure_dir "$(dirname "$dest")"
    echo "[fetch] $url -> $dest"
    curl --fail --silent --show-error --location \
         --user-agent "verolas-origin-data/0.1" \
         --output "$dest" "$url"
}

manual_note() {
    local id="$1"
    local url="$2"
    cat <<EOF
[manual] $id
    Visit:  $url
    Save to: data/origin/${3:-<see MANIFEST.md>}
EOF
}

# ---------------------------------------------------------------
# JRC: Eurocode steel worked examples (auto-downloadable)
# ---------------------------------------------------------------
if ! should_skip jrc; then
    fetch \
        "https://eurocodes.jrc.ec.europa.eu/sites/default/files/2021-12/jrc_steel_report_2015_07_22.pdf" \
        "$DATA_DIR/jrc/jrc96658_steel_worked_examples.pdf" \
        || echo "[warn] JRC96658 (steel) download failed; URL may have moved."

    fetch \
        "https://publications.jrc.ec.europa.eu/repository/bitstream/JRC89037/reqno_jrc89037_eurocode%202%20design%20of%20concrete%20buildings.%20worked%20examples..pdf" \
        "$DATA_DIR/jrc/jrc89037_concrete_worked_examples.pdf" \
        || echo "[warn] JRC89037 (concrete) download failed; URL may have moved."

    fetch \
        "https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/Bridge_Design-Eurocodes-Worked_examples-main_only.pdf" \
        "$DATA_DIR/jrc/eur25193_bridge_design_worked_examples.pdf" \
        || echo "[warn] EUR 25193 (bridge) download failed."

    fetch \
        "https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/EC8_Seismic_Design_of_Buildings-Worked_examples-main_only.pdf" \
        "$DATA_DIR/jrc/eur25204_ec8_seismic_worked_examples.pdf" \
        || echo "[warn] EUR 25204 (seismic) download failed."
fi

# ---------------------------------------------------------------
# AISC Shapes v15.0 — fetched from the ambaker1/aisc-csv mirror
# (MIT-licensed wrapper around the AISC XLSX; the underlying AISC
# disclaimer applies to engineering use).
# ---------------------------------------------------------------
if ! should_skip aisc; then
    fetch \
        "https://raw.githubusercontent.com/ambaker1/aisc-csv/main/v15.0/aisc-shapes-database-v15.0.xlsx" \
        "$DATA_DIR/aisc/aisc-shapes-database-v15.0.xlsx"
    fetch \
        "https://raw.githubusercontent.com/ambaker1/aisc-csv/main/v15.0/Shapes-US.csv" \
        "$DATA_DIR/aisc/aisc-shapes-v15-us.csv"
    fetch \
        "https://raw.githubusercontent.com/ambaker1/aisc-csv/main/v15.0/Shapes-SI.csv" \
        "$DATA_DIR/aisc/aisc-shapes-v15-si.csv"
    manual_note "aisc.spec_360_22" \
        "https://www.aisc.org/Specification-for-Structural-Steel-Buildings-ANSIAISC-360-22-Download" \
        "aisc/ansi_aisc_360_22.pdf"
fi

# ---------------------------------------------------------------
# European steel sections - from pcachim/eurocodepy (MIT). Ships
# JSONs with IPE/HEA/HEB/HEM + CHS/RHS/SHS dimensional + design
# properties (Npl,Rd, Vpl,Rd, Mel,Rd, Mpl,Rd already computed for
# S235). Equivalent coverage to ArcelorMittal for our purposes.
# ---------------------------------------------------------------
if ! should_skip eu-steel; then
    fetch \
        "https://raw.githubusercontent.com/pcachim/eurocodepy/master/src/eurocodepy/data/i_profiles_euro.json" \
        "$DATA_DIR/eu-steel/i_profiles_euro.json"
    fetch \
        "https://raw.githubusercontent.com/pcachim/eurocodepy/master/src/eurocodepy/data/chs_profiles_euro.json" \
        "$DATA_DIR/eu-steel/chs_profiles_euro.json"
    fetch \
        "https://raw.githubusercontent.com/pcachim/eurocodepy/master/src/eurocodepy/data/rhs_profiles_euro.json" \
        "$DATA_DIR/eu-steel/rhs_profiles_euro.json"
    fetch \
        "https://raw.githubusercontent.com/pcachim/eurocodepy/master/src/eurocodepy/data/shs_profiles_euro.json" \
        "$DATA_DIR/eu-steel/shs_profiles_euro.json"
    fetch \
        "https://raw.githubusercontent.com/pcachim/eurocodepy/master/src/eurocodepy/data/eurocodes.json" \
        "$DATA_DIR/eu-steel/eurocodes.json"
fi

# ---------------------------------------------------------------
# ArcelorMittal: registration required - still archive for the
# official manufacturer catalogue as cross-reference / source-of-truth.
# Used for cross-check when an engineer challenges a section property.
# ---------------------------------------------------------------
if ! should_skip arcelormittal; then
    manual_note "arcelormittal.sections" \
        "https://sections.arcelormittal.com/" \
        "arcelormittal/sections_catalogue.xlsx"
fi

# ---------------------------------------------------------------
# DDC CWICR: git clone
# ---------------------------------------------------------------
if ! should_skip ddc-cwicr; then
    DDC_DIR="$DATA_DIR/ddc-cwicr/repo"
    if [[ -d "$DDC_DIR/.git" && $FORCE -eq 0 ]]; then
        echo "[skip] DDC CWICR already cloned; run 'git -C $DDC_DIR pull' to refresh"
    else
        ensure_dir "$DATA_DIR/ddc-cwicr"
        if [[ -d "$DDC_DIR" && $FORCE -eq 1 ]]; then
            rm -rf "$DDC_DIR"
        fi
        echo "[clone] DDC CWICR (large; this may take a while)"
        git clone --depth 1 \
            https://github.com/datadrivenconstruction/OpenConstructionEstimate-DDC-CWICR.git \
            "$DDC_DIR"
    fi
fi

# ---------------------------------------------------------------
# Destatis Baupreisindex via DBnomics (stable CSV mirror)
# ---------------------------------------------------------------
if ! should_skip destatis; then
    fetch \
        "https://api.db.nomics.world/v22/series/DESTATIS/61261BJ008?format=csv" \
        "$DATA_DIR/destatis/baupreisindex_wohngebaeude.csv" \
        || echo "[warn] Destatis Baupreisindex fetch failed; check DBnomics."
fi

# ---------------------------------------------------------------
# NYC OpenData DOB Permits (limited slice)
# ---------------------------------------------------------------
if ! should_skip nyc-opendata; then
    fetch \
        "https://data.cityofnewyork.us/resource/ipu4-2q9a.csv?\$limit=5000" \
        "$DATA_DIR/nyc-opendata/dob_permit_issuance_sample.csv"
fi

# ---------------------------------------------------------------
# EurocodeApplied static reference
# ---------------------------------------------------------------
if ! should_skip eurocodeapplied; then
    fetch \
        "https://eurocodeapplied.com/design/en1993/ipe-hea-heb-hem-design-properties" \
        "$DATA_DIR/eurocodeapplied/ipe_hea_heb_design_properties.html"
fi

# ---------------------------------------------------------------
# ASCE 7-22 hazard tool: API only, no file to download
# ---------------------------------------------------------------
if ! should_skip asce7; then
    ensure_dir "$DATA_DIR/asce7"
    if [[ ! -f "$DATA_DIR/asce7/README.md" ]]; then
        cat > "$DATA_DIR/asce7/README.md" <<'EOF'
# ASCE 7-22 Hazard Tool

No file to download. The Origin engine queries the ASCE 7-22 Hazard
Tool JSON API at request time.

- Public URL: https://asce7hazardtool.online/
- API contract: documented in `apps/api/verolas_api/workflow/origin/loads.py`
  (to be added in P5)
- ToS: re-check before any SaaS deployment that resells the data
EOF
    fi
fi

echo "[done] fetch_all.sh complete. Run scripts/validate_manifest.py to verify."
