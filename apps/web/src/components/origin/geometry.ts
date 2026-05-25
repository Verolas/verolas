"use client";

// Client-side mirror of the server-side normalized geometry shape.
// Kept in sync with verolas_api/workflow/origin/geometry.py. The shape
// is the canonical contract between the floor_parse adapter and the
// architectural-review editor.
//
// Distances are metres. Y-positive points up (engineering convention);
// the canvas applies a Y-flip transform when rendering so the user
// sees plans the right way around.

export interface Point2D {
  x: number;
  y: number;
}

export interface Extents {
  min_x: number;
  min_y: number;
  max_x: number;
  max_y: number;
}

export type WallKind = "exterior" | "interior" | "shear" | "unknown";
export type OpeningKind = "door" | "window" | "opening";

export interface Wall {
  id: string;
  start: Point2D;
  end: Point2D;
  thickness_m: number;
  kind: WallKind;
}

export interface Opening {
  id: string;
  wall_id: string;
  center: Point2D;
  width_m: number;
  kind: OpeningKind;
}

export interface Slab {
  id: string;
  polygon: Point2D[];
}

export interface Column {
  id: string;
  center: Point2D;
  size_m: [number, number];
}

export interface Floor {
  key: string;
  name: string;
  elevation_m: number;
  extents: Extents;
  walls: Wall[];
  openings: Opening[];
  slabs: Slab[];
  columns: Column[];
  is_roof: boolean;
}

export interface Geometry {
  source_format: "dxf" | "ifc";
  floors: Floor[];
  parser_notes: string[];
}

// Recompute a floor's bounding extents from its current entities.
// Edits change the geometry, so the original extents go stale; the
// canvas viewport reads the recomputed extents.
export function recomputeExtents(floor: Floor): Extents {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  const track = (x: number, y: number): void => {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  };
  floor.walls.forEach((w) => {
    track(w.start.x, w.start.y);
    track(w.end.x, w.end.y);
  });
  floor.columns.forEach((c) => track(c.center.x, c.center.y));
  floor.openings.forEach((o) => track(o.center.x, o.center.y));
  floor.slabs.forEach((s) => s.polygon.forEach((p) => track(p.x, p.y)));
  if (minX === Infinity) {
    return { min_x: 0, min_y: 0, max_x: 0, max_y: 0 };
  }
  return { min_x: minX, min_y: minY, max_x: maxX, max_y: maxY };
}

export function newId(prefix: string, existing: { id: string }[]): string {
  const used = new Set(existing.map((e) => e.id));
  for (let i = 0; i < 100000; i++) {
    const candidate = `${prefix}_${i}`;
    if (!used.has(candidate)) return candidate;
  }
  throw new Error(`could not generate a unique id for prefix ${prefix}`);
}

// Find the closest wall to a point, with a maximum snap distance in
// metres. Used by the opening-add tool so doors and windows attach to
// the wall the user clicked near, not floating in space.
export function closestWall(
  floor: Floor,
  point: Point2D,
  maxDistance: number,
): { wall: Wall; projection: Point2D; distance: number } | null {
  let best: { wall: Wall; projection: Point2D; distance: number } | null = null;
  for (const wall of floor.walls) {
    const projection = projectPointToSegment(point, wall.start, wall.end);
    const dx = projection.x - point.x;
    const dy = projection.y - point.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    if (distance > maxDistance) continue;
    if (best === null || distance < best.distance) {
      best = { wall, projection, distance };
    }
  }
  return best;
}

function projectPointToSegment(point: Point2D, a: Point2D, b: Point2D): Point2D {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) return { x: a.x, y: a.y };
  let t = ((point.x - a.x) * dx + (point.y - a.y) * dy) / lengthSquared;
  if (t < 0) t = 0;
  else if (t > 1) t = 1;
  return { x: a.x + t * dx, y: a.y + t * dy };
}
