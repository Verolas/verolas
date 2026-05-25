"use client";

import {
  ArrowLeft,
  Check,
  CheckCircle2,
  CircleDashed,
  CircleX,
  Loader2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  type WorkflowNodeKind,
  type WorkflowNodeStatus,
  type WorkflowRun,
  type WorkflowRunNode,
  workflowsApi,
} from "@/lib/api";

interface Props {
  params: Promise<{ slug: string; projectId: string; runId: string }>;
}

const STATUS_ICON: Partial<Record<WorkflowNodeStatus, typeof Check>> = {
  pending: CircleDashed,
  ready: CircleDashed,
  running: Loader2,
  completed: CheckCircle2,
  failed: CircleX,
  skipped: CircleX,
};

const STATUS_TONE: Record<WorkflowNodeStatus, string> = {
  pending: "text-muted-foreground",
  ready: "text-brand-700 dark:text-brand-300",
  running: "text-brand-700 dark:text-brand-300",
  paused: "text-discipline-water",
  completed: "text-emerald-700 dark:text-emerald-400",
  failed: "text-destructive",
  skipped: "text-muted-foreground",
};

const KIND_LABEL: Record<WorkflowNodeKind, string> = {
  automated: "Automated",
  "gate.review": "Review gate",
  "gate.approve": "Approval gate",
  "gate.signature": "Signature gate",
  manual: "Manual step",
  external_wait: "External wait",
  "branch.condition": "Branch",
  "branch.iterate": "Loop",
  submission: "Submission",
  notification: "Notification",
};

const RUN_STATUS_TONE: Record<WorkflowRun["status"], string> = {
  pending: "border-border text-muted-foreground",
  running: "border-brand-200 text-brand-700",
  paused: "border-discipline-water/40 text-discipline-water",
  completed: "border-emerald-300/40 text-emerald-700 dark:text-emerald-400",
  failed: "border-destructive/30 text-destructive",
  cancelled: "border-border text-muted-foreground",
};

export default function WorkflowRunPage({ params }: Props) {
  const [resolved, setResolved] = useState<
    { slug: string; projectId: string; runId: string } | null
  >(null);
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyNodeKey, setBusyNodeKey] = useState<string | null>(null);
  const [noteByNode, setNoteByNode] = useState<Record<string, string>>({});

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  const reload = useCallback(async () => {
    if (!resolved) return;
    try {
      const r = await workflowsApi.getRun(
        resolved.slug,
        resolved.projectId,
        resolved.runId,
      );
      setRun(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }, [resolved]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const advanceManual = useCallback(
    async (nodeKey: string) => {
      if (!resolved) return;
      setBusyNodeKey(nodeKey);
      setError(null);
      try {
        const r = await workflowsApi.advanceManual(
          resolved.slug,
          resolved.projectId,
          resolved.runId,
          nodeKey,
        );
        setRun(r);
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusyNodeKey(null);
      }
    },
    [resolved],
  );

  const submitGate = useCallback(
    async (nodeKey: string, decision: "approved" | "rejected") => {
      if (!resolved) return;
      setBusyNodeKey(nodeKey);
      setError(null);
      try {
        const r = await workflowsApi.advanceGate(
          resolved.slug,
          resolved.projectId,
          resolved.runId,
          nodeKey,
          { decision, note: noteByNode[nodeKey] ?? null },
        );
        setRun(r);
        setNoteByNode((prev) => {
          const next = { ...prev };
          delete next[nodeKey];
          return next;
        });
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusyNodeKey(null);
      }
    },
    [resolved, noteByNode],
  );

  const cancelRun = useCallback(async () => {
    if (!resolved || !run) return;
    if (!window.confirm("Cancel this run? Non-terminal nodes will be marked skipped.")) {
      return;
    }
    setBusyNodeKey("__cancel__");
    setError(null);
    try {
      const r = await workflowsApi.cancelRun(
        resolved.slug,
        resolved.projectId,
        resolved.runId,
      );
      setRun(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusyNodeKey(null);
    }
  }, [resolved, run]);

  const isCancellable =
    run !== null && !["completed", "failed", "cancelled"].includes(run.status);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-8 py-8">
      <div>
        <Link
          href={
            resolved
              ? `/o/${resolved.slug}/projects/${resolved.projectId}/workflows`
              : "#"
          }
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          prefetch={false}
        >
          <ArrowLeft className="size-3" aria-hidden="true" />
          Back to Workflows
        </Link>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {run === null ? (
        <div className="rounded-md border border-border bg-surface p-10 text-center text-sm text-muted-foreground">
          Loading run...
        </div>
      ) : (
        <>
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-normal tracking-tight text-foreground">
                {run.template_name}
              </h1>
              <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                <span
                  className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${RUN_STATUS_TONE[run.status]}`}
                >
                  {run.status}
                </span>
                <span>
                  Started {run.started_at ? new Date(run.started_at).toLocaleString() : "queued"}
                </span>
                {run.completed_at && (
                  <span>· Finished {new Date(run.completed_at).toLocaleString()}</span>
                )}
              </div>
            </div>
            {isCancellable && (
              <button
                type="button"
                onClick={() => void cancelRun()}
                disabled={busyNodeKey === "__cancel__"}
                className="inline-flex items-center gap-1 rounded border border-destructive/30 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/5 disabled:opacity-50"
              >
                Cancel run
              </button>
            )}
          </header>

          <section className="space-y-3">
            <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Nodes
            </h2>
            <ol className="space-y-2">
              {run.nodes.map((node) => (
                <NodeRow
                  key={node.id}
                  node={node}
                  busy={busyNodeKey === node.node_key}
                  note={noteByNode[node.node_key] ?? ""}
                  onNoteChange={(value) =>
                    setNoteByNode((prev) => ({ ...prev, [node.node_key]: value }))
                  }
                  onManualDone={() => void advanceManual(node.node_key)}
                  onApprove={() => void submitGate(node.node_key, "approved")}
                  onReject={() => void submitGate(node.node_key, "rejected")}
                />
              ))}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}

function NodeRow({
  node,
  busy,
  note,
  onNoteChange,
  onManualDone,
  onApprove,
  onReject,
}: {
  node: WorkflowRunNode;
  busy: boolean;
  note: string;
  onNoteChange: (value: string) => void;
  onManualDone: () => void;
  onApprove: () => void;
  onReject: () => void;
}) {
  const Icon = STATUS_ICON[node.status] ?? CircleDashed;
  const showManualAction = node.kind === "manual" && node.status === "ready";
  const showGateAction =
    (node.kind === "gate.review" || node.kind === "gate.approve") &&
    node.status === "ready";

  return (
    <li className="rounded-md border border-border bg-surface px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <Icon
            className={`mt-0.5 size-4 shrink-0 ${STATUS_TONE[node.status]} ${
              node.status === "running" ? "animate-spin" : ""
            }`}
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-foreground">
                {String(node.params?.["name"] ?? node.node_key)}
              </span>
              <span className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                {KIND_LABEL[node.kind]}
              </span>
              <span className={`text-[11px] uppercase tracking-wider ${STATUS_TONE[node.status]}`}>
                {node.status}
              </span>
              {node.gate_decision && (
                <span className="text-[10px] text-muted-foreground">
                  decision: {node.gate_decision}
                </span>
              )}
            </div>
            {node.error && (
              <p className="mt-1 text-xs text-destructive">{node.error}</p>
            )}
          </div>
        </div>
      </div>

      {showManualAction && (
        <div className="mt-3 pl-7">
          <button
            type="button"
            onClick={onManualDone}
            disabled={busy}
            className="inline-flex items-center gap-1 rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground hover:bg-surface-hover disabled:opacity-50"
          >
            <Check className="size-3" aria-hidden="true" />
            {busy ? "Marking..." : "Mark done"}
          </button>
        </div>
      )}

      {showGateAction && (
        <div className="mt-3 space-y-2 pl-7">
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
    </li>
  );
}
