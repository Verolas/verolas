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
          {flowNodes.length === 0 ? (
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
          />
        </aside>
      </div>

      {selectedFlowNode && (
        <NodeDetailModal
          flowNode={selectedFlowNode}
          runNode={selectedRunNode}
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
  busy,
  note,
  onNoteChange,
  onClose,
  onRename,
  onDelete,
  onManualDone,
  onApprove,
  onReject,
}: {
  flowNode: FlowNode;
  runNode: WorkflowRunNode | null;
  busy: boolean;
  note: string;
  onNoteChange: (value: string) => void;
  onClose: () => void;
  onRename: (value: string) => void;
  onDelete: () => void;
  onManualDone: () => void;
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

          <div className="rounded border border-dashed border-border bg-surface p-6 text-center text-xs text-muted-foreground">
            The node-specific workbench (e.g. the structural concept generator for
            Verolas Origin, the calc workbench for an Analysis node) opens here in a
            later stage. For now, this overlay surfaces run-time actions plus basic
            edit controls.
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
