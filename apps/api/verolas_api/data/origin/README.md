# Origin engine data files

Vendored copies of external open-data sources consumed by
`verolas_api.workflow.origin.sections`. These files ship with the
package so the engine works without filesystem access to the
repo's `data/origin/` cache.

| File | Source | License |
|---|---|---|
| `eu-steel/i_profiles_euro.json` | pcachim/eurocodepy on GitHub | MIT |
| `aisc/aisc-shapes-v15-si.csv` | ambaker1/aisc-csv on GitHub (mirror of AISC Shapes Database v15.0) | MIT wrapper, AISC public-release data |

Attribution strings the Origin PDF report must include:

- "European section properties: pcachim/eurocodepy (MIT)."
- "Section properties: AISC Shapes Database v15.0 (AISC),
  redistributed via the ambaker1/aisc-csv MIT mirror."

To refresh these files, run `data/origin/scripts/fetch_all.sh`
at the repo root and copy the canonical files into the matching
subdirectory here.
