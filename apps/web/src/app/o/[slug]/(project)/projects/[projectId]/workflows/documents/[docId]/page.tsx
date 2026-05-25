"use client";

import "@xyflow/react/dist/style.css";

import {
  addEdge,
  Background,
  BackgroundVariant,
  type Connection,
  Controls,
  type Edge,
  Handle,
  type Node,
  type NodeTypes,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import {
  ArrowLeft,
  Check,
  CircleDashed,
  CircleX,
  Loader2,
  Pencil,
  Play,
  Save,
  Trash2,
  Workflow as WorkflowIcon,
  X,
} from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
} from "react";

import {
  ApiError,
  type OriginStructuralOption,
  type WorkflowDocument,
  type WorkflowEdge,
  type WorkflowGroup,
  type WorkflowNode,
  type WorkflowNodeKind,
  type WorkflowNodeStatus,
  type WorkflowRun,
  type WorkflowRunNode,
  workflowDocumentsApi,
  workflowsApi,
} from "@/lib/api";
import { DetailEditEditor } from "@/components/origin/DetailEditEditor";
import { FloorReviewEditor } from "@/components/origin/FloorReviewEditor";
import { RoofFramingEditor } from "@/components/origin/RoofFramingEditor";
import type { DetailLayout } from "@/components/origin/detail";
import type { Geometry } from "@/components/origin/geometry";
import type { RoofFraming } from "@/components/origin/roof_framing";

interface Props {
  params: Promise<{ slug: string; projectId: string; docId: string }>;
}

// Custom-data shape on each React Flow node.
interface WorkflowNodeData {
  name: string;
  kind: WorkflowNodeKind;
  description: string | null;
  params: Record<string, unknown>;
  status: WorkflowNodeStatus | null;
  groupKey: string | null;
  [key: string]: unknown;
}

// Synthetic "group supernode" cards drawn on the canvas when a group is
// collapsed. They live only in the rendered view; the source-of-truth
// flowNodes list always stays flat and contains the real members.
interface GroupCardData {
  groupKey: string;
  name: string;
  description: string | null;
  memberCount: number;
  aggregateStatus: WorkflowNodeStatus | null;
  onToggle: () => void;
  [key: string]: unknown;
}

type FlowNode = Node<WorkflowNodeData>;
type GroupFlowNode = Node<GroupCardData>;

const GROUP_NODE_PREFIX = "group:";
function groupCardId(groupKey: string): string {
  return `${GROUP_NODE_PREFIX}${groupKey}`;
}
function isGroupCardId(id: string): boolean {
  return id.startsWith(GROUP_NODE_PREFIX);
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

const PALETTE_KINDS: WorkflowNodeKind[] = [
  "manual",
  "gate.review",
  "gate.approve",
  "gate.signature",
  "automated",
  "external_wait",
  "submission",
  "notification",
];

// Drag-and-drop payload type. Lowercase per HTML5 dragstart conventions.
const PALETTE_MIME = "application/x-verolas-workflow-kind";

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

function GroupSupernodeCard({ data }: { data: GroupCardData }) {
  const status = data.aggregateStatus ?? "pending";
  return (
    <button
      type="button"
      onClick={(e) => {
        // Prevent ReactFlow node selection from swallowing the toggle.
        e.stopPropagation();
        data.onToggle();
      }}
      className={`group min-w-[240px] cursor-pointer rounded-lg border-2 border-dashed px-4 py-3 text-left text-xs shadow-md transition-colors ${STATUS_TONE[status]}`}
    >
      <Handle type="target" position={Position.Left} className="!size-1.5 !bg-current" />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider opacity-70">
          Group · click to expand
        </span>
        <span className="text-[10px] opacity-70">{data.memberCount} steps</span>
      </div>
      <div className="mt-1 text-sm font-semibold">{data.name}</div>
      {data.description && (
        <div className="mt-1 line-clamp-2 text-[10px] opacity-80">{data.description}</div>
      )}
      <Handle type="source" position={Position.Right} className="!size-1.5 !bg-current" />
    </button>
  );
}

const NODE_TYPES: NodeTypes = {
  workflowNode: WorkflowNodeCard as unknown as NodeTypes[string],
  groupCard: GroupSupernodeCard as unknown as NodeTypes[string],
};

// Aggregate child statuses into one group status. Order of precedence
// reflects what the user most needs to know first.
function aggregateGroupStatus(
  childStatuses: (WorkflowNodeStatus | null)[],
): WorkflowNodeStatus | null {
  const set = new Set(childStatuses.filter((s): s is WorkflowNodeStatus => s !== null));
  if (set.size === 0) return null;
  if (set.has("failed")) return "failed";
  if (set.has("running")) return "running";
  if (set.has("ready")) return "ready";
  if (set.has("paused")) return "paused";
  if (set.has("pending")) return "pending";
  // Only completed or skipped remain.
  if (set.has("completed") && !set.has("skipped")) return "completed";
  if (set.has("skipped") && !set.has("completed")) return "skipped";
  return "completed";
}

// Build initial React Flow nodes from a server document. Honors a
// previously-saved `_position` in node params; falls back to a BFS layout.
function buildInitialFlow(doc: WorkflowDocument): {
  nodes: FlowNode[];
  edges: Edge[];
} {
  const positionByKey = new Map<string, { x: number; y: number }>();
  doc.definition.nodes.forEach((n) => {
    const pos = (n.params as Record<string, unknown> | undefined)?._position as
      | { x: number; y: number }
      | undefined;
    if (pos && typeof pos.x === "number" && typeof pos.y === "number") {
      positionByKey.set(n.key, pos);
    }
  });

  const needsLayout = doc.definition.nodes.filter(
    (n) => !positionByKey.has(n.key),
  );
  if (needsLayout.length > 0) {
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
    needsLayout.forEach((n) => {
      if (!depthByKey.has(n.key)) depthByKey.set(n.key, 0);
    });
    const byDepth = new Map<number, string[]>();
    depthByKey.forEach((d, k) => {
      if (!byDepth.has(d)) byDepth.set(d, []);
      byDepth.get(d)!.push(k);
    });
    byDepth.forEach((keys) => keys.sort());
    needsLayout.forEach((n) => {
      const depth = depthByKey.get(n.key) ?? 0;
      const row = byDepth.get(depth)?.indexOf(n.key) ?? 0;
      positionByKey.set(n.key, { x: depth * xStep, y: row * yStep });
    });
  }

  const nodes: FlowNode[] = doc.definition.nodes.map((n) => ({
    id: n.key,
    type: "workflowNode",
    position: positionByKey.get(n.key) ?? { x: 0, y: 0 },
    data: {
      name: n.name,
      kind: n.kind,
      description: n.description ?? null,
      params: n.params ?? {},
      status: null,
      groupKey: n.group_key ?? null,
    },
  }));
  const edges: Edge[] = doc.definition.edges.map((e, i) => ({
    id: `e-${i}-${e.from_key}-${e.to_key}`,
    source: e.from_key,
    target: e.to_key,
    type: "smoothstep",
    style: {
      stroke: "currentColor",
      strokeDasharray: "4 3",
      strokeOpacity: 0.6,
    },
  }));
  return { nodes, edges };
}

// Generate a key matching the backend pattern ^[a-z][a-z0-9_]*$.
function generateKey(existing: Set<string>): string {
  for (let i = 0; i < 1000; i++) {
    const candidate = `n_${Math.random().toString(36).slice(2, 8)}`;
    if (!existing.has(candidate)) return candidate;
  }
  throw new Error("could not generate a unique node key");
}

export default function WorkflowDocumentPage({ params }: Props) {
  return (
    <ReactFlowProvider>
      <DocumentEditor params={params} />
    </ReactFlowProvider>
  );
}

function DocumentEditor({ params }: Props) {
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
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const [flowNodes, setFlowNodes, onNodesChange] = useNodesState<FlowNode>([]);
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  // When set, the canvas pane is taken over by an Origin per-node
  // editor. "review" = architectural_review editor; "roof" = roof
  // framing editor; "detail" = detail_edit editor. Null means the
  // React Flow graph is showing. Cleared on Save or Cancel.
  const [reviewMode, setReviewMode] = useState<"review" | "roof" | "detail" | null>(
    null,
  );
  const reactFlow = useReactFlow();
  const reactFlowWrapperRef = useRef<HTMLDivElement>(null);

  const toggleGroup = useCallback((groupKey: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupKey)) next.delete(groupKey);
      else next.add(groupKey);
      return next;
    });
  }, []);

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
      const { nodes, edges } = buildInitialFlow(d);
      setFlowNodes(nodes);
      setFlowEdges(edges);
      // Seed collapsed state from each group's collapsed_by_default
      // flag the first time we see the document. Subsequent reloads
      // preserve the user's expand/collapse choices.
      setCollapsedGroups((prev) => {
        if (prev.size > 0) return prev;
        const seeded = new Set<string>();
        (d.definition.groups ?? []).forEach((g) => {
          if (g.collapsed_by_default !== false) seeded.add(g.key);
        });
        return seeded;
      });
      setDirty(false);
      const runs = await workflowsApi.listRuns(resolved.slug, resolved.projectId);
      const docRuns = runs.filter((r) => r.document_id === d.id);
      setRecentRuns(docRuns);
      const active = docRuns.find(
        (r) => r.status !== "cancelled" && r.status !== "completed",
      );
      setActiveRun(active ?? docRuns[0] ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }, [resolved, setFlowNodes, setFlowEdges]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Propagate active-run statuses into the canvas data. Pure update; no
  // structural changes, no dirty flag.
  useEffect(() => {
    if (flowNodes.length === 0) return;
    const statusByKey = new Map<string, WorkflowNodeStatus>();
    activeRun?.nodes.forEach((n) => statusByKey.set(n.node_key, n.status));
    setFlowNodes((prev) =>
      prev.map((node) => {
        const next = statusByKey.get(node.id) ?? null;
        if (node.data.status === next) return node;
        return { ...node, data: { ...node.data, status: next } };
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRun]);

  // Wrap React Flow's change handlers so we mark the canvas dirty on
  // structural / position changes.
  const handleNodesChange = useCallback<typeof onNodesChange>(
    (changes) => {
      const structural = changes.some(
        (c) =>
          c.type === "position" ||
          c.type === "remove" ||
          c.type === "dimensions" ||
          c.type === "replace",
      );
      if (structural) setDirty(true);
      onNodesChange(changes);
    },
    [onNodesChange],
  );

  const handleEdgesChange = useCallback<typeof onEdgesChange>(
    (changes) => {
      const structural = changes.some((c) => c.type === "remove" || c.type === "add");
      if (structural) setDirty(true);
      onEdgesChange(changes);
    },
    [onEdgesChange],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      if (connection.source === connection.target) return;
      setFlowEdges((prev) =>
        addEdge(
          {
            ...connection,
            id: `e-${Date.now()}-${connection.source}-${connection.target}`,
            type: "smoothstep",
            style: {
              stroke: "currentColor",
              strokeDasharray: "4 3",
              strokeOpacity: 0.6,
            },
          },
          prev,
        ),
      );
      setDirty(true);
    },
    [setFlowEdges],
  );

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      const kind = event.dataTransfer.getData(PALETTE_MIME) as WorkflowNodeKind | "";
      if (!kind) return;
      const position = reactFlow.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      const existingKeys = new Set(flowNodes.map((n) => n.id));
      const newKey = generateKey(existingKeys);
      const newNode: FlowNode = {
        id: newKey,
        type: "workflowNode",
        position,
        data: {
          name: KIND_LABEL[kind],
          kind,
          description: null,
          params: {},
          status: null,
          groupKey: null,
        },
      };
      setFlowNodes((prev) => [...prev, newNode]);
      setDirty(true);
    },
    [reactFlow, flowNodes, setFlowNodes],
  );

  const saveChanges = useCallback(async () => {
    if (!resolved || !doc) return;
    setSaving(true);
    setError(null);
    try {
      const nodeIds = new Set(flowNodes.map((n) => n.id));
      const validEdges = flowEdges.filter(
        (e) => nodeIds.has(e.source) && nodeIds.has(e.target),
      );
      const inboundCount = new Map<string, number>();
      flowNodes.forEach((n) => inboundCount.set(n.id, 0));
      validEdges.forEach((e) => {
        inboundCount.set(e.target, (inboundCount.get(e.target) ?? 0) + 1);
      });
      const entryKeys: string[] = [];
      inboundCount.forEach((count, key) => {
        if (count === 0) entryKeys.push(key);
      });

      const definitionNodes: WorkflowNode[] = flowNodes.map((n) => ({
        key: n.id,
        kind: n.data.kind,
        name: n.data.name,
        description: n.data.description,
        params: {
          ...(n.data.params ?? {}),
          _position: { x: n.position.x, y: n.position.y },
        },
        group_key: n.data.groupKey,
      }));
      const definitionEdges: WorkflowEdge[] = validEdges.map((e) => ({
        from_key: e.source,
        to_key: e.target,
        condition: null,
      }));

      const updated = await workflowDocumentsApi.update(
        resolved.slug,
        resolved.projectId,
        doc.id,
        {
          definition: {
            nodes: definitionNodes,
            edges: definitionEdges,
            entry_keys: entryKeys,
            groups: doc.definition.groups ?? [],
          },
        },
      );
      setDoc(updated);
      setDirty(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setSaving(false);
    }
  }, [resolved, doc, flowNodes, flowEdges]);

  const startRun = useCallback(async () => {
    if (!resolved || !doc) return;
    if (dirty) {
      setError("Save the workflow before starting a run.");
      return;
    }
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
  }, [resolved, doc, dirty]);

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

  const saveDocName = useCallback(async () => {
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

  const renameNode = useCallback(
    (nodeKey: string, newName: string) => {
      setFlowNodes((prev) =>
        prev.map((n) =>
          n.id === nodeKey ? { ...n, data: { ...n.data, name: newName } } : n,
        ),
      );
      setDirty(true);
    },
    [setFlowNodes],
  );

  const deleteNode = useCallback(
    (nodeKey: string) => {
      setFlowNodes((prev) => prev.filter((n) => n.id !== nodeKey));
      setFlowEdges((prev) =>
        prev.filter((e) => e.source !== nodeKey && e.target !== nodeKey),
      );
      setSelectedNodeKey(null);
      setDirty(true);
    },
    [setFlowNodes, setFlowEdges],
  );

  const saveReviewedGeometry = useCallback(
    async (reviewed: Geometry): Promise<void> => {
      if (!resolved || !activeRun) return;
      setBusy(true);
      setError(null);
      try {
        const updated = await workflowsApi.advanceManual(
          resolved.slug,
          resolved.projectId,
          activeRun.id,
          "architectural_review",
          {
            outputs: {
              reviewed_geometry: reviewed,
              reviewed_at: new Date().toISOString(),
            },
          },
        );
        setActiveRun(updated);
        setReviewMode(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
        throw err;
      } finally {
        setBusy(false);
      }
    },
    [resolved, activeRun],
  );

  const saveRoofFraming = useCallback(
    async (framing: RoofFraming): Promise<void> => {
      if (!resolved || !activeRun) return;
      setBusy(true);
      setError(null);
      try {
        const updated = await workflowsApi.advanceManual(
          resolved.slug,
          resolved.projectId,
          activeRun.id,
          "roof_framing",
          {
            outputs: {
              roof_framing: framing,
              roof_framing_at: new Date().toISOString(),
              roof_framing_coverage_pct: framing.coverage.coverage_pct,
            },
          },
        );
        setActiveRun(updated);
        setReviewMode(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
        throw err;
      } finally {
        setBusy(false);
      }
    },
    [resolved, activeRun],
  );

  const saveDetailLayout = useCallback(
    async (layout: DetailLayout): Promise<void> => {
      if (!resolved || !activeRun) return;
      setBusy(true);
      setError(null);
      try {
        const updated = await workflowsApi.advanceManual(
          resolved.slug,
          resolved.projectId,
          activeRun.id,
          "detail_edit",
          {
            outputs: {
              refined_option: layout,
              refined_at: new Date().toISOString(),
              refined_option_id: layout.option_id,
            },
          },
        );
        setActiveRun(updated);
        setReviewMode(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
        throw err;
      } finally {
        setBusy(false);
      }
    },
    [resolved, activeRun],
  );

  const selectedFlowNode = useMemo(() => {
    if (!selectedNodeKey) return null;
    return flowNodes.find((n) => n.id === selectedNodeKey) ?? null;
  }, [selectedNodeKey, flowNodes]);

  // Group-aware view layer. The source-of-truth `flowNodes` is always a
  // flat list of real nodes; the view layer collapses groups into
  // synthetic supernode cards. Edges crossing a collapsed group get
  // their endpoint rewritten to the group card; edges internal to a
  // collapsed group are hidden. Open/expanded groups render their
  // members normally.
  const { viewNodes, viewEdges } = useMemo(() => {
    const groupsByKey = new Map<string, WorkflowGroup>();
    (doc?.definition.groups ?? []).forEach((g) => groupsByKey.set(g.key, g));

    const membersByGroup = new Map<string, FlowNode[]>();
    flowNodes.forEach((n) => {
      const gk = n.data.groupKey;
      if (gk) {
        if (!membersByGroup.has(gk)) membersByGroup.set(gk, []);
        membersByGroup.get(gk)!.push(n);
      }
    });

    // We render real workflow nodes and synthetic group cards as one
    // mixed array; ReactFlow only cares about the `type` discriminator
    // to pick the renderer. We widen to Node so the union is accepted.
    const visibleNodes: Node[] = [];
    const nodeIdToGroupCard = new Map<string, string>();

    // Pass 1: emit one supernode per collapsed group.
    membersByGroup.forEach((members, groupKey) => {
      const def = groupsByKey.get(groupKey);
      const isCollapsed = collapsedGroups.has(groupKey) && def !== undefined;
      if (!isCollapsed) return;
      const avgX = members.reduce((acc, m) => acc + m.position.x, 0) / members.length;
      const avgY = members.reduce((acc, m) => acc + m.position.y, 0) / members.length;
      const groupId = groupCardId(groupKey);
      members.forEach((m) => nodeIdToGroupCard.set(m.id, groupId));
      const card: GroupFlowNode = {
        id: groupId,
        type: "groupCard",
        position: { x: avgX, y: avgY },
        draggable: false,
        deletable: false,
        data: {
          groupKey,
          name: def.name,
          description: def.description ?? null,
          memberCount: members.length,
          aggregateStatus: aggregateGroupStatus(members.map((m) => m.data.status)),
          onToggle: () => toggleGroup(groupKey),
        },
      };
      visibleNodes.push(card as unknown as Node);
    });

    // Pass 2: emit ungrouped nodes + members of expanded groups as-is.
    flowNodes.forEach((n) => {
      if (n.data.groupKey && collapsedGroups.has(n.data.groupKey)) return;
      visibleNodes.push(n as unknown as Node);
    });

    // Edges: rewrite endpoints that live inside a collapsed group to
    // point at the group card; drop edges fully internal to a single
    // collapsed group.
    const visibleEdges: Edge[] = [];
    flowEdges.forEach((e) => {
      const sourceGroup = nodeIdToGroupCard.get(e.source);
      const targetGroup = nodeIdToGroupCard.get(e.target);
      if (sourceGroup && targetGroup && sourceGroup === targetGroup) return;
      const next: Edge = { ...e };
      if (sourceGroup) next.source = sourceGroup;
      if (targetGroup) next.target = targetGroup;
      next.id = `${e.id}::${next.source}->${next.target}`;
      visibleEdges.push(next);
    });

    return { viewNodes: visibleNodes, viewEdges: visibleEdges };
  }, [flowNodes, flowEdges, doc, collapsedGroups, toggleGroup]);

  // Wrap onNodesChange to ignore changes targeting group cards (they
  // are read-only proxies; the source-of-truth nodes do not move when
  // the user drags a card). Member dragging happens when the group is
  // expanded, which goes through the normal pathway.
  const handleViewNodesChange = useCallback<typeof onNodesChange>(
    (changes) => {
      const realChanges = changes.filter((c) => {
        const targetId =
          "id" in c
            ? c.id
            : "item" in c && c.item && typeof c.item === "object"
              ? (c.item as { id?: string }).id
              : undefined;
        if (typeof targetId === "string" && isGroupCardId(targetId)) return false;
        return true;
      });
      handleNodesChange(realChanges);
    },
    [handleNodesChange],
  );

  const selectedRunNode = useMemo<WorkflowRunNode | null>(() => {
    if (!selectedNodeKey || !activeRun) return null;
    return activeRun.nodes.find((n) => n.node_key === selectedNodeKey) ?? null;
  }, [selectedNodeKey, activeRun]);

  if (doc === null) {
    return (
      <div className="grid min-h-[60vh] place-items-center text-sm text-muted-foreground">
        {error ?? "Loading workflow..."}
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] w-full flex-col">
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
              onBlur={() => void saveDocName()}
              onKeyDown={(e) => {
                if (e.key === "Enter") void saveDocName();
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
          {dirty && (
            <span className="ml-1 inline-flex h-1.5 w-1.5 rounded-full bg-amber-500" />
          )}
        </div>
        <div className="flex items-center gap-2">
          {activeRun && (
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Run: {activeRun.status}
            </span>
          )}
          {dirty && (
            <button
              type="button"
              onClick={() => void saveChanges()}
              disabled={saving}
              className="inline-flex items-center gap-1 rounded border border-border bg-background px-3 py-1 text-xs font-medium hover:bg-surface-hover disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="size-3 animate-spin" aria-hidden="true" />
              ) : (
                <Save className="size-3" aria-hidden="true" />
              )}
              Save
            </button>
          )}
          <button
            type="button"
            onClick={() => void startRun()}
            disabled={busy || flowNodes.length === 0 || dirty}
            title={dirty ? "Save the workflow first" : ""}
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
        <div className="relative flex-1 bg-background" ref={reactFlowWrapperRef}>
          {reviewMode === "review" && resolved && activeRun ? (
            <FloorReviewEditor
              activeRun={activeRun}
              orgSlug={resolved.slug}
              projectId={resolved.projectId}
              runId={activeRun.id}
              busy={busy}
              onCancel={() => setReviewMode(null)}
              onSave={saveReviewedGeometry}
            />
          ) : reviewMode === "roof" && resolved && activeRun ? (
            <RoofFramingEditor
              activeRun={activeRun}
              orgSlug={resolved.slug}
              projectId={resolved.projectId}
              runId={activeRun.id}
              busy={busy}
              onCancel={() => setReviewMode(null)}
              onSave={saveRoofFraming}
            />
          ) : reviewMode === "detail" && resolved && activeRun ? (
            <DetailEditEditor
              activeRun={activeRun}
              orgSlug={resolved.slug}
              projectId={resolved.projectId}
              runId={activeRun.id}
              busy={busy}
              onCancel={() => setReviewMode(null)}
              onSave={saveDetailLayout}
            />
          ) : flowNodes.length === 0 ? (
            <div className="grid h-full place-items-center px-6 text-center">
              <div className="max-w-md">
                <WorkflowIcon
                  className="mx-auto mb-3 size-8 text-muted-foreground"
                  aria-hidden="true"
                />
                <p className="text-sm text-foreground">This workflow is empty.</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Drag a component from the right palette to add a node, then drag
                  between node handles to connect them.
                </p>
              </div>
              <div
                className="absolute inset-0"
                onDrop={onDrop}
                onDragOver={onDragOver}
              />
            </div>
          ) : (
            <ReactFlow
              nodes={viewNodes as unknown as FlowNode[]}
              edges={viewEdges}
              nodeTypes={NODE_TYPES}
              onNodesChange={handleViewNodesChange}
              onEdgesChange={handleEdgesChange}
              onConnect={onConnect}
              onDrop={onDrop}
              onDragOver={onDragOver}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              proOptions={{ hideAttribution: true }}
              nodesDraggable
              nodesConnectable
              elementsSelectable
              onNodeClick={(_, node) => {
                // Clicking a group card is a no-op here; the card's
                // own click handler toggles collapse. Selecting it for
                // the side modal would be misleading because the card
                // is synthetic and not editable.
                if (isGroupCardId(node.id)) return;
                setSelectedNodeKey(node.id);
              }}
              deleteKeyCode={["Backspace", "Delete"]}
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>
          )}
        </div>

        <aside className="w-72 shrink-0 overflow-y-auto border-l border-border bg-surface">
          <Sidebar
            doc={doc}
            recentRuns={recentRuns}
            activeRunId={activeRun?.id ?? null}
            onSelectRun={(run) => setActiveRun(run)}
            onRefresh={refreshActiveRun}
            flowNodes={flowNodes}
            collapsedGroups={collapsedGroups}
            onToggleGroup={toggleGroup}
          />
        </aside>
      </div>

      {selectedFlowNode && (
        <NodeDetailModal
          flowNode={selectedFlowNode}
          runNode={selectedRunNode}
          activeRun={activeRun}
          orgSlug={resolved?.slug ?? null}
          projectId={resolved?.projectId ?? null}
          busy={busy}
          note={noteDraft}
          onNoteChange={setNoteDraft}
          onClose={() => {
            setSelectedNodeKey(null);
            setNoteDraft("");
          }}
          onRename={(value) => renameNode(selectedFlowNode.id, value)}
          onDelete={() => deleteNode(selectedFlowNode.id)}
          onManualDone={() => void advanceManual(selectedFlowNode.id)}
          onApprove={() => void submitGate(selectedFlowNode.id, "approved")}
          onReject={() => void submitGate(selectedFlowNode.id, "rejected")}
          onOpenReviewEditor={(mode) => {
            setSelectedNodeKey(null);
            setReviewMode(mode);
          }}
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
  flowNodes,
  collapsedGroups,
  onToggleGroup,
}: {
  doc: WorkflowDocument;
  recentRuns: WorkflowRun[];
  activeRunId: string | null;
  onSelectRun: (run: WorkflowRun) => void;
  onRefresh: () => void;
  flowNodes: FlowNode[];
  collapsedGroups: Set<string>;
  onToggleGroup: (groupKey: string) => void;
}) {
  // Per-group rollup for the Groups section. Built from the same source
  // flowNodes the canvas reads, so collapse/expand here mirrors the
  // canvas state exactly.
  const groupRollups = (doc.definition.groups ?? []).map((g) => {
    const members = flowNodes.filter((n) => n.data.groupKey === g.key);
    return {
      key: g.key,
      name: g.name,
      description: g.description ?? null,
      memberCount: members.length,
      aggregateStatus: aggregateGroupStatus(members.map((m) => m.data.status)),
      collapsed: collapsedGroups.has(g.key),
    };
  });

  return (
    <div className="space-y-5 p-4">
      {groupRollups.length > 0 && (
        <section>
          <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Groups
          </h3>
          <ul className="space-y-1">
            {groupRollups.map((g) => {
              const status = g.aggregateStatus ?? "pending";
              return (
                <li key={g.key}>
                  <button
                    type="button"
                    onClick={() => onToggleGroup(g.key)}
                    className={`w-full rounded border px-2 py-1.5 text-left text-xs ${STATUS_TONE[status]}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{g.name}</span>
                      <span className="text-[10px] opacity-70">
                        {g.collapsed ? "expand" : "collapse"}
                      </span>
                    </div>
                    <div className="mt-0.5 text-[10px] opacity-70">
                      {g.memberCount} steps · {status}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section>
        <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Components
        </h3>
        <p className="mb-2 text-[10px] text-muted-foreground">
          Drag onto the canvas to add a node.
        </p>
        <ul className="grid grid-cols-2 gap-1">
          {PALETTE_KINDS.map((kind) => (
            <li key={kind}>
              <button
                type="button"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData(PALETTE_MIME, kind);
                  event.dataTransfer.effectAllowed = "move";
                }}
                className="w-full cursor-grab rounded border border-border bg-background px-2 py-1.5 text-[11px] text-foreground transition-colors hover:border-brand-300 hover:bg-surface-hover active:cursor-grabbing"
              >
                {KIND_LABEL[kind]}
              </button>
            </li>
          ))}
        </ul>
      </section>

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
    </div>
  );
}

function NodeDetailModal({
  flowNode,
  runNode,
  activeRun,
  orgSlug,
  projectId,
  busy,
  note,
  onNoteChange,
  onClose,
  onRename,
  onDelete,
  onManualDone,
  onApprove,
  onReject,
  onOpenReviewEditor,
}: {
  flowNode: FlowNode;
  runNode: WorkflowRunNode | null;
  activeRun: WorkflowRun | null;
  orgSlug: string | null;
  projectId: string | null;
  busy: boolean;
  note: string;
  onNoteChange: (value: string) => void;
  onClose: () => void;
  onRename: (value: string) => void;
  onDelete: () => void;
  onManualDone: () => void;
  onOpenReviewEditor?: ((mode: "review" | "roof" | "detail") => void) | undefined;
  onApprove: () => void;
  onReject: () => void;
}) {
  const [nameDraft, setNameDraft] = useState(flowNode.data.name);

  useEffect(() => {
    setNameDraft(flowNode.data.name);
  }, [flowNode.id, flowNode.data.name]);

  const status = runNode?.status ?? "pending";
  const Icon =
    status === "completed"
      ? Check
      : status === "failed" || status === "skipped"
        ? CircleX
        : status === "running"
          ? Loader2
          : CircleDashed;
  const showManualAction = flowNode.data.kind === "manual" && status === "ready";
  const showGateAction =
    (flowNode.data.kind === "gate.review" || flowNode.data.kind === "gate.approve") &&
    status === "ready";

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
            <div
              className={`mt-0.5 grid size-8 place-items-center rounded ${STATUS_TONE[status]}`}
            >
              <Icon className={`size-4 ${status === "running" ? "animate-spin" : ""}`} />
            </div>
            <div className="min-w-0 flex-1">
              <input
                type="text"
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                onBlur={() => {
                  const trimmed = nameDraft.trim();
                  if (trimmed && trimmed !== flowNode.data.name) onRename(trimmed);
                }}
                className="block w-full rounded border border-transparent bg-transparent px-1 py-0.5 text-sm font-medium text-foreground hover:border-border focus:border-brand-300 focus:outline-none"
              />
              <div className="mt-0.5 flex items-center gap-2 px-1 text-[11px] text-muted-foreground">
                <span>{KIND_LABEL[flowNode.data.kind]}</span>
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
          {flowNode.data.description && (
            <p className="text-sm text-foreground-light">{flowNode.data.description}</p>
          )}
          {runNode?.error && (
            <p className="rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {runNode.error}
            </p>
          )}

          <NodeWorkbench
            flowNode={flowNode}
            activeRun={activeRun}
            orgSlug={orgSlug}
            projectId={projectId}
            onOpenReviewEditor={onOpenReviewEditor}
          />

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

          <div className="border-t border-border pt-3">
            <button
              type="button"
              onClick={() => {
                if (
                  window.confirm(
                    "Delete this node? Connected edges will also be removed. Save to persist.",
                  )
                ) {
                  onDelete();
                }
              }}
              className="inline-flex items-center gap-1 rounded border border-destructive/30 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/5"
            >
              <Trash2 className="size-3" aria-hidden="true" />
              Delete node
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// NodeWorkbench dispatches per-node-key custom UI. Today only the
// Origin architectural_review node has a workbench (floor-preview
// gallery rendered from the upstream floor_parse outputs). Other
// nodes fall back to a brief placeholder.
function NodeWorkbench({
  flowNode,
  activeRun,
  orgSlug,
  projectId,
  onOpenReviewEditor,
}: {
  flowNode: FlowNode;
  activeRun: WorkflowRun | null;
  orgSlug: string | null;
  projectId: string | null;
  onOpenReviewEditor?: ((mode: "review" | "roof" | "detail") => void) | undefined;
}) {
  if (flowNode.id === "architectural_review") {
    return (
      <OriginFloorGallery
        activeRun={activeRun}
        orgSlug={orgSlug}
        projectId={projectId}
        onOpenReviewEditor={
          onOpenReviewEditor ? () => onOpenReviewEditor("review") : undefined
        }
      />
    );
  }
  if (flowNode.id === "roof_framing") {
    return (
      <OriginRoofFramingPanel
        activeRun={activeRun}
        onOpenReviewEditor={
          onOpenReviewEditor ? () => onOpenReviewEditor("roof") : undefined
        }
      />
    );
  }
  if (flowNode.id === "select_option") {
    return <OriginSelectOptionPanel activeRun={activeRun} />;
  }
  if (flowNode.id === "detail_edit") {
    return (
      <OriginDetailEditPanel
        activeRun={activeRun}
        onOpenReviewEditor={
          onOpenReviewEditor ? () => onOpenReviewEditor("detail") : undefined
        }
      />
    );
  }
  return (
    <div className="rounded border border-dashed border-border bg-surface p-6 text-center text-xs text-muted-foreground">
      A node-specific workbench will live here. For Origin floor parse
      review, open the architectural_review node to see the parsed
      floors.
    </div>
  );
}

function OriginDetailEditPanel({
  activeRun,
  onOpenReviewEditor,
}: {
  activeRun: WorkflowRun | null;
  onOpenReviewEditor?: (() => void) | undefined;
}) {
  const aiNode = activeRun?.nodes.find((n) => n.node_key === "ai_options") ?? null;
  const options =
    (aiNode?.outputs?.options as OriginStructuralOption[] | undefined) ?? [];
  const selectNode = activeRun?.nodes.find((n) => n.node_key === "select_option");
  const note = selectNode?.outputs?.note as string | undefined;
  const chosenId = pickOptionIdFromNoteText(note, options);
  const chosen = options.find((o) => o.option_id === chosenId) ?? options[0] ?? null;

  const detailNode = activeRun?.nodes.find((n) => n.node_key === "detail_edit");
  const refined = detailNode?.outputs?.refined_option_id as string | undefined;

  return (
    <div className="space-y-3">
      <div className="rounded border border-border bg-surface px-3 py-2 text-[11px] text-muted-foreground">
        Detail the chosen option member-by-member. Toggle layers, click any
        column or beam to change its size, and watch the DCR colour update.
        Save persists the refined layout for the export step.
      </div>
      {chosen ? (
        <div className="rounded border border-border bg-background px-3 py-2 text-[11px]">
          <span className="text-muted-foreground">Working on:</span>{" "}
          <span className="font-medium">{chosen.primary_structure}</span>{" "}
          <span className="text-muted-foreground">
            ({chosen.option_id} · bay {chosen.bay_grid_m.x_m.toFixed(1)} x{" "}
            {chosen.bay_grid_m.y_m.toFixed(1)} m)
          </span>
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          ai_options has not produced a shortlist yet; finish that step first.
        </p>
      )}
      {refined && (
        <div className="rounded border border-emerald-300/50 bg-emerald-50/40 px-3 py-2 text-[11px] text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300">
          Refined detail saved for option <span className="font-mono">{refined}</span>.
          Reopen the editor to make further edits.
        </div>
      )}
      {onOpenReviewEditor && chosen && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onOpenReviewEditor}
            className="inline-flex items-center gap-1 rounded border border-brand-300 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-100 dark:bg-accent dark:text-accent-foreground"
          >
            Open detail editor
          </button>
        </div>
      )}
    </div>
  );
}

function pickOptionIdFromNoteText(
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

function OriginRoofFramingPanel({
  activeRun,
  onOpenReviewEditor,
}: {
  activeRun: WorkflowRun | null;
  onOpenReviewEditor?: (() => void) | undefined;
}) {
  const node = activeRun?.nodes.find((n) => n.node_key === "roof_framing") ?? null;
  const saved = node?.outputs?.roof_framing as
    | { coverage?: { coverage_pct?: number } }
    | undefined;
  const pct = saved?.coverage?.coverage_pct ?? null;

  const reviewNode = activeRun?.nodes.find((n) => n.node_key === "architectural_review");
  const reviewedReady = (reviewNode?.status ?? "pending") === "completed";

  return (
    <div className="space-y-3">
      <div className="rounded border border-border bg-surface px-3 py-2 text-[11px] text-muted-foreground">
        Plan where regular trusses cover the roof. The editor enforces
        full coverage of the roof footprint and lets you add girder
        trusses + beams across the rest of the structure.
      </div>
      {pct !== null && (
        <div
          className={`rounded border px-3 py-1.5 text-[11px] ${
            pct >= 100
              ? "border-emerald-300/50 bg-emerald-50/40 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"
              : pct >= 90
                ? "border-amber-300/60 bg-amber-50/50 text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
                : "border-destructive/40 bg-destructive/10 text-destructive"
          }`}
        >
          Last saved coverage: {Math.round(pct)}%
        </div>
      )}
      {!reviewedReady && (
        <p className="text-[11px] text-muted-foreground">
          Architectural review has not completed. The editor will fall back to
          the raw parsed geometry; finish review for higher-fidelity edits.
        </p>
      )}
      {onOpenReviewEditor && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onOpenReviewEditor}
            className="inline-flex items-center gap-1 rounded border border-brand-300 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-100 dark:bg-accent dark:text-accent-foreground"
          >
            Open roof framing editor
          </button>
        </div>
      )}
    </div>
  );
}

// Origin select_option workbench. Reads the three structural options
// emitted by ai_options.outputs and renders them as side-by-side cards
// matching Genia's three-option modal: takeoff, DCR distribution,
// constructibility. The Approve/Reject buttons live on the node detail
// modal proper; this panel makes the choice informed by surfacing the
// numbers the engineer needs to compare.
function OriginSelectOptionPanel({
  activeRun,
}: {
  activeRun: WorkflowRun | null;
}) {
  const aiNode = activeRun?.nodes.find((n) => n.node_key === "ai_options") ?? null;
  const options = (aiNode?.outputs?.options as OriginStructuralOption[] | undefined) ?? [];
  const note = aiNode?.outputs?.note as string | undefined;
  const model = aiNode?.outputs?.model as string | undefined;

  if (!aiNode) {
    return (
      <div className="rounded border border-dashed border-border bg-surface p-6 text-center text-xs text-muted-foreground">
        ai_options has not run yet on this workflow. Start a run from
        this document so the AI shortlist appears here.
      </div>
    );
  }
  if (aiNode.status !== "completed") {
    return (
      <div className="rounded border border-dashed border-border bg-surface p-6 text-center text-xs text-muted-foreground">
        ai_options status: <span className="uppercase">{aiNode.status}</span>.{" "}
        {aiNode.error ?? "Waiting for the design engine to finish."}
      </div>
    );
  }
  if (options.length === 0) {
    return (
      <div className="rounded border border-dashed border-border bg-surface p-6 text-center text-xs text-muted-foreground">
        ai_options completed but produced no options. Check the architectural
        review and roof framing steps; rerun ai_options.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-muted-foreground">
        Pick which option proceeds to detail-edit and seal. Use the Approve
        button below and record the option_id in the note field.
        {model === "engine"
          ? " (LLM polish is off; structural numbers come from the deterministic engine.)"
          : null}
      </p>
      {note && (
        <p className="rounded border border-border bg-surface px-3 py-1.5 text-[11px] text-muted-foreground">
          {note}
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {options.map((opt) => (
          <OriginOptionCard key={opt.option_id} option={opt} />
        ))}
      </div>
    </div>
  );
}

function OriginOptionCard({ option }: { option: OriginStructuralOption }) {
  const dcr = option.dcr_distribution;
  return (
    <div className="flex flex-col gap-2 rounded border border-border bg-background p-3 text-[11px]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {option.variant}
        </span>
        <span className="rounded bg-surface px-1.5 py-0.5 text-[10px] font-mono">
          {option.option_id}
        </span>
      </div>
      <div className="text-sm font-semibold text-foreground">
        {option.primary_structure}
      </div>
      <p className="text-foreground-light">{option.summary}</p>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
        <dt className="text-muted-foreground">Bay grid</dt>
        <dd className="text-right">
          {option.bay_grid_m.x_m.toFixed(1)} x {option.bay_grid_m.y_m.toFixed(1)} m
        </dd>
        <dt className="text-muted-foreground">Slab</dt>
        <dd className="text-right">{option.slab_type}</dd>
        <dt className="text-muted-foreground">Material</dt>
        <dd className="text-right">{option.material}</dd>
        <dt className="text-muted-foreground">Prelim load</dt>
        <dd className="text-right">{option.prelim_load_kN_m2.toFixed(1)} kN/m²</dd>
        <dt className="text-muted-foreground">BoQ</dt>
        <dd className="text-right">€{Math.round(option.boq_estimate_eur_m2)} /m²</dd>
        <dt className="text-muted-foreground">Total BoQ</dt>
        <dd className="text-right">€{Math.round(option.boq_total_eur).toLocaleString()}</dd>
      </dl>

      <div>
        <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Material takeoff
        </div>
        <ul className="space-y-0.5 text-[10px]">
          {option.takeoff.structural_steel_kg > 0 && (
            <li>
              Steel: {Math.round(option.takeoff.structural_steel_kg).toLocaleString()} kg
            </li>
          )}
          {option.takeoff.concrete_m3 > 0 && (
            <li>Concrete: {option.takeoff.concrete_m3.toFixed(1)} m³</li>
          )}
          {option.takeoff.rebar_kg > 0 && (
            <li>Rebar: {Math.round(option.takeoff.rebar_kg).toLocaleString()} kg</li>
          )}
          {option.takeoff.clt_m3 > 0 && (
            <li>CLT: {option.takeoff.clt_m3.toFixed(1)} m³</li>
          )}
          {option.takeoff.glulam_m3 > 0 && (
            <li>Glulam: {option.takeoff.glulam_m3.toFixed(1)} m³</li>
          )}
        </ul>
      </div>

      <div>
        <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          DCR distribution
        </div>
        <DcrBar dcr={dcr} />
      </div>

      <div>
        <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Constructibility
        </div>
        <p className="text-[10px]">
          {option.constructibility.total_unique_sizes} unique sections (
          {option.constructibility.unique_beam_sizes} beam,{" "}
          {option.constructibility.unique_column_sizes} column)
        </p>
      </div>

      <div>
        <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Sustainability
        </div>
        <p className="text-[10px] text-foreground-light">
          {option.sustainability_note}
        </p>
      </div>

      {option.caveats.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Caveats
          </div>
          <ul className="list-disc space-y-0.5 pl-4 text-[10px] text-foreground-light">
            {option.caveats.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function DcrBar({ dcr }: { dcr: OriginStructuralOption["dcr_distribution"] }) {
  // Inline-svg horizontal stacked bar showing DCR distribution.
  const segments = [
    { label: "<60", value: dcr.under_60_pct, color: "#7BB39C" },
    { label: "60-80", value: dcr.between_60_80, color: "#C1A857" },
    { label: "80-100", value: dcr.between_80_100, color: "#C77F49" },
    { label: ">100", value: dcr.over_100, color: "#C0463E" },
  ];
  const total = Math.max(0.0001, segments.reduce((s, x) => s + x.value, 0));
  let cumulative = 0;
  return (
    <div className="space-y-1">
      <svg viewBox="0 0 100 6" width="100%" height="14" preserveAspectRatio="none">
        {segments.map((seg) => {
          const w = (seg.value / total) * 100;
          const x = cumulative;
          cumulative += w;
          return <rect key={seg.label} x={x} y={0} width={w} height={6} fill={seg.color} />;
        })}
      </svg>
      <div className="flex flex-wrap gap-x-2 text-[9px] text-muted-foreground">
        {segments.map((seg) => (
          <span key={seg.label} className="inline-flex items-center gap-1">
            <span
              className="inline-block size-2 rounded-sm"
              style={{ backgroundColor: seg.color }}
            />
            {seg.label}: {Math.round(seg.value * 100)}%
          </span>
        ))}
      </div>
    </div>
  );
}

interface ParsedFloorEntry {
  floor_key: string;
  name: string;
  is_roof: boolean;
  svg_key: string;
  svg_inline?: string;
}

interface FloorParseOutputs {
  geometry_summary?: {
    source_format?: string;
    floor_count?: number;
    wall_count?: number;
    column_count?: number;
    opening_count?: number;
    slab_count?: number;
    floor_names?: string[];
  };
  floor_svgs?: ParsedFloorEntry[];
  quality_report?: {
    checks: Array<{
      name: string;
      status: "ok" | "warning" | "error";
      message: string;
    }>;
  };
  parser_notes?: string[];
  parsed_at?: string;
}

function OriginFloorGallery({
  activeRun,
  orgSlug,
  projectId,
  onOpenReviewEditor,
}: {
  activeRun: WorkflowRun | null;
  orgSlug: string | null;
  projectId: string | null;
  onOpenReviewEditor?: (() => void) | undefined;
}) {
  const floorParseNode = useMemo(
    () => activeRun?.nodes.find((n) => n.node_key === "floor_parse") ?? null,
    [activeRun],
  );

  const outputs = floorParseNode?.outputs as FloorParseOutputs | undefined;
  const floors = outputs?.floor_svgs ?? [];
  const summary = outputs?.geometry_summary;
  const report = outputs?.quality_report;

  if (!floorParseNode) {
    return (
      <div className="rounded border border-dashed border-border bg-surface p-6 text-center text-xs text-muted-foreground">
        Start a run from this workflow to parse the architect CAD; the
        parsed floors will appear here for review.
      </div>
    );
  }
  if (floorParseNode.status !== "completed") {
    return (
      <div className="rounded border border-dashed border-border bg-surface p-6 text-center text-xs text-muted-foreground">
        Floor parse status: <span className="uppercase">{floorParseNode.status}</span>.{" "}
        {floorParseNode.error ?? "Waiting for the parser to finish."}
      </div>
    );
  }
  if (floors.length === 0) {
    return (
      <div className="rounded border border-dashed border-border bg-surface p-6 text-center text-xs text-muted-foreground">
        Floor parse completed but produced no floors. Re-upload the CAD with
        per-floor layouts (DXF) or building storeys (IFC).
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {summary && (
        <div className="rounded border border-border bg-surface px-3 py-2 text-[11px] text-muted-foreground">
          Parsed from <span className="uppercase">{summary.source_format}</span>:{" "}
          {summary.floor_count} floors · {summary.wall_count} walls ·{" "}
          {summary.column_count} columns · {summary.opening_count} openings
        </div>
      )}

      {report && (
        <div className="space-y-1">
          {report.checks.map((c) => (
            <div
              key={c.name}
              className={`flex items-start gap-2 rounded border px-2.5 py-1.5 text-[11px] ${
                c.status === "ok"
                  ? "border-emerald-300/50 bg-emerald-50/40 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"
                  : c.status === "warning"
                    ? "border-amber-300/60 bg-amber-50/50 text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
                    : "border-destructive/40 bg-destructive/10 text-destructive"
              }`}
            >
              <span className="font-medium capitalize">{c.name.replace(/_/g, " ")}</span>
              <span>·</span>
              <span className="flex-1">{c.message}</span>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {floors.map((entry) => (
          <FloorPreviewCard
            key={entry.floor_key}
            entry={entry}
            runId={activeRun?.id ?? null}
            orgSlug={orgSlug}
            projectId={projectId}
          />
        ))}
      </div>

      {onOpenReviewEditor && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onOpenReviewEditor}
            className="inline-flex items-center gap-1 rounded border border-brand-300 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-100 dark:bg-accent dark:text-accent-foreground"
          >
            Open architectural review editor
          </button>
        </div>
      )}
    </div>
  );
}

function FloorPreviewCard({
  entry,
  runId,
  orgSlug,
  projectId,
}: {
  entry: ParsedFloorEntry;
  runId: string | null;
  orgSlug: string | null;
  projectId: string | null;
}) {
  const [svgUrl, setSvgUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (entry.svg_inline) {
        setSvgUrl(
          `data:image/svg+xml;utf8,${encodeURIComponent(entry.svg_inline)}`,
        );
        return;
      }
      if (!entry.svg_key || !runId || !orgSlug || !projectId) return;
      try {
        const presigned = await workflowsApi.getArtifactUrl(
          orgSlug,
          projectId,
          runId,
          entry.svg_key,
        );
        if (!cancelled) setSvgUrl(presigned.url);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : String(err));
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [entry.svg_key, entry.svg_inline, runId, orgSlug, projectId]);

  return (
    <div className="overflow-hidden rounded border border-border bg-background">
      <div className="flex items-center justify-between gap-2 border-b border-border px-2.5 py-1.5 text-[11px]">
        <span className="font-medium">{entry.name}</span>
        {entry.is_roof && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            Roof
          </span>
        )}
      </div>
      <div className="grid aspect-[4/3] place-items-center bg-surface">
        {svgUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={svgUrl}
            alt={`Parsed plan for ${entry.name}`}
            className="size-full object-contain"
          />
        ) : error ? (
          <span className="px-3 text-[10px] text-destructive">{error}</span>
        ) : (
          <Loader2
            className="size-4 animate-spin text-muted-foreground"
            aria-hidden="true"
          />
        )}
      </div>
    </div>
  );
}
