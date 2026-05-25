"use client";

import { Globe2, Play, Workflow as WorkflowIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type WorkflowRun,
  type WorkflowTemplate,
  workflowsApi,
} from "@/lib/api";

interface Props {
  params: Promise<{ slug: string; projectId: string }>;
}

const RUN_STATUS_TONE: Record<WorkflowRun["status"], string> = {
  pending: "border-border text-muted-foreground",
  running: "border-brand-200 text-brand-700",
  paused: "border-discipline-water/40 text-discipline-water",
  completed: "border-emerald-300/40 text-emerald-700 dark:text-emerald-400",
  failed: "border-destructive/30 text-destructive",
  cancelled: "border-border text-muted-foreground",
};

export default function WorkflowsPage({ params }: Props) {
  const [resolved, setResolved] = useState<{ slug: string; projectId: string } | null>(
    null,
  );
  const [templates, setTemplates] = useState<WorkflowTemplate[] | null>(null);
  const [runs, setRuns] = useState<WorkflowRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyTemplateSlug, setBusyTemplateSlug] = useState<string | null>(null);

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  const reload = useCallback(async () => {
    if (!resolved) return;
    try {
      const [tpls, runList] = await Promise.all([
        workflowsApi.listTemplates(resolved.slug),
        workflowsApi.listRuns(resolved.slug, resolved.projectId),
      ]);
      setTemplates(tpls);
      setRuns(runList);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }, [resolved]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const handleStart = useCallback(
    async (templateSlug: string) => {
      if (!resolved) return;
      setBusyTemplateSlug(templateSlug);
      setError(null);
      try {
        const run = await workflowsApi.createRun(
          resolved.slug,
          resolved.projectId,
          templateSlug,
        );
        window.location.href = `/o/${resolved.slug}/projects/${resolved.projectId}/workflows/runs/${run.id}`;
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
        setBusyTemplateSlug(null);
      }
    },
    [resolved],
  );

  const groupedTemplates = useMemo(() => {
    const groups = new Map<string, WorkflowTemplate[]>();
    (templates ?? []).forEach((t) => {
      const key = t.jurisdiction ?? "Universal";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(t);
    });
    return groups;
  }, [templates]);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-8 px-8 py-8">
      <header>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Workflows</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a template for your jurisdiction or your firm. Verolas runs the engineering
          sequence; you approve gates and review artifacts. Output is a stamped, signed,
          submission-ready deliverable bundle.
        </p>
      </header>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Templates
        </h2>
        {templates === null ? (
          <div className="rounded-md border border-border bg-surface p-10 text-center text-sm text-muted-foreground">
            Loading templates...
          </div>
        ) : templates.length === 0 ? (
          <div className="rounded-md border border-border bg-surface p-10 text-center text-sm text-muted-foreground">
            No templates available yet.
          </div>
        ) : (
          <div className="space-y-6">
            {Array.from(groupedTemplates.entries()).map(([group, items]) => (
              <div key={group} className="space-y-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  {group}
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {items.map((tpl) => (
                    <article
                      key={tpl.id}
                      className="group flex flex-col gap-3 rounded-md border border-border bg-surface p-4"
                    >
                      <div className="flex items-start gap-2">
                        <div className="grid size-8 place-items-center rounded bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground">
                          <WorkflowIcon className="size-4" aria-hidden="true" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-foreground">
                            {tpl.name}
                          </div>
                          <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                            {tpl.is_global && (
                              <span className="inline-flex items-center gap-1">
                                <Globe2 className="size-3" aria-hidden="true" />
                                Verolas
                              </span>
                            )}
                            <span>v{tpl.active_version}</span>
                            <span>·</span>
                            <span>{tpl.node_count} nodes</span>
                          </div>
                        </div>
                      </div>
                      {tpl.description && (
                        <p className="text-xs text-foreground-light">{tpl.description}</p>
                      )}
                      <button
                        type="button"
                        onClick={() => void handleStart(tpl.slug)}
                        disabled={busyTemplateSlug !== null}
                        className="mt-auto inline-flex items-center justify-center gap-2 rounded border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Play className="size-3" aria-hidden="true" />
                        {busyTemplateSlug === tpl.slug ? "Starting..." : "Start run"}
                      </button>
                    </article>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Recent runs
        </h2>
        {runs === null ? (
          <div className="rounded-md border border-border bg-surface p-10 text-center text-sm text-muted-foreground">
            Loading runs...
          </div>
        ) : runs.length === 0 ? (
          <div className="rounded-md border border-border bg-surface p-10 text-center text-sm text-muted-foreground">
            No runs yet on this project. Start one above.
          </div>
        ) : (
          <div className="overflow-hidden rounded-md border border-border bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/40 text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-medium">Template</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Started</th>
                  <th className="px-4 py-2 font-medium">Nodes</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        href={
                          resolved
                            ? `/o/${resolved.slug}/projects/${resolved.projectId}/workflows/runs/${run.id}`
                            : "#"
                        }
                        className="font-medium text-foreground hover:underline"
                        prefetch={false}
                      >
                        {run.template_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${RUN_STATUS_TONE[run.status]}`}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {run.started_at
                        ? new Date(run.started_at).toLocaleString()
                        : "queued"}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {run.nodes.filter((n) => n.status === "completed").length} /{" "}
                      {run.nodes.length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
