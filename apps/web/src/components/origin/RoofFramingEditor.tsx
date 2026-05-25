"use client";

import dynamic from "next/dynamic";
import {
  ArrowLeft,
  Check,
  Loader2,
  Trash2,
  Undo2,
  X,
} from "lucide-react";
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
import type { Extents, Floor, Geometry, Point2D } from "@/components/origin/geometry";
import {
  computeCoverage,
  defaultTrussZone,
  emptyFraming,
  newFramingId,
  withRecomputedCoverage,
  type CoverageReport,
  type FramingLine,
  type RoofFraming,
  type TrussZone,
} from "@/components/origin/roof_framing";

const Stage = dynamic(() => import("react-konva").then((m) => m.Stage), { ssr: false });
const Layer = dynamic(() => import("react-konva").then((m) => m.Layer), { ssr: false });
const KonvaRect = dynamic(() => import("react-konva").then((m) => m.Rect), { ssr: false });
const KonvaLine = dynamic(() => import("react-konva").then((m) => m.Line), { ssr: false });
const KonvaCircle = dynamic(() => import("react-konva").then((m) => m.Circle), {
  ssr: false,
});

type Tool = "select" | "truss_zone" | "girder_truss" | "beam";

type Selection =
  | { kind: "zone"; id: string }
  | { kind: "line"; id: string }
  | null;

const PALETTE: { tool: Tool; label: string; hint: string }[] = [
  { tool: "select", label: "Select", hint: "Click + delete to remove" },
  { tool: "truss_zone", label: "Regular Truss", hint: "Click + drag a coverage zone" },
  { tool: "girder_truss", label: "Girder Truss", hint: "Click + drag a girder line" },
  { tool: "beam", label: "Beam", hint: "Click + drag a beam line" },
];

const HISTORY_CAP = 50;

export interface RoofFramingEditorProps {
  activeRun: WorkflowRun | null;
  orgSlug: string;
  projectId: string;
  runId: string;
  busy: boolean;
  onCancel: () => void;
  onSave: (framing: RoofFraming) => Promise<void>;
}

export function RoofFramingEditor({
  activeRun,
  orgSlug,
  projectId,
  runId,
  busy,
  onCancel,
  onSave,
}: RoofFramingEditorProps) {
  const [framing, setFraming] = useState<RoofFraming | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("select");
  const [selection, setSelection] = useState<Selection>(null);
  const [pendingStart, setPendingStart] = useState<Point2D | null>(null);
  const [pendingEnd, setPendingEnd] = useState<Point2D | null>(null);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number }>(
    { width: 800, height: 600 },
  );
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const historyRef = useRef<RoofFraming[]>([]);
  const pushHistory = useCallback((snapshot: RoofFraming): void => {
    historyRef.current.push(snapshot);
    if (historyRef.current.length > HISTORY_CAP) {
      historyRef.current.shift();
    }
  }, []);
  const undo = useCallback((): void => {
    const prev = historyRef.current.pop();
    if (!prev) return;
    setFraming(prev);
    setSelection(null);
    setPendingStart(null);
    setPendingEnd(null);
  }, []);

  // Resize observer keeps the Konva stage in lockstep with its container.
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

  // Load: prefer an existing roof_framing.outputs payload (resume),
  // else fall back to the architectural_review reviewed_geometry to
  // derive the roof floor's footprint, else fall back to floor_parse
  // geometry. Roof floor = floor with is_roof===true; topmost if
  // multiple, first floor if none flagged.
  useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      if (!activeRun) {
        setLoadError("No active run; start a run from the workflow first.");
        return;
      }
      const node = activeRun.nodes.find((n) => n.node_key === "roof_framing");
      const saved = node?.outputs?.roof_framing as RoofFraming | undefined;
      if (saved && saved.roof_outline) {
        // Re-run coverage in case the rasteriser changed since save.
        setFraming(withRecomputedCoverage(saved));
        return;
      }
      const reviewNode = activeRun.nodes.find(
        (n) => n.node_key === "architectural_review",
      );
      const reviewedGeometry = reviewNode?.outputs?.reviewed_geometry as
        | Geometry
        | undefined;
      const parseNode = activeRun.nodes.find((n) => n.node_key === "floor_parse");
      try {
        let geometry: Geometry | null = reviewedGeometry ?? null;
        if (!geometry) {
          const geometryKey = parseNode?.outputs?.geometry_key as string | undefined;
          if (!geometryKey) {
            setLoadError(
              "Need a reviewed or parsed geometry to plan roof framing; finish floor parse first.",
            );
            return;
          }
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
          geometry = (await response.json()) as Geometry;
        }
        const roof = pickRoofFloor(geometry.floors);
        if (!roof) {
          setLoadError(
            "No roof floor identified. Mark one floor as is_roof in the parsed CAD or rename it to include 'roof'.",
          );
          return;
        }
        if (!cancelled) {
          setFraming(emptyFraming(roof.key, roof.extents));
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

  // Transform: fit the roof outline (with padding) into the container.
  const transform = useMemo(() => {
    if (!framing) return null;
    const r = framing.roof_outline;
    const widthM = Math.max(r.max_x - r.min_x, 1);
    const heightM = Math.max(r.max_y - r.min_y, 1);
    const padM = 2.0;
    const totalW = widthM + 2 * padM;
    const totalH = heightM + 2 * padM;
    const scale = Math.min(containerSize.width / totalW, containerSize.height / totalH);
    const drawnW = totalW * scale;
    const drawnH = totalH * scale;
    const offsetX = (containerSize.width - drawnW) / 2 - (r.min_x - padM) * scale;
    const offsetY = (containerSize.height - drawnH) / 2 + (r.max_y + padM) * scale;
    return { scale, offsetX, offsetY };
  }, [framing, containerSize]);

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

  const update = useCallback(
    (
      mutate: (current: RoofFraming) => RoofFraming,
      options?: { skipHistory?: boolean },
    ): void => {
      setFraming((prev) => {
        if (!prev) return prev;
        if (!options?.skipHistory) pushHistory(prev);
        return withRecomputedCoverage(mutate(prev));
      });
      setDirty(true);
    },
    [pushHistory],
  );

  const onMouseDown = useCallback(
    (event: KonvaEventObject<MouseEvent>): void => {
      if (tool === "select" || !framing) return;
      const stage = event.target.getStage();
      const ptr = stage?.getPointerPosition();
      if (!ptr) return;
      const m = toModel(ptr.x, ptr.y);
      setPendingStart(m);
      setPendingEnd(m);
    },
    [tool, framing, toModel],
  );

  const onMouseMove = useCallback(
    (event: KonvaEventObject<MouseEvent>): void => {
      if (!pendingStart) return;
      const stage = event.target.getStage();
      const ptr = stage?.getPointerPosition();
      if (!ptr) return;
      setPendingEnd(toModel(ptr.x, ptr.y));
    },
    [pendingStart, toModel],
  );

  const onMouseUp = useCallback((): void => {
    if (!pendingStart || !pendingEnd || !framing) {
      setPendingStart(null);
      setPendingEnd(null);
      return;
    }
    if (tool === "truss_zone") {
      const bounds = {
        min_x: Math.min(pendingStart.x, pendingEnd.x),
        min_y: Math.min(pendingStart.y, pendingEnd.y),
        max_x: Math.max(pendingStart.x, pendingEnd.x),
        max_y: Math.max(pendingStart.y, pendingEnd.y),
      };
      // Drop trivial zones (<0.5 m on any side).
      if (bounds.max_x - bounds.min_x >= 0.5 && bounds.max_y - bounds.min_y >= 0.5) {
        update((prev) => ({
          ...prev,
          truss_zones: [
            ...prev.truss_zones,
            defaultTrussZone(prev.truss_zones, bounds),
          ],
        }));
      }
    } else if (tool === "girder_truss" || tool === "beam") {
      const dx = pendingEnd.x - pendingStart.x;
      const dy = pendingEnd.y - pendingStart.y;
      if (Math.sqrt(dx * dx + dy * dy) >= 0.5) {
        const start = pendingStart;
        const end = pendingEnd;
        update((prev) => ({
          ...prev,
          framing_lines: [
            ...prev.framing_lines,
            {
              id: newFramingId("line", prev.framing_lines),
              kind: tool,
              start,
              end,
              size: tool === "girder_truss" ? "GLT 320x180" : "RHS 200x100x6",
            } satisfies FramingLine,
          ],
        }));
      }
    }
    setPendingStart(null);
    setPendingEnd(null);
  }, [pendingStart, pendingEnd, framing, tool, update]);

  const deleteSelection = useCallback((): void => {
    if (!selection) return;
    update((prev) => {
      if (selection.kind === "zone") {
        return {
          ...prev,
          truss_zones: prev.truss_zones.filter((z) => z.id !== selection.id),
        };
      }
      return {
        ...prev,
        framing_lines: prev.framing_lines.filter((l) => l.id !== selection.id),
      };
    });
    setSelection(null);
  }, [selection, update]);

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
      if (e.key === "Delete" || e.key === "Backspace") deleteSelection();
      else if (e.key === "Escape") {
        setSelection(null);
        setPendingStart(null);
        setPendingEnd(null);
        setTool("select");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [deleteSelection, undo]);

  const handleSave = useCallback(async () => {
    if (!framing) return;
    setSaving(true);
    try {
      await onSave(framing);
    } finally {
      setSaving(false);
    }
  }, [framing, onSave]);

  const coverage = framing?.coverage;

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

  if (!framing) {
    return (
      <div className="grid h-full place-items-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden="true" />
      </div>
    );
  }

  const toolHint = PALETTE.find((p) => p.tool === tool)?.hint ?? "";
  const coverageBand = coverageBandFor(coverage?.coverage_pct ?? 0);

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
          <span className="text-xs font-medium text-foreground">Plan roof framing</span>
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
                setPendingStart(null);
                setPendingEnd(null);
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
            title="Undo (Ctrl/Cmd+Z)"
            className="ml-2 inline-flex items-center gap-1 rounded border border-border bg-background px-2.5 py-1 text-[11px] font-medium hover:bg-surface-hover disabled:opacity-40"
          >
            <Undo2 className="size-3" aria-hidden="true" />
            Undo
          </button>
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

      <div
        className={`flex items-center gap-2 border-b border-border px-4 py-1.5 text-[11px] ${coverageBand.tone}`}
      >
        <span className="font-medium">{coverageBand.label}</span>
        <span>
          Regular truss coverage {Math.round(coverage?.coverage_pct ?? 0)}% (
          {(coverage?.covered_m2 ?? 0).toFixed(1)} / {(coverage?.total_m2 ?? 0).toFixed(1)} m²)
        </span>
        <span className="ml-auto text-muted-foreground">{toolHint}</span>
      </div>

      <div className="relative flex-1 overflow-hidden" ref={containerRef}>
        {transform ? (
          <RoofCanvas
            framing={framing}
            width={containerSize.width}
            height={containerSize.height}
            scale={transform.scale}
            offsetX={transform.offsetX}
            offsetY={transform.offsetY}
            tool={tool}
            selection={selection}
            pendingStart={pendingStart}
            pendingEnd={pendingEnd}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onSelectZone={(id) => setSelection({ kind: "zone", id })}
            onSelectLine={(id) => setSelection({ kind: "line", id })}
          />
        ) : (
          <div className="grid h-full place-items-center text-xs text-muted-foreground">
            Loading roof footprint...
          </div>
        )}
      </div>
    </div>
  );
}

function RoofCanvas({
  framing,
  width,
  height,
  scale,
  offsetX,
  offsetY,
  tool,
  selection,
  pendingStart,
  pendingEnd,
  onMouseDown,
  onMouseMove,
  onMouseUp,
  onSelectZone,
  onSelectLine,
}: {
  framing: RoofFraming;
  width: number;
  height: number;
  scale: number;
  offsetX: number;
  offsetY: number;
  tool: Tool;
  selection: Selection;
  pendingStart: Point2D | null;
  pendingEnd: Point2D | null;
  onMouseDown: (event: KonvaEventObject<MouseEvent>) => void;
  onMouseMove: (event: KonvaEventObject<MouseEvent>) => void;
  onMouseUp: () => void;
  onSelectZone: (id: string) => void;
  onSelectLine: (id: string) => void;
}) {
  const toPxX = (m: number): number => offsetX + m * scale;
  const toPxY = (m: number): number => offsetY - m * scale;
  const cursor: CSSProperties["cursor"] =
    tool === "select" ? "default" : "crosshair";

  const roof = framing.roof_outline;

  return (
    <div style={{ width, height, cursor }}>
      <Stage
        width={width}
        height={height}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
      >
        <Layer listening={false}>
          <KonvaRect x={0} y={0} width={width} height={height} fill="#FAFAF7" />
        </Layer>
        <Layer listening={false}>
          {/* Roof outline as a dashed border so the engineer sees what must be covered. */}
          <KonvaRect
            x={toPxX(roof.min_x)}
            y={toPxY(roof.max_y)}
            width={(roof.max_x - roof.min_x) * scale}
            height={(roof.max_y - roof.min_y) * scale}
            fill="#E8E6DE"
            stroke="#5C5C58"
            strokeWidth={2}
            dash={[6, 4]}
          />
        </Layer>
        {/* Uncovered cells render red so missing coverage is impossible to miss. */}
        <Layer listening={false}>
          {framing.coverage.uncovered_cells.map((c, i) => (
            <KonvaRect
              key={`uncov_${i}`}
              x={toPxX(c.min_x)}
              y={toPxY(c.max_y)}
              width={(c.max_x - c.min_x) * scale}
              height={(c.max_y - c.min_y) * scale}
              fill="#C0463E"
              opacity={0.15}
            />
          ))}
        </Layer>
        <Layer>
          {framing.truss_zones.map((z) => {
            const isSelected = selection?.kind === "zone" && selection.id === z.id;
            const w = (z.max_x - z.min_x) * scale;
            const h = (z.max_y - z.min_y) * scale;
            return (
              <KonvaRect
                key={z.id}
                x={toPxX(z.min_x)}
                y={toPxY(z.max_y)}
                width={w}
                height={h}
                fill={isSelected ? "#3A6BBF" : "#3A6BBF"}
                opacity={0.18}
                stroke="#3A6BBF"
                strokeWidth={isSelected ? 3 : 1.5}
                onClick={(e) => {
                  e.cancelBubble = true;
                  if (tool === "select") onSelectZone(z.id);
                }}
              />
            );
          })}
        </Layer>
        <Layer>
          {/* Preview lines hint the truss direction inside each zone. */}
          {framing.truss_zones.map((z) =>
            previewTrussLines(z).map((line, i) => (
              <KonvaLine
                key={`${z.id}_t${i}`}
                points={[toPxX(line[0].x), toPxY(line[0].y), toPxX(line[1].x), toPxY(line[1].y)]}
                stroke="#3A6BBF"
                strokeWidth={1}
                opacity={0.45}
                listening={false}
              />
            )),
          )}
        </Layer>
        <Layer>
          {framing.framing_lines.map((l) => {
            const isSelected = selection?.kind === "line" && selection.id === l.id;
            const colour = l.kind === "girder_truss" ? "#C0463E" : "#7B3FBF";
            return (
              <KonvaLine
                key={l.id}
                points={[toPxX(l.start.x), toPxY(l.start.y), toPxX(l.end.x), toPxY(l.end.y)]}
                stroke={isSelected ? "#3A6BBF" : colour}
                strokeWidth={4}
                lineCap="round"
                onClick={(e) => {
                  e.cancelBubble = true;
                  if (tool === "select") onSelectLine(l.id);
                }}
              />
            );
          })}
        </Layer>
        {/* Pending preview while dragging a new entity. */}
        <Layer listening={false}>
          {pendingStart && pendingEnd && tool === "truss_zone" && (
            <KonvaRect
              x={toPxX(Math.min(pendingStart.x, pendingEnd.x))}
              y={toPxY(Math.max(pendingStart.y, pendingEnd.y))}
              width={Math.abs(pendingEnd.x - pendingStart.x) * scale}
              height={Math.abs(pendingEnd.y - pendingStart.y) * scale}
              fill="#3A6BBF"
              opacity={0.18}
              stroke="#3A6BBF"
              strokeWidth={2}
              dash={[4, 3]}
            />
          )}
          {pendingStart &&
            pendingEnd &&
            (tool === "girder_truss" || tool === "beam") && (
              <KonvaLine
                points={[
                  toPxX(pendingStart.x),
                  toPxY(pendingStart.y),
                  toPxX(pendingEnd.x),
                  toPxY(pendingEnd.y),
                ]}
                stroke="#3A6BBF"
                strokeWidth={3}
                dash={[6, 4]}
              />
            )}
        </Layer>
        {/* Selection-indicator circles on framing line endpoints. */}
        <Layer listening={false}>
          {selection?.kind === "line" &&
            (() => {
              const line = framing.framing_lines.find((l) => l.id === selection.id);
              if (!line) return null;
              return (
                <>
                  <KonvaCircle
                    x={toPxX(line.start.x)}
                    y={toPxY(line.start.y)}
                    radius={5}
                    fill="#FFFFFF"
                    stroke="#3A6BBF"
                    strokeWidth={2}
                  />
                  <KonvaCircle
                    x={toPxX(line.end.x)}
                    y={toPxY(line.end.y)}
                    radius={5}
                    fill="#FFFFFF"
                    stroke="#3A6BBF"
                    strokeWidth={2}
                  />
                </>
              );
            })()}
        </Layer>
      </Stage>
    </div>
  );
}

// Render at most 6 hint lines inside a zone showing truss direction.
// Fewer than the real count (which is zone-width / spacing_m) so the
// canvas stays readable.
function previewTrussLines(zone: TrussZone): [Point2D, Point2D][] {
  const lines: [Point2D, Point2D][] = [];
  const MAX_PREVIEW = 6;
  if (zone.direction === "east_west") {
    const span = zone.max_y - zone.min_y;
    const count = Math.min(MAX_PREVIEW, Math.max(1, Math.ceil(span / zone.spacing_m)));
    for (let i = 1; i <= count; i++) {
      const y = zone.min_y + (i / (count + 1)) * span;
      lines.push([
        { x: zone.min_x, y },
        { x: zone.max_x, y },
      ]);
    }
  } else {
    const span = zone.max_x - zone.min_x;
    const count = Math.min(MAX_PREVIEW, Math.max(1, Math.ceil(span / zone.spacing_m)));
    for (let i = 1; i <= count; i++) {
      const x = zone.min_x + (i / (count + 1)) * span;
      lines.push([
        { x, y: zone.min_y },
        { x, y: zone.max_y },
      ]);
    }
  }
  return lines;
}

function pickRoofFloor(floors: Floor[]): Floor | null {
  if (floors.length === 0) return null;
  const flagged = floors.find((f) => f.is_roof);
  if (flagged) return flagged;
  // Fallback: assume the last storey is the roof. Better than nothing
  // when the parser didn't tag any floor.
  return floors[floors.length - 1] ?? null;
}

function coverageBandFor(pct: number): { tone: string; label: string } {
  if (pct >= 100) {
    return {
      tone: "bg-emerald-50/60 text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300",
      label: "Coverage OK",
    };
  }
  if (pct >= 90) {
    return {
      tone: "bg-amber-50/60 text-amber-900 dark:bg-amber-950/30 dark:text-amber-200",
      label: "Coverage close, finish covering uncovered cells",
    };
  }
  return {
    tone: "bg-destructive/10 text-destructive",
    label: "Regular truss must fully cover the roof area",
  };
}

// Pure helpers re-exported for tests.
export const _internal = { previewTrussLines, pickRoofFloor, coverageBandFor };
// Suppress "unused" lint on the helpers used only by ssr-imported components.
const _coverage = computeCoverage;
const _extents: Extents | null = null;
const _report: CoverageReport | null = null;
void _coverage;
void _extents;
void _report;
