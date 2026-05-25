"use client";

// Roof framing model for the Origin roof_framing node.
//
// The engineer places truss zones (axis-aligned rectangles) over the
// roof footprint plus optional girder trusses and beams (lines) that
// run across the rest of the structure. Coverage validation requires
// the union of truss zones to fully cover the roof footprint, mirroring
// Genia's "Regular Truss must fully cover the roof area" guarantee.

import type { Extents, Point2D } from "@/components/origin/geometry";

export type FramingKind = "regular_truss" | "girder_truss" | "beam";

export interface TrussZone {
  id: string;
  // Axis-aligned rectangle in floor-local model coords (metres).
  min_x: number;
  min_y: number;
  max_x: number;
  max_y: number;
  // Spacing of trusses inside the zone. Stored for downstream
  // consumers (AI options); the canvas does not draw individual
  // trusses at this stage to keep render cost low.
  spacing_m: number;
  // Cardinal orientation of the trusses inside the zone. The renderer
  // draws a few preview lines so the engineer can sanity-check.
  direction: "east_west" | "north_south";
}

export interface FramingLine {
  id: string;
  kind: "girder_truss" | "beam";
  start: Point2D;
  end: Point2D;
  // Member size encoded as a string so the AI options adapter can
  // interpret based on jurisdiction (e.g. "GLT 320x180" or "W14x22").
  size: string;
}

export interface CoverageReport {
  covered_m2: number;
  total_m2: number;
  coverage_pct: number;
  uncovered_cells: { min_x: number; min_y: number; max_x: number; max_y: number }[];
  cell_size_m: number;
}

export interface RoofFraming {
  roof_floor_key: string;
  roof_outline: Extents;
  truss_zones: TrussZone[];
  framing_lines: FramingLine[];
  coverage: CoverageReport;
}

const DEFAULT_SPACING_M = 0.61; // ~24 inches
const RASTER_CELL_M = 0.25;

// Stable id generator scoped to the roof framing model.
export function newFramingId(prefix: string, used: { id: string }[]): string {
  const set = new Set(used.map((x) => x.id));
  for (let i = 0; i < 100000; i++) {
    const candidate = `${prefix}_${i}`;
    if (!set.has(candidate)) return candidate;
  }
  throw new Error(`could not generate a unique framing id for ${prefix}`);
}

// Build an empty framing payload anchored to a roof floor.
export function emptyFraming(roofFloorKey: string, roofOutline: Extents): RoofFraming {
  return {
    roof_floor_key: roofFloorKey,
    roof_outline: roofOutline,
    truss_zones: [],
    framing_lines: [],
    coverage: computeCoverage(roofOutline, [], RASTER_CELL_M),
  };
}

// Build a default truss zone for the new-zone tool. The engineer can
// resize / move after.
export function defaultTrussZone(
  used: { id: string }[],
  bounds: { min_x: number; min_y: number; max_x: number; max_y: number },
): TrussZone {
  return {
    id: newFramingId("zone", used),
    min_x: bounds.min_x,
    min_y: bounds.min_y,
    max_x: bounds.max_x,
    max_y: bounds.max_y,
    spacing_m: DEFAULT_SPACING_M,
    direction: bounds.max_x - bounds.min_x >= bounds.max_y - bounds.min_y
      ? "east_west"
      : "north_south",
  };
}

// Rasterised coverage: divide the roof outline into a grid of cells,
// mark each cell covered if its centre falls inside any truss zone,
// then return covered area + a list of uncovered-cell rectangles for
// the canvas to highlight in red.
//
// We use rasterisation (not analytic polygon-set ops) because axis-
// aligned union of overlapping rectangles intersected with an axis-
// aligned roof outline collapses cleanly onto a regular grid, the
// math is robust against floating-point drift, and the uncovered
// cells are themselves drawable rectangles for the validator banner.
export function computeCoverage(
  roof: Extents,
  zones: TrussZone[],
  cellSize: number = RASTER_CELL_M,
): CoverageReport {
  const width = Math.max(0, roof.max_x - roof.min_x);
  const height = Math.max(0, roof.max_y - roof.min_y);
  const cols = Math.max(1, Math.ceil(width / cellSize));
  const rows = Math.max(1, Math.ceil(height / cellSize));
  const cellArea = cellSize * cellSize;

  let covered = 0;
  const uncovered: CoverageReport["uncovered_cells"] = [];

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const cx = roof.min_x + (col + 0.5) * cellSize;
      const cy = roof.min_y + (row + 0.5) * cellSize;
      // Cells outside the roof outline do not count toward area.
      if (cx > roof.max_x || cy > roof.max_y) continue;
      const insideZone = zones.some(
        (z) => cx >= z.min_x && cx <= z.max_x && cy >= z.min_y && cy <= z.max_y,
      );
      if (insideZone) {
        covered += 1;
      } else {
        uncovered.push({
          min_x: roof.min_x + col * cellSize,
          min_y: roof.min_y + row * cellSize,
          max_x: roof.min_x + (col + 1) * cellSize,
          max_y: roof.min_y + (row + 1) * cellSize,
        });
      }
    }
  }

  const totalCells = cols * rows;
  const total = totalCells * cellArea;
  const coveredArea = covered * cellArea;
  const coveragePct = total > 0 ? (coveredArea / total) * 100 : 0;

  return {
    covered_m2: coveredArea,
    total_m2: total,
    coverage_pct: coveragePct,
    uncovered_cells: uncovered,
    cell_size_m: cellSize,
  };
}

// Recompute coverage and return a new RoofFraming. The caller stores
// it back as state.
export function withRecomputedCoverage(framing: RoofFraming): RoofFraming {
  return {
    ...framing,
    coverage: computeCoverage(framing.roof_outline, framing.truss_zones),
  };
}
