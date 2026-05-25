"use client";

import dynamic from "next/dynamic";
import { Anchor, ArrowLeft, Check, Loader2, Square, Trash2, Undo2, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import type { KonvaEventObject } from "konva/lib/Node";

import {
  ApiError,
  type WorkflowRun,
  workflowsApi,
} from "@/lib/api";
import {
  closestWall,
  newId,
  recomputeExtents,
  type Floor,
  type Geometry,
  type Point2D,
} from "@/components/origin/geometry";

// Konva touches the DOM and uses canvas; dynamic-import with ssr:false
// keeps Next.js from trying to render it on the server.
const Stage = dynamic(() => import("react-konva").then((m) => m.Stage), { ssr: false });
const Layer = dynamic(() => import("react-konva").then((m) => m.Layer), { ssr: false });
const KonvaRect = dynamic(() => import("react-konva").then((m) => m.Rect), { ssr: false });
const KonvaLine = dynamic(() => import("react-konva").then((m) => m.Line), { ssr: false });
const KonvaCircle = dynamic(() => import("react-konva").then((m) => m.Circle), {
  ssr: false,
});

type Tool = "select" | "wall" | "column" | "door" | "window";

type Selection =
  | { kind: "wall"; id: string }
  | { kind: "column"; id: string }
  | { kind: "opening"; id: string }
  | null;

const PALETTE: { tool: Tool; label: string; hint: string }[] = [
  { tool: "select", label: "Select", hint: "Pick + drag endpoints" },
  { tool: "wall", label: "Wall", hint: "Click + drag" },
  { tool: "column", label: "Column", hint: "Click to place" },
  { tool: "door", label: "Door", hint: "Click on wall" },
  { tool: "window", label: "Window", hint: "Click on wall" },
];

const SNAP_M = 0.5;
const HANDLE_RADIUS_PX = 6;

export interface FloorReviewEditorProps {
  activeRun: WorkflowRun | null;
  orgSlug: string;
  projectId: string;
  runId: string;
  busy: boolean;
  onCancel: () => void;
  onSave: (reviewedGeometry: Geometry) => Promise<void>;
}

export function FloorReviewEditor({
  activeRun,
  orgSlug,
  projectId,
  runId,
  busy,
  onCancel,
  onSave,
}: FloorReviewEditorProps) {
  const [geometry, setGeometry] = useState<Geometry | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [floorKey, setFloorKey] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("select");
  const [selection, setSelection] = useState<Selection>(null);
  const [pendingWallStart, setPendingWallStart] = useState<Point2D | null>(null);
  const [pendingWallEnd, setPendingWallEnd] = useState<Point2D | null>(null);
  const [draggingEndpoint, setDraggingEndpoint] = useState<
    { wallId: string; which: "start" | "end" } | null
  >(null);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number }>(
    { width: 800, height: 600 },
  );
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Undo history. We push the previous Geometry snapshot onto the stack
  // before each edit so Ctrl+Z (Cmd+Z) restores it. Capped at 50 to
  // bound memory. Endpoint drags would otherwise spam the stack with
  // every mouse-move frame, so the move-endpoint path uses a single
  // commit on drag start instead of every frame.
  const historyRef = useRef<Geometry[]>([]);
  const HISTORY_CAP = 50;
  const pushHistory = useCallback((snapshot: Geometry): void => {
    historyRef.current.push(snapshot);
    if (historyRef.current.length > HISTORY_CAP) {
      historyRef.current.shift();
    }
  }, []);
  const undo = useCallback((): void => {
    const prev = historyRef.current.pop();
    if (!prev) return;
    setGeometry(prev);
    setSelection(null);
    setPendingWallStart(null);
    setPendingWallEnd(null);
    setDraggingEndpoint(null);
  }, []);

  // Resize observer keeps the canvas in lockstep with its container.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = (): void => {
      setContainerSize({ width: el.clientWidth, height: el.clientHeight });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Pull the parsed geometry from the upstream floor_parse outputs. If
  // a previous review save left a reviewed_geometry, prefer that so
  // the engineer can resume edits.
  useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      if (!activeRun) {
        setLoadError("No active run; start a run from the workflow first.");
        return;
      }
      const reviewNode = activeRun.nodes.find(
        (n) => n.node_key === "architectural_review",
      );
      const reviewed = reviewNode?.outputs?.reviewed_geometry as Geometry | undefined;
      if (reviewed && reviewed.floors) {
        setGeometry(reviewed);
        setFloorKey(reviewed.floors[0]?.key ?? null);
        return;
      }
      const floorParse = activeRun.nodes.find((n) => n.node_key === "floor_parse");
      if (!floorParse) {
        setLoadError("Floor parse node not found on this run.");
        return;
      }
      const geometryKey = floorParse.outputs?.geometry_key as string | undefined;
      if (!geometryKey) {
        setLoadError(
          "Floor parse did not produce a geometry artifact yet. Wait for it to complete.",
        );
        return;
      }
      try {
        const presigned = await workflowsApi.getArtifactUrl(
          orgSlug,
          projectId,
          runId,
          geometryKey,
        );
        const response = await fetch(presigned.url);
        if (!response.ok) {
          throw new Error(`fetch ${geometryKey} failed: ${response.status}`);
        }
        const parsed = (await response.json()) as Geometry;
        if (!cancelled) {
          setGeometry(parsed);
          setFloorKey(parsed.floors[0]?.key ?? null);
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof ApiError ? err.detail : String(err));
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [activeRun, orgSlug, projectId, runId]);

  const currentFloor = useMemo<Floor | null>(() => {
    if (!geometry || !floorKey) return null;
    return geometry.floors.find((f) => f.key === floorKey) ?? null;
  }, [geometry, floorKey]);

  // Compute a scale + offset that fits the current floor inside the
  // container with padding. Coordinates inside Konva are pixels; we
  // store geometry in metres and convert at draw time.
  const transform = useMemo(() => {
    if (!currentFloor) return null;
    const ex = recomputeExtents(currentFloor);
    const widthM = Math.max(ex.max_x - ex.min_x, 1);
    const heightM = Math.max(ex.max_y - ex.min_y, 1);
    const padM = 2.5;
    const totalW = widthM + 2 * padM;
    const totalH = heightM + 2 * padM;
    const scaleX = containerSize.width / totalW;
    const scaleY = containerSize.height / totalH;
    const scale = Math.min(scaleX, scaleY);
    const drawnW = totalW * scale;
    const drawnH = totalH * scale;
    const offsetX = (containerSize.width - drawnW) / 2 - (ex.min_x - padM) * scale;
    const offsetY = (containerSize.height - drawnH) / 2 + (ex.max_y + padM) * scale;
    return { scale, offsetX, offsetY };
  }, [currentFloor, containerSize]);

  const toModel = useCallback(
    (px: number, py: number): Point2D => {
      if (!transform) return { x: 0, y: 0 };
      return {
        x: (px - transform.offsetX) / transform.scale,
        y: -(py - transform.offsetY) / transform.scale,
      };
    },
    [transform],
  );

  const updateCurrentFloor = useCallback(
    (mutate: (floor: Floor) => Floor, options?: { skipHistory?: boolean }): void => {
      setGeometry((prev) => {
        if (!prev || !floorKey) return prev;
        if (!options?.skipHistory) {
          pushHistory(prev);
        }
        const next: Geometry = {
          ...prev,
          floors: prev.floors.map((f) => (f.key === floorKey ? mutate(f) : f)),
        };
        return next;
      });
      setDirty(true);
    },
    [floorKey, pushHistory],
  );

  // Stage click dispatches by current tool.
  const onStageClick = useCallback(
    (event: KonvaEventObject<MouseEvent>): void => {
      if (!currentFloor || !transform) return;
      const stage = event.target.getStage();
      const ptr = stage?.getPointerPosition();
      if (!ptr) return;
      const model = toModel(ptr.x, ptr.y);

      if (tool === "column") {
        updateCurrentFloor((floor) => ({
          ...floor,
          columns: [
            ...floor.columns,
            {
              id: newId("col_user", floor.columns),
              center: model,
              size_m: [0.3, 0.3],
            },
          ],
        }));
        return;
      }
      if (tool === "door" || tool === "window") {
        const hit = closestWall(currentFloor, model, SNAP_M);
        if (!hit) return;
        updateCurrentFloor((floor) => ({
          ...floor,
          openings: [
            ...floor.openings,
            {
              id: newId("op_user", floor.openings),
              wall_id: hit.wall.id,
              center: hit.projection,
              width_m: tool === "door" ? 0.9 : 1.2,
              kind: tool,
            },
          ],
        }));
        return;
      }
      // select-tool fallback: a click on empty stage clears selection.
      if (tool === "select" && event.target === event.target.getStage()) {
        setSelection(null);
      }
    },
    [tool, currentFloor, transform, toModel, updateCurrentFloor],
  );

  const onStageMouseDown = useCallback(
    (event: KonvaEventObject<MouseEvent>): void => {
      if (tool !== "wall") return;
      const stage = event.target.getStage();
      const ptr = stage?.getPointerPosition();
      if (!ptr) return;
      const model = toModel(ptr.x, ptr.y);
      setPendingWallStart(model);
      setPendingWallEnd(model);
    },
    [tool, toModel],
  );

  const onStageMouseMove = useCallback(
    (event: KonvaEventObject<MouseEvent>): void => {
      const stage = event.target.getStage();
      const ptr = stage?.getPointerPosition();
      if (!ptr) return;
      const model = toModel(ptr.x, ptr.y);
      if (pendingWallStart) setPendingWallEnd(model);
      if (draggingEndpoint && currentFloor) {
        // Each mouse-move during a drag is a separate edit by the
        // updater's eyes, but we only want one history entry per drag.
        // The drag-start handler captured a snapshot already; per-
        // frame updates here skip the stack.
        updateCurrentFloor(
          (floor) => ({
            ...floor,
            walls: floor.walls.map((w) =>
              w.id === draggingEndpoint.wallId
                ? draggingEndpoint.which === "start"
                  ? { ...w, start: model }
                  : { ...w, end: model }
                : w,
            ),
          }),
          { skipHistory: true },
        );
      }
    },
    [pendingWallStart, draggingEndpoint, currentFloor, toModel, updateCurrentFloor],
  );

  const onStageMouseUp = useCallback((): void => {
    if (pendingWallStart && pendingWallEnd) {
      const dx = pendingWallEnd.x - pendingWallStart.x;
      const dy = pendingWallEnd.y - pendingWallStart.y;
      const length = Math.sqrt(dx * dx + dy * dy);
      if (length > 0.1) {
        const start = pendingWallStart;
        const end = pendingWallEnd;
        updateCurrentFloor((floor) => ({
          ...floor,
          walls: [
            ...floor.walls,
            {
              id: newId("wall_user", floor.walls),
              start,
              end,
              thickness_m: 0.2,
              kind: "unknown",
            },
          ],
        }));
      }
      setPendingWallStart(null);
      setPendingWallEnd(null);
    }
    if (draggingEndpoint) {
      setDraggingEndpoint(null);
    }
  }, [pendingWallStart, pendingWallEnd, draggingEndpoint, updateCurrentFloor]);

  // Delete the current selection. Bound to the Delete and Backspace
  // keys when the canvas is focused (we attach to window so the user
  // does not have to click into the stage first).
  const deleteSelection = useCallback((): void => {
    if (!selection) return;
    updateCurrentFloor((floor) => {
      if (selection.kind === "wall") {
        const remainingWalls = floor.walls.filter((w) => w.id !== selection.id);
        // Openings referencing the deleted wall lose their wall_id but
        // stay placed; the engineer can re-anchor or delete.
        return {
          ...floor,
          walls: remainingWalls,
          openings: floor.openings.map((o) =>
            o.wall_id === selection.id ? { ...o, wall_id: "" } : o,
          ),
        };
      }
      if (selection.kind === "column") {
        return {
          ...floor,
          columns: floor.columns.filter((c) => c.id !== selection.id),
        };
      }
      return {
        ...floor,
        openings: floor.openings.filter((o) => o.id !== selection.id),
      };
    });
    setSelection(null);
  }, [selection, updateCurrentFloor]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      const ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        undo();
        return;
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        deleteSelection();
      } else if (e.key === "Escape") {
        setSelection(null);
        setPendingWallStart(null);
        setPendingWallEnd(null);
        setTool("select");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [deleteSelection, undo]);

  // Snap a selected orphaned opening to whatever wall is closest, no
  // distance limit. Used when the engineer deletes a wall and wants to
  // rebind the affected door/window to a new wall without re-drawing.
  const reanchorSelectedOpening = useCallback((): void => {
    if (!selection || selection.kind !== "opening" || !currentFloor) return;
    const opening = currentFloor.openings.find((o) => o.id === selection.id);
    if (!opening) return;
    let bestId = "";
    let bestProj = opening.center;
    let bestDistance = Infinity;
    for (const wall of currentFloor.walls) {
      const proj = projectOnto(opening.center, wall.start, wall.end);
      const dx = proj.x - opening.center.x;
      const dy = proj.y - opening.center.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestId = wall.id;
        bestProj = proj;
      }
    }
    if (!bestId) return;
    updateCurrentFloor((floor) => ({
      ...floor,
      openings: floor.openings.map((o) =>
        o.id === opening.id ? { ...o, wall_id: bestId, center: bestProj } : o,
      ),
    }));
  }, [selection, currentFloor, updateCurrentFloor]);

  // True only when an orphaned opening (wall_id="") is selected.
  const orphanedOpeningSelected = useMemo(() => {
    if (!selection || selection.kind !== "opening" || !currentFloor) return false;
    const opening = currentFloor.openings.find((o) => o.id === selection.id);
    return opening !== undefined && opening.wall_id === "";
  }, [selection, currentFloor]);

  const handleSave = useCallback(async () => {
    if (!geometry) return;
    setSaving(true);
    try {
      await onSave(geometry);
    } finally {
      setSaving(false);
    }
  }, [geometry, onSave]);

  const toolHint = useMemo(() => {
    const found = PALETTE.find((p) => p.tool === tool);
    return found?.hint ?? "";
  }, [tool]);

  if (loadError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <p className="text-sm text-destructive">{loadError}</p>
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-1 rounded border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-surface-hover"
        >
          <ArrowLeft className="size-3" aria-hidden="true" />
          Back to graph
        </button>
      </div>
    );
  }

  if (!geometry) {
    return (
      <div className="grid h-full place-items-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden="true" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-2">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-1 rounded border border-border bg-background px-2.5 py-1 text-xs font-medium hover:bg-surface-hover"
          >
            <ArrowLeft className="size-3" aria-hidden="true" />
            Back
          </button>
          <span className="text-xs font-medium text-foreground">Review parsed floors</span>
          {dirty && (
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-amber-500" />
          )}
        </div>
        <div className="flex items-center gap-1">
          {PALETTE.map((p) => (
            <button
              key={p.tool}
              type="button"
              onClick={() => {
                setTool(p.tool);
                setPendingWallStart(null);
                setPendingWallEnd(null);
                setSelection(null);
              }}
              title={p.hint}
              className={`rounded border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                tool === p.tool
                  ? "border-brand-300 bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground"
                  : "border-border bg-background text-foreground hover:bg-surface-hover"
              }`}
            >
              {p.label}
            </button>
          ))}
          <button
            type="button"
            onClick={undo}
            disabled={historyRef.current.length === 0}
            title="Undo last edit (Ctrl/Cmd+Z)"
            className="ml-2 inline-flex items-center gap-1 rounded border border-border bg-background px-2.5 py-1 text-[11px] font-medium hover:bg-surface-hover disabled:opacity-40"
          >
            <Undo2 className="size-3" aria-hidden="true" />
            Undo
          </button>
          {orphanedOpeningSelected && (
            <button
              type="button"
              onClick={reanchorSelectedOpening}
              title="Re-anchor this opening to the nearest wall"
              className="inline-flex items-center gap-1 rounded border border-brand-300 bg-brand-50 px-2.5 py-1 text-[11px] font-medium text-brand-700 hover:bg-brand-100 dark:bg-accent dark:text-accent-foreground"
            >
              <Anchor className="size-3" aria-hidden="true" />
              Re-anchor
            </button>
          )}
          {selection && (
            <button
              type="button"
              onClick={deleteSelection}
              className="inline-flex items-center gap-1 rounded border border-destructive/30 bg-destructive/5 px-2.5 py-1 text-[11px] font-medium text-destructive hover:bg-destructive/10"
            >
              <Trash2 className="size-3" aria-hidden="true" />
              Delete
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving || busy}
            className="inline-flex items-center gap-1 rounded border border-border bg-background px-3 py-1 text-xs hover:bg-surface-hover disabled:opacity-50"
          >
            <X className="size-3" aria-hidden="true" />
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || busy}
            className="inline-flex items-center gap-1 rounded border border-brand-300 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100 disabled:opacity-50 dark:bg-accent dark:text-accent-foreground"
          >
            {saving ? (
              <Loader2 className="size-3 animate-spin" aria-hidden="true" />
            ) : (
              <Check className="size-3" aria-hidden="true" />
            )}
            Save + mark done
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1 border-b border-border bg-surface px-4 py-1.5 text-[11px]">
        {geometry.floors.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => {
              setFloorKey(f.key);
              setSelection(null);
            }}
            className={`rounded border px-2.5 py-1 transition-colors ${
              floorKey === f.key
                ? "border-brand-300 bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground"
                : "border-border bg-background hover:bg-surface-hover"
            }`}
          >
            {f.name}
            {f.is_roof && (
              <span className="ml-1 text-[9px] uppercase tracking-wider opacity-70">
                roof
              </span>
            )}
          </button>
        ))}
        <span className="ml-auto text-muted-foreground">{toolHint}</span>
      </div>

      <div className="relative flex-1 overflow-hidden" ref={containerRef}>
        {currentFloor && transform ? (
          <CanvasStage
            floor={currentFloor}
            width={containerSize.width}
            height={containerSize.height}
            scale={transform.scale}
            offsetX={transform.offsetX}
            offsetY={transform.offsetY}
            selection={selection}
            tool={tool}
            pendingWallStart={pendingWallStart}
            pendingWallEnd={pendingWallEnd}
            onStageClick={onStageClick}
            onStageMouseDown={onStageMouseDown}
            onStageMouseMove={onStageMouseMove}
            onStageMouseUp={onStageMouseUp}
            onSelectWall={(id) => setSelection({ kind: "wall", id })}
            onSelectColumn={(id) => setSelection({ kind: "column", id })}
            onSelectOpening={(id) => setSelection({ kind: "opening", id })}
            onBeginDragEndpoint={(wallId, which) => {
              // Snapshot once at drag start so Ctrl+Z restores the
              // wall's pre-drag position, not the previous frame.
              if (geometry) pushHistory(geometry);
              setDraggingEndpoint({ wallId, which });
            }}
          />
        ) : (
          <div className="grid h-full place-items-center text-xs text-muted-foreground">
            Select a floor to begin reviewing.
          </div>
        )}
      </div>
    </div>
  );
}

function CanvasStage({
  floor,
  width,
  height,
  scale,
  offsetX,
  offsetY,
  selection,
  tool,
  pendingWallStart,
  pendingWallEnd,
  onStageClick,
  onStageMouseDown,
  onStageMouseMove,
  onStageMouseUp,
  onSelectWall,
  onSelectColumn,
  onSelectOpening,
  onBeginDragEndpoint,
}: {
  floor: Floor;
  width: number;
  height: number;
  scale: number;
  offsetX: number;
  offsetY: number;
  selection: Selection;
  tool: Tool;
  pendingWallStart: Point2D | null;
  pendingWallEnd: Point2D | null;
  onStageClick: (event: KonvaEventObject<MouseEvent>) => void;
  onStageMouseDown: (event: KonvaEventObject<MouseEvent>) => void;
  onStageMouseMove: (event: KonvaEventObject<MouseEvent>) => void;
  onStageMouseUp: () => void;
  onSelectWall: (id: string) => void;
  onSelectColumn: (id: string) => void;
  onSelectOpening: (id: string) => void;
  onBeginDragEndpoint: (wallId: string, which: "start" | "end") => void;
}) {
  const toPxX = (m: number): number => offsetX + m * scale;
  const toPxY = (m: number): number => offsetY - m * scale;

  const cursor: CSSProperties["cursor"] =
    tool === "wall" ? "crosshair" : tool === "select" ? "default" : "copy";

  return (
    <div style={{ width, height, cursor }}>
      <Stage
        width={width}
        height={height}
        onMouseDown={onStageMouseDown}
        onMouseMove={onStageMouseMove}
        onMouseUp={onStageMouseUp}
        onClick={onStageClick}
      >
        <Layer listening={false}>
          <KonvaRect
            x={0}
            y={0}
            width={width}
            height={height}
            fill="#FAFAF7"
          />
        </Layer>
        <Layer listening={false}>
          {floor.slabs.map((s) => (
            <KonvaLine
              key={s.id}
              points={s.polygon.flatMap((p) => [toPxX(p.x), toPxY(p.y)])}
              closed
              fill="#E8E6DE"
            />
          ))}
        </Layer>
        <Layer>
          {floor.walls.map((w) => {
            const isSelected = selection?.kind === "wall" && selection.id === w.id;
            return (
              <KonvaLine
                key={w.id}
                points={[toPxX(w.start.x), toPxY(w.start.y), toPxX(w.end.x), toPxY(w.end.y)]}
                stroke={isSelected ? "#3A6BBF" : "#1F1F1B"}
                strokeWidth={Math.max(2, w.thickness_m * scale)}
                lineCap="square"
                onClick={(e) => {
                  e.cancelBubble = true;
                  if (tool === "select") onSelectWall(w.id);
                }}
                onMouseEnter={(e) => {
                  const stage = e.target.getStage();
                  if (stage) stage.container().style.cursor = "pointer";
                }}
                onMouseLeave={(e) => {
                  const stage = e.target.getStage();
                  if (stage) stage.container().style.cursor = cursor ?? "default";
                }}
              />
            );
          })}
        </Layer>
        <Layer>
          {floor.columns.map((c) => {
            const isSelected =
              selection?.kind === "column" && selection.id === c.id;
            const wPx = Math.max(6, c.size_m[0] * scale);
            const hPx = Math.max(6, c.size_m[1] * scale);
            return (
              <KonvaRect
                key={c.id}
                x={toPxX(c.center.x) - wPx / 2}
                y={toPxY(c.center.y) - hPx / 2}
                width={wPx}
                height={hPx}
                fill={isSelected ? "#3A6BBF" : "#1F1F1B"}
                onClick={(e) => {
                  e.cancelBubble = true;
                  if (tool === "select") onSelectColumn(c.id);
                }}
              />
            );
          })}
        </Layer>
        <Layer>
          {floor.openings.map((o) => {
            const isSelected =
              selection?.kind === "opening" && selection.id === o.id;
            const isOrphan = o.wall_id === "";
            const r = Math.max(4, (o.width_m / 2) * scale);
            const fill = isSelected
              ? "#3A6BBF"
              : o.kind === "door"
                ? "#C0463E"
                : "#3A6BBF";
            const orphanProps = isOrphan
              ? { stroke: "#C0463E", strokeWidth: 2, dash: [3, 2] }
              : {};
            return (
              <KonvaCircle
                key={o.id}
                x={toPxX(o.center.x)}
                y={toPxY(o.center.y)}
                radius={r}
                fill={fill}
                opacity={isOrphan ? 0.35 : 0.75}
                {...orphanProps}
                onClick={(e) => {
                  e.cancelBubble = true;
                  if (tool === "select") onSelectOpening(o.id);
                }}
              />
            );
          })}
        </Layer>
        {/* Handles overlay: only draws when a wall is selected. */}
        <Layer>
          {selection?.kind === "wall" &&
            (() => {
              const wall = floor.walls.find((w) => w.id === selection.id);
              if (!wall) return null;
              return (
                <>
                  <EndpointHandle
                    x={toPxX(wall.start.x)}
                    y={toPxY(wall.start.y)}
                    onMouseDown={() => onBeginDragEndpoint(wall.id, "start")}
                  />
                  <EndpointHandle
                    x={toPxX(wall.end.x)}
                    y={toPxY(wall.end.y)}
                    onMouseDown={() => onBeginDragEndpoint(wall.id, "end")}
                  />
                </>
              );
            })()}
        </Layer>
        {/* Pending wall preview during click-drag-add. */}
        <Layer listening={false}>
          {pendingWallStart && pendingWallEnd && (
            <KonvaLine
              points={[
                toPxX(pendingWallStart.x),
                toPxY(pendingWallStart.y),
                toPxX(pendingWallEnd.x),
                toPxY(pendingWallEnd.y),
              ]}
              stroke="#3A6BBF"
              strokeWidth={3}
              dash={[6, 4]}
            />
          )}
        </Layer>
      </Stage>
    </div>
  );
}

function EndpointHandle({
  x,
  y,
  onMouseDown,
}: {
  x: number;
  y: number;
  onMouseDown: () => void;
}) {
  return (
    <KonvaCircle
      x={x}
      y={y}
      radius={HANDLE_RADIUS_PX}
      fill="#FFFFFF"
      stroke="#3A6BBF"
      strokeWidth={2}
      onMouseDown={(e) => {
        e.cancelBubble = true;
        onMouseDown();
      }}
      onMouseEnter={(e) => {
        const stage = e.target.getStage();
        if (stage) stage.container().style.cursor = "grab";
      }}
      onMouseLeave={(e) => {
        const stage = e.target.getStage();
        if (stage) stage.container().style.cursor = "default";
      }}
    />
  );
}

// Lucide alias so the toolbar import stays tidy. `Square` is used as
// the column-tool glyph in callers when we wire icons in the future;
// kept exported so the symbol is referenced.
export const ColumnGlyph = Square;

// Project a point onto the infinite line segment between a and b,
// clamped to the segment. Used by the re-anchor action so the opening
// snaps onto the closest wall instead of floating at its old centre.
function projectOnto(p: Point2D, a: Point2D, b: Point2D): Point2D {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) return { x: a.x, y: a.y };
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / lengthSquared;
  if (t < 0) t = 0;
  else if (t > 1) t = 1;
  return { x: a.x + t * dx, y: a.y + t * dy };
}
