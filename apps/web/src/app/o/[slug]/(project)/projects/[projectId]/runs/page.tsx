"use client";

import { Loader2, Play } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { RunLauncher } from "@/components/run-launcher";
import { type AgentRun, type AgentRunStatus, ApiError, runsApi } from "@/lib/api";

interface Props {
  params: Promise<{ slug: string; projectId: string }>;
}

const STATUS_TONE: Record<AgentRunStatus, string> = {
  queued: "text-muted-foreground",
  running: "text-primary",
  blocked: "text-warning",
  completed: "text-success",
  failed: "text-destructive",
  cancelled: "text-muted-foreground",
};

type Filter = "all" | "active" | "history";

export default function RunsPage({ params }: Props) {
  const [resolved, setResolved] = useState<{ slug: string; projectId: string } | null>(null);
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  const refresh = useCallback(async (): Promise<void> => {
    if (!resolved) return;
    setError(null);
    try {
      const list = await runsApi.list(resolved.slug, resolved.projectId);
      setRuns(list);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }, [resolved]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const filtered =
    filter === "all"
      ? runs ?? []
      : filter === "active"
        ? (runs ?? []).filter(
            (r) => r.status === "queued" || r.status === "running" || r.status === "blocked",
          )
        : (runs ?? []).filter(
            (r) => r.status === "completed" || r.status === "failed" || r.status === "cancelled",
          );

  const counts = {
    all: runs?.length ?? 0,
    active: (runs ?? []).filter(
      (r) => r.status === "queued" || r.status === "running" || r.status === "blocked",
    ).length,
    history: (runs ?? []).filter(
      (r) => r.status === "completed" || r.status === "failed" || r.status === "cancelled",
    ).length,
  };

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-8 py-8">
      <header>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Runs</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Every agent run on this project. Click a row to inspect the plan, citations, and
          produced artefacts.
        </p>
      </header>

      {resolved && (
        <RunLauncher
          orgSlug={resolved.slug}
          projectId={resolved.projectId}
          onRunCreated={() => void refresh()}
        />
      )}

      <div className="flex items-center gap-3">
        <div className="segmented">
          {(["all", "active", "history"] as Filter[]).map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
              className="capitalize"
            >
              {f}{" "}
              <span className="ml-1 font-mono text-[10px] opacity-70">{counts[f]}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-md border border-border bg-surface">
        {runs === null ? (
          <div className="py-10 text-center text-sm text-muted-foreground">Loading runs...</div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center">
            <Play className="mx-auto size-5 text-muted-foreground" aria-hidden="true" />
            <div className="mt-2 text-sm font-medium text-foreground">No runs yet</div>
            <p className="mt-1 text-sm text-muted-foreground">
              Launch an agent above to create the first run.
            </p>
          </div>
        ) : (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2.5">Agent</th>
                <th className="px-4 py-2.5">Brief</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Progress</th>
                <th className="px-4 py-2.5">Updated</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((run, index) => (
                <tr
                  key={run.id}
                  className={`group transition-colors hover:bg-surface-hover ${
                    index === filtered.length - 1 ? "" : "border-b border-border"
                  }`}
                >
                  <td className="px-4 py-3">
                    {resolved && (
                      <Link
                        href={`/o/${resolved.slug}/projects/${resolved.projectId}/runs/${run.id}`}
                        className="flex items-center gap-2 font-medium text-foreground hover:text-primary"
                        prefetch={false}
                      >
                        {run.status === "running" && (
                          <Loader2 className="size-3.5 animate-spin text-primary" aria-hidden="true" />
                        )}
                        {run.agent_name}
                        <span className="font-mono text-[10px] text-muted-foreground">
                          T{run.tier}
                        </span>
                      </Link>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="max-w-[40ch] truncate text-foreground">{run.brief}</div>
                  </td>
                  <td className={`px-4 py-3 capitalize ${STATUS_TONE[run.status]}`}>
                    {run.status}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-foreground">
                    {run.progress_percent}% ({run.current_step + 1}/{Math.max(run.plan.length, 1)})
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {new Date(run.updated_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
