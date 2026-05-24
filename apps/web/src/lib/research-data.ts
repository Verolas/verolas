/**
 * Sample structural-engineering clauses for the Research surface.
 *
 * Real licensed code text comes through a separate ingest pipeline.
 * This stub gives the UI enough shape to render the project-scoped
 * tree, the search hits, and the cross-code comparison while the
 * licensing pipeline lands.
 */

export type CodeId =
  | "EN1990"
  | "EN1991-1-1"
  | "EN1992-1-1"
  | "EN1993-1-1"
  | "EN1997-1"
  | "DIN_NA_EN1992"
  | "SIA_262"
  | "ACI_318"
  | "ASCE_7"
  | "AISC_360";

export interface CodeMeta {
  id: CodeId;
  short: string;
  title: string;
  region: string[];
}

export const CODES: CodeMeta[] = [
  { id: "EN1990", short: "EN 1990", title: "Basis of structural design", region: ["de", "ch", "at", "fr", "nl", "be", "uk"] },
  { id: "EN1991-1-1", short: "EN 1991-1-1", title: "Densities, self-weight, imposed loads", region: ["de", "ch", "at", "fr", "nl", "be", "uk"] },
  { id: "EN1992-1-1", short: "EN 1992-1-1", title: "Design of concrete structures", region: ["de", "ch", "at", "fr", "nl", "be", "uk"] },
  { id: "EN1993-1-1", short: "EN 1993-1-1", title: "Design of steel structures", region: ["de", "ch", "at", "fr", "nl", "be", "uk"] },
  { id: "EN1997-1", short: "EN 1997-1", title: "Geotechnical design", region: ["de", "ch", "at", "fr", "nl", "be", "uk"] },
  { id: "DIN_NA_EN1992", short: "DIN EN 1992 NA", title: "German National Annex", region: ["de"] },
  { id: "SIA_262", short: "SIA 262", title: "Concrete structures (Switzerland)", region: ["ch"] },
  { id: "ACI_318", short: "ACI 318", title: "Building code for structural concrete", region: ["us"] },
  { id: "ASCE_7", short: "ASCE 7", title: "Minimum design loads and associated criteria", region: ["us"] },
  { id: "AISC_360", short: "AISC 360", title: "Specification for structural steel buildings", region: ["us"] },
];

export interface ClauseStub {
  codeId: CodeId;
  number: string;
  title: string;
  topic: string;
  summary: string;
}

export const CLAUSES: ClauseStub[] = [
  {
    codeId: "EN1992-1-1",
    number: "6.4",
    title: "Punching shear",
    topic: "design verification",
    summary:
      "Design rules for punching shear of slabs supported on columns or under concentrated loads. Includes critical perimeter definition u1 at 2d from the loaded area and the basic check VEd <= vRd,c·u1·d.",
  },
  {
    codeId: "EN1992-1-1",
    number: "9.2.1",
    title: "Minimum and maximum reinforcement areas (beams)",
    topic: "reinforcement",
    summary:
      "Establishes As,min = 0.26·(fctm/fyk)·bt·d but not less than 0.0013·bt·d for tensile reinforcement in beams. The maximum As,max = 0.04·Ac applies outside lap regions.",
  },
  {
    codeId: "EN1992-1-1",
    number: "9.5.2",
    title: "Longitudinal reinforcement (columns)",
    topic: "reinforcement",
    summary:
      "Minimum longitudinal reinforcement is the greater of 0.10·NEd/fyd and 0.002·Ac. Maximum is 0.04·Ac outside laps. Bars must be at least diameter 8 mm.",
  },
  {
    codeId: "EN1992-1-1",
    number: "7.3.4",
    title: "Crack width calculation",
    topic: "serviceability",
    summary:
      "Computes the design crack width wk from the maximum crack spacing sr,max and the difference between mean concrete and steel strains. The wk,max limit depends on the exposure class.",
  },
  {
    codeId: "DIN_NA_EN1992",
    number: "NA 9.2.1.1",
    title: "Nationally Determined Parameter for beam As,min",
    topic: "national annex",
    summary:
      "The German NA confirms the recommended values for As,min and adds restrictions for high-strength concrete classes above C50/60.",
  },
  {
    codeId: "EN1990",
    number: "6.4.3.2",
    title: "Combination of actions for ULS persistent and transient",
    topic: "load combinations",
    summary:
      "Sets the partial factors γG = 1.35 (unfavourable permanent) and γQ = 1.5 (unfavourable variable), with ψ0 combination values for non-leading variable actions.",
  },
  {
    codeId: "EN1991-1-1",
    number: "6.3.1.1",
    title: "Imposed loads in residential and office areas",
    topic: "imposed loads",
    summary:
      "Defines characteristic values qk for residential category A (1.5 to 2.0 kN/m²) and office category B (2.5 to 3.0 kN/m²), with αA reduction factors for large tributary areas.",
  },
  {
    codeId: "EN1993-1-1",
    number: "6.2.4",
    title: "Compression members (steel)",
    topic: "design verification",
    summary:
      "Verifies a member in pure compression against the design buckling resistance Nb,Rd = χ·A·fy/γM1 with the reduction factor χ taken from the appropriate buckling curve.",
  },
  {
    codeId: "EN1997-1",
    number: "6.5.2",
    title: "Bearing resistance of shallow foundations",
    topic: "foundations",
    summary:
      "Design approach DA-2 / DA-2* uses partial factors on actions and resistances to verify Rd = Nb,Rd / γR,v >= Vd, with bearing capacity factors Nc, Nq, Nγ from the soil parameters.",
  },
  {
    codeId: "ACI_318",
    number: "25.4",
    title: "Development of reinforcement",
    topic: "reinforcement",
    summary:
      "ACI 318 development length ℓd is computed via tabulated equations with factors for casting position, epoxy coating, and bar size. Hooks and headed bars follow §25.4.3 and §25.4.4.",
  },
  {
    codeId: "ASCE_7",
    number: "12.8",
    title: "Equivalent lateral force procedure (seismic)",
    topic: "seismic",
    summary:
      "Computes the seismic base shear V = Cs·W where Cs is the seismic response coefficient derived from SDS, R, and Ie, with story-force vertical distribution using k = 1 for T <= 0.5s.",
  },
  {
    codeId: "AISC_360",
    number: "B3",
    title: "Design basis (LRFD and ASD)",
    topic: "design basis",
    summary:
      "Sets the dual-design framework: LRFD with load and resistance factor design (φRn >= Ru) or ASD allowable strength design (Rn/Ω >= Ra). LRFD uses ASCE 7 load combinations.",
  },
];

export function clausesByCode(codeId: CodeId): ClauseStub[] {
  return CLAUSES.filter((c) => c.codeId === codeId);
}

export function searchClauses(query: string, scopeCodes?: CodeId[]): ClauseStub[] {
  const q = query.trim().toLowerCase();
  const scope = scopeCodes && scopeCodes.length > 0 ? new Set(scopeCodes) : null;
  return CLAUSES.filter((c) => {
    if (scope && !scope.has(c.codeId)) return false;
    if (!q) return true;
    return (
      c.title.toLowerCase().includes(q) ||
      c.summary.toLowerCase().includes(q) ||
      c.number.toLowerCase().includes(q) ||
      c.topic.toLowerCase().includes(q)
    );
  });
}
