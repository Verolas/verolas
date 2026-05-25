"use client";

// Detail layout for the `detail_edit` node. Given the option the
// engineer selected at the `select_option` gate, plus the reviewed
// geometry, compute per-member positions (columns at grid intersections,
// beams along grid lines) and seed every member with a DCR sampled from
// the option's DCR distribution.
//
// Numbers are intentionally illustrative, not load-case-verified. The
// responsible engineer refines sizes and connections in the editor
// before the seal step. The point of this layout is to give the
// engineer something concrete and editable on a real plan rather than
// a card of abstract takeoffs.

import type {
  Extents,
  Floor,
  Geometry,
  Point2D,
} from "@/components/origin/geometry";
import type { OriginStructuralOption } from "@/lib/api";

export type DcrBand = "under_60" | "between_60_80" | "between_80_100" | "over_100";

export interface DetailColumn {
  id: string;
  floor_key: string;
  center: Point2D;
  size: string;
  dcr: DcrBand;
}

export interface DetailBeam {
  id: string;
  floor_key: string;
  start: Point2D;
  end: Point2D;
  // east_west beams run along x; north_south beams along y.
  orientation: "east_west" | "north_south";
  size: string;
  dcr: DcrBand;
}

export interface DetailSlab {
  id: string;
  floor_key: string;
  polygon: Point2D[];
}

export interface DetailFloor {
  floor_key: string;
  name: string;
  extents: Extents;
  is_roof: boolean;
  columns: DetailColumn[];
  beams: DetailBeam[];
  slabs: DetailSlab[];
}

export interface DetailLayout {
  option_id: string;
  variant: string;
  primary_structure: string;
  bay_grid_m: { x_m: number; y_m: number };
  // Default member sizes per band, used when the engineer hasn't yet
  // overridden a member-specific size. Reflects the system_id of the
  // selected option.
  default_sizes: {
    column: string;
    beam: string;
  };
  floors: DetailFloor[];
}

const _STORY_HEIGHT_M = 3.0;

// Deterministic DCR-band sampler. Walks the option's DCR distribution
// proportionally over a stable ordering of member ids; the same inputs
// always produce the same output.
function bandWalker(
  option: OriginStructuralOption,
): (memberIndex: number, totalMembers: number) => DcrBand {
  const dcr = option.dcr_distribution;
  return (index: number, total: number): DcrBand => {
    const ratio = total <= 0 ? 0 : index / total;
    let acc = dcr.under_60_pct;
    if (ratio < acc) return "under_60";
    acc += dcr.between_60_80;
    if (ratio < acc) return "between_60_80";
    acc += dcr.between_80_100;
    if (ratio < acc) return "between_80_100";
    return "over_100";
  };
}

function defaultSizesFor(option: OriginStructuralOption): {
  column: string;
  beam: string;
} {
  switch (option.option_id) {
    case "optimized_rc_flat_slab":
      return { column: "RC 400x400 (C25/30)", beam: "Flat slab band 1600x260" };
    case "balanced_steel_mrf":
      return { column: "HEB 260 (S355)", beam: "IPE 360 (S355)" };
    case "conservative_clt_hybrid":
      return { column: "Glulam GL24h 320x320", beam: "Glulam GL24h 240x440" };
    default:
      return { column: "Generic column", beam: "Generic beam" };
  }
}

function placeGrid(
  extents: Extents,
  bay: { x_m: number; y_m: number },
): { x: number[]; y: number[] } {
  const width = Math.max(0.0001, extents.max_x - extents.min_x);
  const depth = Math.max(0.0001, extents.max_y - extents.min_y);
  // Round to the nearest integer number of bays in each direction so
  // the grid lands exactly on the building corners. min cols=1.
  const cols = Math.max(1, Math.round(width / bay.x_m));
  const rows = Math.max(1, Math.round(depth / bay.y_m));
  const xs: number[] = [];
  for (let i = 0; i <= cols; i++) {
    xs.push(extents.min_x + (i / cols) * width);
  }
  const ys: number[] = [];
  for (let j = 0; j <= rows; j++) {
    ys.push(extents.min_y + (j / rows) * depth);
  }
  return { x: xs, y: ys };
}

// Build the detail layout from a chosen option + reviewed geometry.
// Pure function; no I/O, no randomness, deterministic across reloads.
export function buildDetailLayout(
  option: OriginStructuralOption,
  geometry: Geometry,
): DetailLayout {
  const defaults = defaultSizesFor(option);
  const occupiedFloors = geometry.floors.filter((f) => !f.is_roof);
  const floors = (occupiedFloors.length > 0 ? occupiedFloors : geometry.floors).map(
    (f) => buildDetailFloor(f, option, defaults),
  );
  return {
    option_id: option.option_id,
    variant: option.variant,
    primary_structure: option.primary_structure,
    bay_grid_m: option.bay_grid_m,
    default_sizes: defaults,
    floors,
  };
}

function buildDetailFloor(
  floor: Floor,
  option: OriginStructuralOption,
  defaults: { column: string; beam: string },
): DetailFloor {
  const grid = placeGrid(floor.extents, option.bay_grid_m);

  const columns: DetailColumn[] = [];
  const cellIds = grid.x.flatMap((_x, i) => grid.y.map((_y, j) => ({ i, j })));
  const totalColumns = cellIds.length;
  const colBand = bandWalker(option);
  cellIds.forEach((pair, index) => {
    const cx = grid.x[pair.i];
    const cy = grid.y[pair.j];
    if (cx === undefined || cy === undefined) return;
    columns.push({
      id: `${floor.key}_col_${pair.i}_${pair.j}`,
      floor_key: floor.key,
      center: { x: cx, y: cy },
      size: defaults.column,
      dcr: colBand(index, totalColumns),
    });
  });

  const beams: DetailBeam[] = [];
  // East-west beams: between adjacent x-positions at each y line.
  let beamIndex = 0;
  const beamBand = bandWalker(option);
  const ewTotal = (grid.x.length - 1) * grid.y.length;
  for (let j = 0; j < grid.y.length; j++) {
    for (let i = 0; i < grid.x.length - 1; i++) {
      const y = grid.y[j];
      const x0 = grid.x[i];
      const x1 = grid.x[i + 1];
      if (y === undefined || x0 === undefined || x1 === undefined) continue;
      beams.push({
        id: `${floor.key}_beam_ew_${i}_${j}`,
        floor_key: floor.key,
        start: { x: x0, y },
        end: { x: x1, y },
        orientation: "east_west",
        size: defaults.beam,
        dcr: beamBand(beamIndex, ewTotal),
      });
      beamIndex += 1;
    }
  }
  // North-south beams.
  beamIndex = 0;
  const nsTotal = grid.x.length * (grid.y.length - 1);
  for (let i = 0; i < grid.x.length; i++) {
    for (let j = 0; j < grid.y.length - 1; j++) {
      const x = grid.x[i];
      const y0 = grid.y[j];
      const y1 = grid.y[j + 1];
      if (x === undefined || y0 === undefined || y1 === undefined) continue;
      beams.push({
        id: `${floor.key}_beam_ns_${i}_${j}`,
        floor_key: floor.key,
        start: { x, y: y0 },
        end: { x, y: y1 },
        orientation: "north_south",
        size: defaults.beam,
        dcr: beamBand(beamIndex, nsTotal),
      });
      beamIndex += 1;
    }
  }

  const slabs: DetailSlab[] = floor.slabs.map((s, i) => ({
    id: `${floor.key}_slab_${i}`,
    floor_key: floor.key,
    polygon: s.polygon,
  }));

  return {
    floor_key: floor.key,
    name: floor.name,
    extents: floor.extents,
    is_roof: floor.is_roof,
    columns,
    beams,
    slabs,
  };
}

export const DCR_COLOR: Record<DcrBand, string> = {
  under_60: "#7BB39C",
  between_60_80: "#C1A857",
  between_80_100: "#C77F49",
  over_100: "#C0463E",
};

export const DCR_LABEL: Record<DcrBand, string> = {
  under_60: "<60%",
  between_60_80: "60-80%",
  between_80_100: "80-100%",
  over_100: ">100%",
};

// Total story height for the layout. Used by the editor's status bar.
export function totalHeightM(layout: DetailLayout): number {
  return layout.floors.length * _STORY_HEIGHT_M;
}
