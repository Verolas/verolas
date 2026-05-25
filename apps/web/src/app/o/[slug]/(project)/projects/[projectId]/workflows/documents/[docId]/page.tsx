"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  type Node,
  type NodeTypes,
  Position,
  ReactFlow,
  type Edge,
} from "@xyflow/react";
import {
  ArrowLeft,
  Check,
  CircleDashed,
  CircleX,
  Loader2,
  Pencil,
  Play,
  Workflow as WorkflowIcon,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type WorkflowDocument,
  type WorkflowNodeKind,
  type WorkflowNodeStatus,
  type WorkflowRun,
  type WorkflowRunNode,
  workflowDocumentsApi,
  workflowsApi,
} from "@/lib/api";

interface Props {
  params: Promise<{ slug: string; projectId: string; docId: string }>;
}

// Layout helper: simple left-to-right Sugiyama-style layering using BFS
// depth from entry_keys.
function layoutNodes(
  doc: WorkflowDocument,
  statusByNodeKey: Record<string, WorkflowNodeStatus>,
): { nodes: Node[]; edges: Edge[] } {
  const xStep = 240;
  const yStep = 120;
  const depthByKey = new Map<string, number>();
  const queue = doc.definition.entry_keys.map((k) => ({ key: k, depth: 0 }));
  while (queue.length > 0) {
    const { key, depth } = queue.shift()!;
    if (depthByKey.has(key)) continue;
    depthByKey.set(key, depth);
    doc.definition.edges
      .filter((e) => e.from_key === key)
      .forEach((e) => queue.push({ key: e.to_key, depth: depth + 1 }));
  }
  doc.definition.nodes.forEach((n) => {
    if (!depthByKey.has(n.key)) depthByKey.set(n.key, 0);
  });

  const byDepth = new Map<number, string[]>();
  depthByKey.forEach((d, k) => {
    if (!byDepth.has(d)) byDepth.set(d, []);
    byDepth.get(d)!.push(k);
  });
  const indexByKey = new Map<string, number>();
  byDepth.forEach((keys) => {
    keys.sort();
    keys.forEach((k, i) => indexByKey.set(k, i));
  });

  const nodes: Node[] = doc.definition.nodes.map((n) => {
    const depth = depthByKey.get(n.key) ?? 0;
    const row = indexByKey.get(n.key) ?? 0;
    return {
      id: n.key,
      type: "workflowNode",
      position: { x: depth * xStep, y: row * yStep },
      data: {
        kind: n.kind,
        name: n.name,
        status: statusByNodeKey[n.key] ?? null,
      },
    };
  });

  const edges: Edge[] = doc.definition.edges.map((e, i) => ({
    id: `e-${i}-${e.from_key}-${e.to_key}`,
    source: e.from_key,
    target: e.to_key,
    type: "smoothstep",
    style: {
      stroke: "var(--xy-edge-stroke, currentColor)",
      strokeDasharray: "4 3",
      strokeOpacity: 0.6,
    },
  }));

  return { nodes, edges };
}

const STATUS_TONE: Record<WorkflowNodeStatus, string> = {
  pending: "border-border bg-surface text-muted-foreground",
  ready: "border-brand-300 bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground",
  running:
    "border-brand-300 bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground",
  paused: "border-discipline-water/40 bg-surface text-discipline-water",
  completed:
    "border-emerald-300/50 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400",
  failed: "border-destructive/40 bg-destructive/5 text-destructive",
  skipped: "border-border bg-surface text-muted-foreground",
};

const KIND_LABEL: Record<WorkflowNodeKind, string> = {
  automated: "Automated",
  "gate.review": "Review",
  "gate.approve": "Approval",
  "gate.signature": "Signature",
  manual: "Manual",
  external_wait: "External",
  "branch.condition": "Branch",
  "branch.iterate": "Loop",
  submission: "Submission",
  notification: "Notify",
};

interface WorkflowNodeData {
  name: string;
  kind: WorkflowNodeKind;
  status: WorkflowNodeStatus | null;
  [key: string]: unknown;
}

function WorkflowNodeCard({ data }: { data: WorkflowNodeData }) {
  const status = data.status ?? "pending";
  return (
    <div
      className={`min-w-[180px] rounded-md border px-3 py-2 text-xs shadow-sm ${STATUS_TONE[status]}`}
    >
      <Handle type="target" position={Position.Left} className="!size-1.5 !bg-current" />
      <div className="font-medium">{data.name}</div>
      <div className="mt-0.5 text-[10px] opacity-70">{KIND_LABEL[data.kind]}</div>
      <Handle type="source" position={Position.Right} className="!size-1.5 !bg-current" />
    </div>
  );
}

const NODE_TYPES: NodeTypes = { workflowNode: WorkflowNodeCard as unknown as NodeTypes[string] };

export default function WorkflowDocumentPage({ params }: Props) {
  const [resolved, setResolved] = useState<
    { slug: string; projectId: string; docId: string } | null
  >(null);
  const [doc, setDoc] = useState<WorkflowDocument | null>(null);
  const [activeRun, setActiveRun] = useState<WorkflowRun | null>(null);
  const [recentRuns, setRecentRuns] = useState<WorkflowRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeKey, setSelectedNodeKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [noteDraft, setNoteDraft] = useState("");

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  const reload = useCallback(async () => {
    if (!resolved) return;
    try {
      const d = await workflowDocumentsApi.get(
        resolved.slug,
        resolved.projectId,
        resolved.docId,
      );
      setDoc(d);
      setNameDraft(d.name);
      const runs = await workflowsApi.listRuns(resolved.slug, resolved.projectId);
      const docRuns = runs.filter((r) => r.document_id === d.id);
      setRecentRuns(docRuns);
      // Pick the most recent non-cancelled run as the active view, else null.
      const active = docRuns.find(
        (r) => r.status !== "cancelled" && r.status !== "completed",
      );
      setActiveRun(active ?? docRuns[0] ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }, [resolved]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const statusByNodeKey = useMemo(() => {
    const map: Record<string, WorkflowNodeStatus> = {};
    if (activeRun) {
      activeRun.nodes.forEach((n) => {
        map[n.node_key] = n.status;
      });
    }
    return map;
  }, [activeRun]);

  const { nodes: flowNodes, edges: flowEdges } = useMemo(() => {
    if (!doc) return { nodes: [], edges: [] };
    return layoutNodes(doc, statusByNodeKey);
  }, [doc, statusByNodeKey]);

  const startRun = useCallback(async () => {
    if (!resolved || !doc) return;
    setBusy(true);
    setError(null);
    try {
      const run = await workflowDocumentsApi.createRunFromDocument(
        resolved.slug,
        resolved.projectId,
        doc.id,
      );
      setActiveRun(run);
      setRecentRuns((prev) => [run, ...prev]);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }, [resolved, doc]);

  const refreshActiveRun = useCallback(async () => {
    if (!resolved || !activeRun) return;
    try {
      const r = await workflowsApi.getRun(
        resolved.slug,
        resolved.projectId,
        activeRun.id,
      );
      setActiveRun(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }, [resolved, activeRun]);

  const advanceManual = useCallback(
    async (nodeKey: string) => {
      if (!resolved || !activeRun) return;
      setBusy(true);
      setError(null);
      try {
        const r = await workflowsApi.advanceManual(
          resolved.slug,
          resolved.projectId,
          activeRun.id,
          nodeKey,
        );
        setActiveRun(r);
        setSelectedNodeKey(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusy(false);
      }
    },
    [resolved, activeRun],
  );

  const submitGate = useCallback(
    async (nodeKey: string, decision: "approved" | "rejected") => {
      if (!resolved || !activeRun) return;
      setBusy(true);
      setError(null);
      try {
        const r = await workflowsApi.advanceGate(
          resolved.slug,
          resolved.projectId,
          activeRun.id,
          nodeKey,
          { decision, note: noteDraft || null },
        );
        setActiveRun(r);
        setNoteDraft("");
        setSelectedNodeKey(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusy(false);
      }
    },
    [resolved, activeRun, noteDraft],
  );

  const saveName = useCallback(async () => {
    if (!resolved || !doc) return;
    const next = nameDraft.trim();
    if (!next || next === doc.name) {
      setEditingName(false);
      return;
    }
    setBusy(true);
    try {
      const updated = await workflowDocumentsApi.update(
        resolved.slug,
        resolved.projectId,
        doc.id,
        { name: next },
      );
      setDoc(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
      setEditingName(false);
    }
  }, [resolved, doc, nameDraft]);

  const selectedNode = useMemo(() => {
    if (!selectedNodeKey || !doc) return null;
    const def = doc.definition.nodes.find((n) => n.key === selectedNodeKey);
    if (!def) return null;
    const runNode: WorkflowRunNode | undefined = activeRun?.nodes.find(
      (n) => n.node_key === selectedNodeKey,
    );
    return { def, runNode };
  }, [selectedNodeKey, doc, activeRun]);

  if (doc === null) {
    return (
      <div className="grid min-h-[60vh] place-items-center text-sm text-muted-foreground">
        {error ?? "Loading workflow..."}
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] w-full flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-2">
        <div className="flex min-w-0 flex-1 items-center gap-2 text-xs text-muted-foreground">
          <Link
            href={
              resolved
                ? `/o/${resolved.slug}/projects/${resolved.projectId}/workflows`
                : "#"
            }
            prefetch={false}
            className="inline-flex items-center gap-1 hover:text-foreground"
          >
            <ArrowLeft className="size-3" aria-hidden="true" />
            Workflows
          </Link>
          <span>·</span>
          <span>{doc.folder === "/" ? "Root" : doc.folder}</span>
          <span>·</span>
          {editingName ? (
            <input
              type="text"
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              onBlur={() => void saveName()}
              onKeyDown={(e) => {
                if (e.key === "Enter") void saveName();
                if (e.key === "Escape") {
                  setEditingName(false);
                  setNameDraft(doc.name);
                }
              }}
              ref={(el) => {
                if (el) el.focus();
              }}
              className="rounded border border-border bg-background px-1.5 py-0.5 text-sm text-foreground focus:border-brand-300 focus:outline-none"
            />
          ) : (
            <button
              type="button"
              onClick={() => setEditingName(true)}
              className="inline-flex items-center gap-1 text-sm font-medium text-foreground hover:underline"
            >
              {doc.name}
              <Pencil className="size-3 text-muted-foreground" aria-hidden="true" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          {activeRun && (
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Run: {activeRun.status}
            </span>
          )}
          <button
            type="button"
            onClick={() => void startRun()}
            disabled={busy || doc.definition.nodes.length === 0}
            className="inline-flex items-center gap-1 rounded border border-brand-300 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100 disabled:opacity-50 dark:bg-accent dark:text-accent-foreground"
          >
            {busy ? (
              <Loader2 className="size-3 animate-spin" aria-hidden="true" />
            ) : (
              <Play className="size-3" aria-hidden="true" />
            )}
            Start run
          </button>
        </div>
      </div>

      {error && (
        <div className="border-b border-destructive/30 bg-destructive/5 px-4 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Canvas */}
        <div className="relative flex-1 bg-background">
          {doc.definition.nodes.length === 0 ? (
            <div className="grid h-full place-items-center px-6 text-center">
              <div className="max-w-md">
                <WorkflowIcon
                  className="mx-auto mb-3 size-8 text-muted-foreground"
                  aria-hidden="true"
                />
                <p className="text-sm text-foreground">This workflow is empty.</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Editing the graph (drag nodes from the component palette) lands in a
                  follow-up stage. For now, blank workflows can only be created and
                  named; pick one from a template to see the canvas populated.
                </p>
              </div>
            </div>
          ) : (
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={NODE_TYPES}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              proOptions={{ hideAttribution: true }}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={true}
              onNodeClick={(_, node) => setSelectedNodeKey(node.id)}
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>
          )}
        </div>

        {/* Right sidebar */}
        <aside className="w-72 shrink-0 overflow-y-auto border-l border-border bg-surface">
          <Sidebar
            doc={doc}
            recentRuns={recentRuns}
            activeRunId={activeRun?.id ?? null}
            onSelectRun={(run) => setActiveRun(run)}
            onRefresh={refreshActiveRun}
          />
        </aside>
      </div>

      {/* Node detail modal */}
      {selectedNode && activeRun && (
        <NodeDetailModal
          def={selectedNode.def}
          runNode={selectedNode.runNode ?? null}
          busy={busy}
          note={noteDraft}
          onNoteChange={setNoteDraft}
          onClose={() => {
            setSelectedNodeKey(null);
            setNoteDraft("");
          }}
          onManualDone={() => void advanceManual(selectedNode.def.key)}
          onApprove={() => void submitGate(selectedNode.def.key, "approved")}
          onReject={() => void submitGate(selectedNode.def.key, "rejected")}
        />
      )}
    </div>
  );
}

function Sidebar({
  doc,
  recentRuns,
  activeRunId,
  onSelectRun,
  onRefresh,
}: {
  doc: WorkflowDocument;
  recentRuns: WorkflowRun[];
  activeRunId: string | null;
  onSelectRun: (run: WorkflowRun) => void;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-5 p-4">
      <section>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Recent runs
          </h3>
          <button
            type="button"
            onClick={onRefresh}
            className="text-[10px] text-muted-foreground hover:text-foreground"
          >
            Refresh
          </button>
        </div>
        {recentRuns.length === 0 ? (
          <p className="text-xs text-muted-foreground">No runs yet.</p>
        ) : (
          <ul className="space-y-1">
            {recentRuns.slice(0, 6).map((run) => (
              <li key={run.id}>
                <button
                  type="button"
                  onClick={() => onSelectRun(run)}
                  className={`w-full rounded border px-2 py-1.5 text-left text-xs ${
                    run.id === activeRunId
                      ? "border-brand-300 bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground"
                      : "border-border bg-background hover:bg-surface-hover"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">
                      {run.started_at
                        ? new Date(run.started_at).toLocaleTimeString()
                        : "queued"}
                    </span>
                    <span className="text-[10px] uppercase opacity-70">{run.status}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Template
        </h3>
        <p className="text-xs text-foreground">
          {doc.source_template_id ? "Forked from a Verolas template." : "Blank canvas."}
        </p>
      </section>

      <section>
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Components
        </h3>
        <p className="text-xs text-muted-foreground">
          The component palette ships in the next stage along with drag-and-drop graph
          editing. The kinds available for new nodes will be: Origin, Import, Analysis,
          Code check, Detailing, Bauphysik, Verify gate, Submission, E-signature,
          Output, CDE sync, Notify, Branch, Loop.
        </p>
      </section>
    </div>
  );
}

function NodeDetailModal({
  def,
  runNode,
  busy,
  note,
  onNoteChange,
  onClose,
  onManualDone,
  onApprove,
  onReject,
}: {
  def: { key: string; kind: WorkflowNodeKind; name: string; description?: string | null };
  runNode: WorkflowRunNode | null;
  busy: boolean;
  note: string;
  onNoteChange: (value: string) => void;
  onClose: () => void;
  onManualDone: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const status = runNode?.status ?? "pending";
  const Icon =
    status === "completed"
      ? Check
      : status === "failed" || status === "skipped"
        ? CircleX
        : status === "running"
          ? Loader2
          : CircleDashed;
  const showManualAction = def.kind === "manual" && status === "ready";
  const showGateAction =
    (def.kind === "gate.review" || def.kind === "gate.approve") && status === "ready";

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
    >
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-foreground/50"
      />
      <div className="relative flex w-full max-w-3xl flex-col rounded-lg border border-border bg-background shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-3">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <div className={`mt-0.5 grid size-8 place-items-center rounded ${STATUS_TONE[status]}`}>
              <Icon className={`size-4 ${status === "running" ? "animate-spin" : ""}`} />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-medium text-foreground">{def.name}</h2>
              <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                <span>{KIND_LABEL[def.kind]}</span>
                <span>·</span>
                <span className="uppercase">{status}</span>
                {runNode?.gate_decision && (
                  <>
                    <span>·</span>
                    <span>decision: {runNode.gate_decision}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-surface-hover"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          {def.description && (
            <p className="text-sm text-foreground-light">{def.description}</p>
          )}
          {runNode?.error && (
            <p className="rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {runNode.error}
            </p>
          )}

          <div className="rounded border border-dashed border-border bg-surface p-6 text-center text-xs text-muted-foreground">
            The node-specific workbench (e.g. the structural concept generator for
            Verolas Origin, the calc workbench for an Analysis node) opens here in a
            later stage. For now, this overlay surfaces the same actions the run-detail
            page provided.
          </div>

          {showManualAction && (
            <div>
              <button
                type="button"
                onClick={onManualDone}
                disabled={busy}
                className="inline-flex items-center gap-1 rounded border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-surface-hover disabled:opacity-50"
              >
                <Check className="size-3" aria-hidden="true" />
                Mark done
              </button>
            </div>
          )}

          {showGateAction && (
            <div className="space-y-2">
              <textarea
                value={note}
                onChange={(e) => onNoteChange(e.target.value)}
                placeholder="Optional note (visible in audit log)"
                rows={2}
                className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:border-brand-300 focus:outline-none"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onApprove}
                  disabled={busy}
                  className="inline-flex items-center gap-1 rounded border border-emerald-300/40 bg-emerald-50 px-3 py-1.5 text-xs text-emerald-800 hover:bg-emerald-100 disabled:opacity-50 dark:bg-emerald-950/40 dark:text-emerald-300"
                >
                  <Check className="size-3" aria-hidden="true" />
                  Approve
                </button>
                <button
                  type="button"
                  onClick={onReject}
                  disabled={busy}
                  className="inline-flex items-center gap-1 rounded border border-destructive/30 bg-destructive/5 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50"
                >
                  <X className="size-3" aria-hidden="true" />
                  Reject
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
