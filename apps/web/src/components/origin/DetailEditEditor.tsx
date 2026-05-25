"use client";

import dynamic from "next/dynamic";
import { ArrowLeft, Check, Loader2, Undo2, X } from "lucide-react";
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
  type OriginStructuralOption,
  type WorkflowRun,
  workflowsApi,
} from "@/lib/api";
import type { Geometry } from "@/components/origin/geometry";
import {
  DCR_COLOR,
  DCR_LABEL,
  buildDetailLayout,
  type DcrBand,
  type DetailBeam,
  type DetailColumn,
  type DetailLayout,
} from "@/components/origin/detail";

const Stage = dynamic(() => import("react-konva").then((m) => m.Stage), { ssr: false });
const Layer = dynamic(() => import("react-konva").then((m) => m.Layer), { ssr: false });
const KonvaRect = dynamic(() => import("react-konva").then((m) => m.Rect), { ssr: false });
const KonvaLine = dynamic(() => import("react-konva").then((m) => m.Line), { ssr: false });
const KonvaCircle = dynamic(() => import("react-konva").then((m) => m.Circle), {
  ssr: false,
});
// KonvaText is no longer needed (we deleted the layer labels) but
// keeping the import behind a guard avoids tree-shake regressions.

type LayerKey = "slab" | "beam" | "column" | "loads";

const LAYERS: { key: LayerKey; label: string }[] = [
  { key: "loads", label: "Vertical loads" },
  { key: "slab", label: "Slabs" },
  { key: "beam", label: "Beams" },
  { key: "column", label: "Columns" },
];

const HISTORY_CAP = 50;

type Selection =
  | { kind: "column"; id: string }
  | { kind: "beam"; id: string }
  | null;

const COLUMN_SIZES = [
  "RC 400x400 (C25/30)",
  "RC 500x500 (C25/30)",
  "HEB 200 (S355)",
  "HEB 260 (S355)",
  "HEB 320 (S355)",
  "Glulam GL24h 280x280",
  "Glulam GL24h 320x320",
];

const BEAM_SIZES = [
  "IPE 240 (S355)",
  "IPE 300 (S355)",
  "IPE 360 (S355)",
  "IPE 450 (S355)",
  "Flat slab band 1600x240",
  "Flat slab band 1600x260",
  "Glulam GL24h 200x440",
  "Glulam GL24h 240x440",
];

export interface DetailEditEditorProps {
  activeRun: WorkflowRun | null;
  orgSlug: string;
  projectId: string;
  runId: string;
  busy: boolean;
  onCancel: () => void;
  onSave: (layout: DetailLayout) => Promise<void>;
}

export function DetailEditEditor({
  activeRun,
  orgSlug,
  projectId,
  runId,
  busy,
  onCancel,
  onSave,
}: DetailEditEditorProps) {
  const [layout, setLayout] = useState<DetailLayout | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [floorKey, setFloorKey] = useState<string | null>(null);
  const [visibleLayers, setVisibleLayers] = useState<Set<LayerKey>>(
    new Set(["slab", "beam", "column"]),
  );
  const [selection, setSelection] = useState<Selection>(null);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number }>(
    { width: 800, height: 600 },
  );
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const historyRef = useRef<DetailLayout[]>([]);
  const pushHistory = useCallback((snapshot: DetailLayout): void => {
    historyRef.current.push(snapshot);
    if (historyRef.current.length > HISTORY_CAP) {
      historyRef.current.shift();
    }
  }, []);
  const undo = useCallback((): void => {
    const prev = historyRef.current.pop();
    if (!prev) return;
    setLayout(prev);
    setSelection(null);
  }, []);

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

  // Load on mount: prefer an existing refined_option on detail_edit
  // (engineer is resuming) -> else build a fresh layout from the
  // selected option_id + reviewed geometry.
  useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      if (!activeRun) {
        setLoadError("No active run; start a run from the workflow first.");
        return;
      }
      const detailNode = activeRun.nodes.find((n) => n.node_key === "detail_edit");
      const saved = detailNode?.outputs?.refined_option as DetailLayout | undefined;
      if (saved && saved.floors) {
        setLayout(saved);
        setFloorKey(saved.floors[0]?.floor_key ?? null);
        return;
      }

      const aiNode = activeRun.nodes.find((n) => n.node_key === "ai_options");
      const options =
        (aiNode?.outputs?.options as OriginStructuralOption[] | undefined) ?? [];
      const selectNode = activeRun.nodes.find((n) => n.node_key === "select_option");
      const noteRaw = selectNode?.outputs?.note as string | undefined;
      const noteOptionId = pickOptionIdFromNote(noteRaw, options);
      const fallback = options[0];
      const chosen =
        options.find((o) => o.option_id === noteOptionId) ?? fallback ?? null;
      if (!chosen) {
        setLoadError(
          "No structural options found on ai_options. Run that step before opening the detail editor.",
        );
        return;
      }

      const reviewNode = activeRun.nodes.find(
        (n) => n.node_key === "architectural_review",
      );
      const reviewed = reviewNode?.outputs?.reviewed_geometry as Geometry | undefined;
      try {
        let geometry: Geometry | null = reviewed ?? null;
        if (!geometry) {
          const parseNode = activeRun.nodes.find((n) => n.node_key === "floor_parse");
          const geometryKey = parseNode?.outputs?.geometry_key as string | undefined;
          if (!geometryKey) {
            setLoadError(
              "Need reviewed or parsed geometry; finish the floor parse step first.",
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
          if (!response.ok) throw new Error(`fetch geometry failed: ${response.status}`);
          geometry = (await response.json()) as Geometry;
        }
        const fresh = buildDetailLayout(chosen, geometry);
        if (!cancelled) {
          setLayout(fresh);
          setFloorKey(fresh.floors[0]?.floor_key ?? null);
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

  const currentFloor = useMemo(() => {
    if (!layout || !floorKey) return null;
    return layout.floors.find((f) => f.floor_key === floorKey) ?? null;
  }, [layout, floorKey]);

  const transform = useMemo(() => {
    if (!currentFloor) return null;
    const ex = currentFloor.extents;
    const w = Math.max(1, ex.max_x - ex.min_x);
    const d = Math.max(1, ex.max_y - ex.min_y);
    const pad = 2.5;
    const totalW = w + 2 * pad;
    const totalH = d + 2 * pad;
    const scale = Math.min(containerSize.width / totalW, containerSize.height / totalH);
    const drawnW = totalW * scale;
    const drawnH = totalH * scale;
    const offsetX = (containerSize.width - drawnW) / 2 - (ex.min_x - pad) * scale;
    const offsetY = (containerSize.height - drawnH) / 2 + (ex.max_y + pad) * scale;
    return { scale, offsetX, offsetY };
  }, [currentFloor, containerSize]);

  const updateMember = useCallback(
    (
      kind: "column" | "beam",
      id: string,
      patch: { size?: string; dcr?: DcrBand },
    ): void => {
      setLayout((prev) => {
        if (!prev) return prev;
        pushHistory(prev);
        return {
          ...prev,
          floors: prev.floors.map((f) => {
            if (f.floor_key !== floorKey) return f;
            if (kind === "column") {
              return {
                ...f,
                columns: f.columns.map((c) => (c.id === id ? { ...c, ...patch } : c)),
              };
            }
            return {
              ...f,
              beams: f.beams.map((b) => (b.id === id ? { ...b, ...patch } : b)),
            };
          }),
        };
      });
      setDirty(true);
    },
    [floorKey, pushHistory],
  );

  const selectedMember = useMemo<DetailColumn | DetailBeam | null>(() => {
    if (!selection || !currentFloor) return null;
    if (selection.kind === "column") {
      return currentFloor.columns.find((c) => c.id === selection.id) ?? null;
    }
    return currentFloor.beams.find((b) => b.id === selection.id) ?? null;
  }, [selection, currentFloor]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) {
        return;
      }
      const ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        undo();
      } else if (e.key === "Escape") {
        setSelection(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo]);

  const handleSave = useCallback(async () => {
    if (!layout) return;
    setSaving(true);
    try {
      await onSave(layout);
    } finally {
      setSaving(false);
    }
  }, [layout, onSave]);

  const toggleLayer = useCallback((key: LayerKey): void => {
    setVisibleLayers((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

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

  if (!layout) {
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
          <span className="text-xs font-medium text-foreground">
            Detail: {layout.primary_structure}
          </span>
          <span className="text-[10px] text-muted-foreground">
            Bay {layout.bay_grid_m.x_m.toFixed(1)} x {layout.bay_grid_m.y_m.toFixed(1)} m
          </span>
          {dirty && (
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-amber-500" />
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={undo}
            disabled={historyRef.current.length === 0}
            title="Undo (Ctrl/Cmd+Z)"
            className="inline-flex items-center gap-1 rounded border border-border bg-background px-2.5 py-1 text-[11px] font-medium hover:bg-surface-hover disabled:opacity-40"
          >
            <Undo2 className="size-3" aria-hidden="true" />
            Undo
          </button>
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
        {layout.floors.map((f) => (
          <button
            key={f.floor_key}
            type="button"
            onClick={() => {
              setFloorKey(f.floor_key);
              setSelection(null);
            }}
            className={`rounded border px-2.5 py-1 transition-colors ${
              floorKey === f.floor_key
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
        <span className="ml-auto text-muted-foreground">
          Click member to edit · Ctrl/Cmd+Z to undo
        </span>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 shrink-0 space-y-3 overflow-y-auto border-r border-border bg-surface px-3 py-3">
          <section>
            <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Layer view
            </h3>
            <ul className="space-y-1 text-[11px]">
              {LAYERS.map((layer) => {
                const enabled = visibleLayers.has(layer.key);
                return (
                  <li key={layer.key}>
                    <button
                      type="button"
                      onClick={() => toggleLayer(layer.key)}
                      className={`flex w-full items-center justify-between gap-2 rounded border px-2 py-1 text-left ${
                        enabled
                          ? "border-brand-300 bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground"
                          : "border-border bg-background text-muted-foreground hover:bg-surface-hover"
                      }`}
                    >
                      <span>{layer.label}</span>
                      <span className="text-[9px] uppercase tracking-wider">
                        {enabled ? "on" : "off"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>

          <section>
            <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              DCR legend
            </h3>
            <ul className="space-y-0.5 text-[10px]">
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
          </section>

          {selectedMember && selection && (
            <MemberPanel
              selection={selection}
              member={selectedMember}
              onChangeSize={(size) =>
                updateMember(selection.kind, selection.id, { size })
              }
              onChangeDcr={(dcr) =>
                updateMember(selection.kind, selection.id, { dcr })
              }
            />
          )}
        </aside>

        <div className="relative flex-1 overflow-hidden" ref={containerRef}>
          {currentFloor && transform ? (
            <DetailCanvas
              floor={currentFloor}
              width={containerSize.width}
              height={containerSize.height}
              scale={transform.scale}
              offsetX={transform.offsetX}
              offsetY={transform.offsetY}
              visibleLayers={visibleLayers}
              selection={selection}
              onSelectColumn={(id) => setSelection({ kind: "column", id })}
              onSelectBeam={(id) => setSelection({ kind: "beam", id })}
              onClearSelection={() => setSelection(null)}
            />
          ) : (
            <div className="grid h-full place-items-center text-xs text-muted-foreground">
              Select a floor to view detail.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MemberPanel({
  selection,
  member,
  onChangeSize,
  onChangeDcr,
}: {
  selection: NonNullable<Selection>;
  member: DetailColumn | DetailBeam;
  onChangeSize: (size: string) => void;
  onChangeDcr: (dcr: DcrBand) => void;
}) {
  const options = selection.kind === "column" ? COLUMN_SIZES : BEAM_SIZES;
  return (
    <section className="space-y-2 rounded border border-border bg-background p-2 text-[11px]">
      <div className="flex items-center justify-between">
        <span className="font-medium capitalize">{selection.kind}</span>
        <span className="font-mono text-[9px] text-muted-foreground">{member.id}</span>
      </div>
      <label className="block text-[10px]">
        Size
        <select
          value={member.size}
          onChange={(e) => onChangeSize(e.target.value)}
          className="mt-0.5 w-full rounded border border-border bg-background px-1.5 py-1 text-[11px]"
        >
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
          {!options.includes(member.size) && (
            <option value={member.size}>{member.size}</option>
          )}
        </select>
      </label>
      <label className="block text-[10px]">
        DCR
        <select
          value={member.dcr}
          onChange={(e) => onChangeDcr(e.target.value as DcrBand)}
          className="mt-0.5 w-full rounded border border-border bg-background px-1.5 py-1 text-[11px]"
        >
          {(Object.keys(DCR_LABEL) as DcrBand[]).map((b) => (
            <option key={b} value={b}>
              {DCR_LABEL[b]}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}

function DetailCanvas({
  floor,
  width,
  height,
  scale,
  offsetX,
  offsetY,
  visibleLayers,
  selection,
  onSelectColumn,
  onSelectBeam,
  onClearSelection,
}: {
  floor: DetailLayout["floors"][number];
  width: number;
  height: number;
  scale: number;
  offsetX: number;
  offsetY: number;
  visibleLayers: Set<LayerKey>;
  selection: Selection;
  onSelectColumn: (id: string) => void;
  onSelectBeam: (id: string) => void;
  onClearSelection: () => void;
}) {
  const toPxX = (m: number): number => offsetX + m * scale;
  const toPxY = (m: number): number => offsetY - m * scale;
  const cursor: CSSProperties["cursor"] = "default";

  const onStageClick = (event: KonvaEventObject<MouseEvent>): void => {
    if (event.target === event.target.getStage()) onClearSelection();
  };

  return (
    <div style={{ width, height, cursor }}>
      <Stage width={width} height={height} onClick={onStageClick}>
        <Layer listening={false}>
          <KonvaRect x={0} y={0} width={width} height={height} fill="#FAFAF7" />
        </Layer>
        {visibleLayers.has("slab") && (
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
        )}
        {visibleLayers.has("loads") && (
          <Layer listening={false}>
            {/* Vertical-load arrows above each column. Approximates the
              Genia "Vertical Load From Above" layer at a low fidelity. */}
            {floor.columns.map((c) => (
              <KonvaLine
                key={`load_${c.id}`}
                points={[
                  toPxX(c.center.x),
                  toPxY(c.center.y) - 26,
                  toPxX(c.center.x),
                  toPxY(c.center.y) - 4,
                ]}
                stroke="#5C5C58"
                strokeWidth={1}
                listening={false}
              />
            ))}
          </Layer>
        )}
        {visibleLayers.has("beam") && (
          <Layer>
            {floor.beams.map((b) => {
              const isSelected = selection?.kind === "beam" && selection.id === b.id;
              return (
                <KonvaLine
                  key={b.id}
                  points={[
                    toPxX(b.start.x),
                    toPxY(b.start.y),
                    toPxX(b.end.x),
                    toPxY(b.end.y),
                  ]}
                  stroke={isSelected ? "#3A6BBF" : DCR_COLOR[b.dcr]}
                  strokeWidth={isSelected ? 5 : 3}
                  lineCap="round"
                  onClick={(e) => {
                    e.cancelBubble = true;
                    onSelectBeam(b.id);
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
        )}
        {visibleLayers.has("column") && (
          <Layer>
            {floor.columns.map((c) => {
              const isSelected = selection?.kind === "column" && selection.id === c.id;
              const r = isSelected ? 9 : 6;
              return (
                <KonvaCircle
                  key={c.id}
                  x={toPxX(c.center.x)}
                  y={toPxY(c.center.y)}
                  radius={r}
                  fill={isSelected ? "#3A6BBF" : DCR_COLOR[c.dcr]}
                  stroke="#1F1F1B"
                  strokeWidth={1}
                  onClick={(e) => {
                    e.cancelBubble = true;
                    onSelectColumn(c.id);
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
        )}
      </Stage>
    </div>
  );
}

// Pull an option_id from the gate's note field. Engineers typically
// write something like "Approve balanced_steel_mrf" so we try a few
// extraction patterns.
function pickOptionIdFromNote(
  note: string | undefined,
  options: OriginStructuralOption[],
): string | null {
  if (!note) return null;
  for (const opt of options) {
    if (note.includes(opt.option_id)) return opt.option_id;
  }
  for (const opt of options) {
    if (note.toLowerCase().includes(opt.variant)) return opt.option_id;
  }
  return null;
}
