"use client";

import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";
import { Suspense, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import {
  DCR_COLOR,
  DCR_LABEL,
  type DcrBand,
  type DetailBeam,
  type DetailColumn,
  type DetailFloor,
  type DetailLayout,
} from "@/components/origin/detail";

const Canvas = dynamic(
  () => import("@react-three/fiber").then((m) => m.Canvas),
  { ssr: false },
);
const OrbitControls = dynamic(
  () => import("@react-three/drei").then((m) => m.OrbitControls),
  { ssr: false },
);

const STORY_HEIGHT_M = 3.0;
const COLUMN_SIZE_M = 0.4;
const BEAM_DEPTH_M = 0.5;
const BEAM_WIDTH_M = 0.3;
const SLAB_THICKNESS_M = 0.25;
const SELECTED_COLOR = "#3A6BBF";

export interface Selection3D {
  kind: "column" | "beam";
  id: string;
}

export interface Detail3DViewerProps {
  layout: DetailLayout;
  selection: Selection3D | null;
  onSelect: (selection: Selection3D | null) => void;
}

export function Detail3DViewer({
  layout,
  selection,
  onSelect,
}: Detail3DViewerProps) {
  // Section slicer: hide everything above this elevation. The slider
  // moves from total height (everything visible) down to 0 (all hidden).
  const totalHeight = Math.max(
    1,
    layout.floors.length * STORY_HEIGHT_M + SLAB_THICKNESS_M,
  );
  const [sectionY, setSectionY] = useState<number>(totalHeight);

  // Centre of the building footprint for camera framing. We use the
  // first floor's extents as a proxy; bay grid centres on the same
  // axis system across floors.
  const cameraTarget = useMemo<[number, number, number]>(() => {
    const f = layout.floors[0];
    if (!f) return [0, 0, 0];
    const cx = (f.extents.min_x + f.extents.max_x) / 2;
    const cy = (f.extents.min_y + f.extents.max_y) / 2;
    return [cx, totalHeight / 2, cy];
  }, [layout, totalHeight]);

  const cameraPosition = useMemo<[number, number, number]>(() => {
    const f = layout.floors[0];
    if (!f) return [25, 25, 25];
    const width = f.extents.max_x - f.extents.min_x;
    const depth = f.extents.max_y - f.extents.min_y;
    const reach = Math.max(width, depth) * 1.5 + 15;
    return [cameraTarget[0] + reach, totalHeight + reach * 0.5, cameraTarget[2] + reach];
  }, [cameraTarget, totalHeight, layout]);

  return (
    <div className="relative size-full">
      <Canvas
        camera={{ position: cameraPosition, fov: 45, near: 0.1, far: 2000 }}
        gl={{ localClippingEnabled: true, antialias: true }}
        shadows
      >
        <Suspense fallback={null}>
          <Scene
            layout={layout}
            sectionY={sectionY}
            selection={selection}
            onSelect={onSelect}
            cameraTarget={cameraTarget}
          />
        </Suspense>
      </Canvas>

      <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center">
        <div className="pointer-events-auto flex items-center gap-3 rounded-md border border-border bg-surface/95 px-3 py-1.5 text-[10px] shadow-md backdrop-blur">
          <label className="flex items-center gap-2 whitespace-nowrap">
            Section
            <input
              type="range"
              min={0}
              max={totalHeight}
              step={0.1}
              value={sectionY}
              onChange={(e) => setSectionY(Number(e.target.value))}
              className="w-44 accent-brand-300"
            />
            <span className="font-mono">{sectionY.toFixed(1)} m</span>
          </label>
        </div>
      </div>

      <div className="pointer-events-none absolute right-3 top-3 rounded-md border border-border bg-surface/95 px-3 py-2 text-[10px] shadow-md backdrop-blur">
        <div className="mb-1 font-semibold uppercase tracking-wider text-muted-foreground">
          DCR
        </div>
        <ul className="space-y-0.5">
          {(Object.keys(DCR_COLOR) as DcrBand[]).map((band) => (
            <li key={band} className="flex items-center gap-2">
              <span
                className="inline-block size-3 rounded-sm"
                style={{ backgroundColor: DCR_COLOR[band] }}
              />
              {DCR_LABEL[band]}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Scene({
  layout,
  sectionY,
  selection,
  onSelect,
  cameraTarget,
}: {
  layout: DetailLayout;
  sectionY: number;
  selection: Selection3D | null;
  onSelect: (selection: Selection3D | null) => void;
  cameraTarget: [number, number, number];
}) {
  // Clip plane: keep everything below y=sectionY visible (negative Y in
  // a plane normal pointing +Y means "below" in three's convention).
  const clipPlane = useMemo(
    () => new THREE.Plane(new THREE.Vector3(0, -1, 0), sectionY),
    [sectionY],
  );

  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight
        position={[40, 80, 40]}
        intensity={1.0}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />
      <directionalLight position={[-40, 60, -40]} intensity={0.35} />
      <hemisphereLight args={["#cfd9e4", "#352a1f", 0.35]} />
      <BuildingFrame
        layout={layout}
        selection={selection}
        onSelect={onSelect}
        clipPlane={clipPlane}
      />
      <Ground layout={layout} />
      <OrbitControls
        target={cameraTarget}
        enableDamping
        dampingFactor={0.08}
        minDistance={5}
        maxDistance={500}
        maxPolarAngle={Math.PI / 2.1}
      />
    </>
  );
}

function BuildingFrame({
  layout,
  selection,
  onSelect,
  clipPlane,
}: {
  layout: DetailLayout;
  selection: Selection3D | null;
  onSelect: (selection: Selection3D | null) => void;
  clipPlane: THREE.Plane;
}) {
  return (
    <group
      onPointerMissed={() => onSelect(null)}
    >
      {layout.floors.map((floor, index) => (
        <FloorMeshes
          key={floor.floor_key}
          floor={floor}
          floorIndex={index}
          totalFloors={layout.floors.length}
          selection={selection}
          onSelect={onSelect}
          clipPlane={clipPlane}
        />
      ))}
    </group>
  );
}

function FloorMeshes({
  floor,
  floorIndex,
  totalFloors,
  selection,
  onSelect,
  clipPlane,
}: {
  floor: DetailFloor;
  floorIndex: number;
  totalFloors: number;
  selection: Selection3D | null;
  onSelect: (selection: Selection3D | null) => void;
  clipPlane: THREE.Plane;
}) {
  // Anchor: in 2D we used (model x, model y) directly. In 3D we map
  // model y to world z so the building stands "up" along world Y.
  const floorElevationM = (floorIndex + 1) * STORY_HEIGHT_M;
  const floorBelowM = floorIndex * STORY_HEIGHT_M;

  return (
    <group>
      {/* Slab at this floor's elevation. */}
      <Slab floor={floor} elevationM={floorElevationM} clipPlane={clipPlane} />
      {floor.columns.map((c) => (
        <ColumnMesh
          key={c.id}
          column={c}
          fromY={floorBelowM}
          toY={floorElevationM}
          selected={selection?.kind === "column" && selection.id === c.id}
          onSelect={() => onSelect({ kind: "column", id: c.id })}
          clipPlane={clipPlane}
        />
      ))}
      {floor.beams.map((b) => (
        <BeamMesh
          key={b.id}
          beam={b}
          elevationY={floorElevationM - BEAM_DEPTH_M / 2 - SLAB_THICKNESS_M / 2}
          selected={selection?.kind === "beam" && selection.id === b.id}
          onSelect={() => onSelect({ kind: "beam", id: b.id })}
          clipPlane={clipPlane}
        />
      ))}
      {/* Roof slab on top of the top floor. */}
      {floorIndex === totalFloors - 1 && (
        <Slab
          floor={floor}
          elevationM={floorElevationM + STORY_HEIGHT_M}
          clipPlane={clipPlane}
        />
      )}
    </group>
  );
}

function ColumnMesh({
  column,
  fromY,
  toY,
  selected,
  onSelect,
  clipPlane,
}: {
  column: DetailColumn;
  fromY: number;
  toY: number;
  selected: boolean;
  onSelect: () => void;
  clipPlane: THREE.Plane;
}) {
  const height = toY - fromY;
  const cy = (fromY + toY) / 2;
  const color = selected ? SELECTED_COLOR : DCR_COLOR[column.dcr];
  const ref = useRef<THREE.Mesh>(null);
  return (
    <mesh
      ref={ref}
      castShadow
      receiveShadow
      position={[column.center.x, cy, column.center.y]}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
    >
      <boxGeometry args={[COLUMN_SIZE_M, height, COLUMN_SIZE_M]} />
      <meshStandardMaterial color={color} clippingPlanes={[clipPlane]} />
    </mesh>
  );
}

function BeamMesh({
  beam,
  elevationY,
  selected,
  onSelect,
  clipPlane,
}: {
  beam: DetailBeam;
  elevationY: number;
  selected: boolean;
  onSelect: () => void;
  clipPlane: THREE.Plane;
}) {
  const start = beam.start;
  const end = beam.end;
  const length = Math.hypot(end.x - start.x, end.y - start.y) || 0.01;
  const cx = (start.x + end.x) / 2;
  const cy = elevationY;
  const cz = (start.y + end.y) / 2;
  // Rotate beam around Y so it lies along the chord between start/end.
  const angleY = Math.atan2(end.y - start.y, end.x - start.x);
  const color = selected ? SELECTED_COLOR : DCR_COLOR[beam.dcr];
  return (
    <mesh
      castShadow
      receiveShadow
      position={[cx, cy, cz]}
      rotation={[0, -angleY, 0]}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
    >
      <boxGeometry args={[length, BEAM_DEPTH_M, BEAM_WIDTH_M]} />
      <meshStandardMaterial color={color} clippingPlanes={[clipPlane]} />
    </mesh>
  );
}

function Slab({
  floor,
  elevationM,
  clipPlane,
}: {
  floor: DetailFloor;
  elevationM: number;
  clipPlane: THREE.Plane;
}) {
  const ex = floor.extents;
  const width = Math.max(0.001, ex.max_x - ex.min_x);
  const depth = Math.max(0.001, ex.max_y - ex.min_y);
  const cx = (ex.min_x + ex.max_x) / 2;
  const cz = (ex.min_y + ex.max_y) / 2;
  return (
    <mesh
      receiveShadow
      position={[cx, elevationM, cz]}
    >
      <boxGeometry args={[width, SLAB_THICKNESS_M, depth]} />
      <meshStandardMaterial
        color="#E8E6DE"
        roughness={0.75}
        clippingPlanes={[clipPlane]}
      />
    </mesh>
  );
}

function Ground({ layout }: { layout: DetailLayout }) {
  const ex = layout.floors[0]?.extents;
  if (!ex) return null;
  const width = Math.max(50, (ex.max_x - ex.min_x) * 4);
  const depth = Math.max(50, (ex.max_y - ex.min_y) * 4);
  const cx = (ex.min_x + ex.max_x) / 2;
  const cz = (ex.min_y + ex.max_y) / 2;
  return (
    <>
      <mesh
        receiveShadow
        position={[cx, -0.05, cz]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <planeGeometry args={[width, depth]} />
        <meshStandardMaterial color="#F0EDE5" roughness={1} />
      </mesh>
      <gridHelper args={[Math.max(width, depth), 40, "#CECEC2", "#E8E6DE"]} position={[cx, 0, cz]} />
    </>
  );
}

// Loading fallback exported so callers can wrap the viewer if they
// stream it in via Suspense at a higher level. Today the dynamic
// import handles the load state, but exporting keeps it referenced.
export const Detail3DViewerFallback = () => (
  <div className="grid h-full place-items-center">
    <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden="true" />
  </div>
);
