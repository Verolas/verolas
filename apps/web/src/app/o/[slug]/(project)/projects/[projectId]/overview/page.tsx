"use client";

import {
  Activity,
  ClipboardCheck,
  Cog,
  Copy,
  FileText,
  GitBranch,
  History,
  Loader2,
  MapPin,
  Play,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { RunLauncher } from "@/components/run-launcher";
import {
  type AgentRun,
  type AgentRunStatus,
  ApiError,
  orgsApi,
  type Project,
  runsApi,
} from "@/lib/api";

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

export default function ProjectOverviewPage({ params }: Props) {
  const [resolved, setResolved] = useState<{ slug: string; projectId: string } | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  const refresh = useCallback(async (): Promise<void> => {
    if (!resolved) return;
    try {
      const [list, runList] = await Promise.all([
        orgsApi.listProjects(resolved.slug),
        runsApi.list(resolved.slug, resolved.projectId),
      ]);
      const match = list.find((p) => p.id === resolved.projectId) ?? null;
      setProject(match);
      setRuns(runList);
      if (!match) setError("Project not found.");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }, [resolved]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const active = (runs ?? []).filter(
    (r) => r.status === "queued" || r.status === "running" || r.status === "blocked",
  );
  const recent = (runs ?? [])
    .filter((r) => r.status === "completed" || r.status === "failed" || r.status === "cancelled")
    .slice(0, 5);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-8 py-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-normal tracking-tight text-foreground">
          {project?.name ?? "Loading..."}
        </h1>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="font-mono text-xs">
            verolas.com/o/{resolved?.slug ?? "..."}/projects/
            {resolved?.projectId.slice(0, 12) ?? "..."}
          </span>
          <button
            type="button"
            className="inline-flex h-6 items-center gap-1 rounded border border-border bg-surface px-2 text-[11px] text-muted-foreground hover:bg-surface-hover hover:text-foreground"
            onClick={() => {
              const url = `${window.location.origin}/o/${resolved?.slug}/projects/${resolved?.projectId}`;
              void navigator.clipboard?.writeText(url);
            }}
          >
            <Copy className="size-3" aria-hidden="true" />
            Copy
          </button>
        </div>
      </header>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {resolved && (
        <RunLauncher
          orgSlug={resolved.slug}
          projectId={resolved.projectId}
          onRunCreated={() => void refresh()}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <section className="rounded-md border border-border bg-surface p-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Play className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-foreground">
                Active runs <span className="text-muted-foreground">({active.length})</span>
              </h2>
            </div>
            {resolved && (
              <Link
                href={`/o/${resolved.slug}/projects/${resolved.projectId}/runs`}
                className="text-xs text-primary hover:underline"
                prefetch={false}
              >
                View all →
              </Link>
            )}
          </div>
          {runs === null ? (
            <div className="py-6 text-center text-sm text-muted-foreground">Loading runs...</div>
          ) : active.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No runs in flight. Launch one above.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {active.map((run) => (
                <li key={run.id}>
                  {resolved && (
                    <Link
                      href={`/o/${resolved.slug}/projects/${resolved.projectId}/runs/${run.id}`}
                      className="flex items-start gap-3 py-3 hover:bg-surface-hover"
                      prefetch={false}
                    >
                      <Loader2
                        className={`mt-0.5 size-4 animate-spin ${STATUS_TONE[run.status]}`}
                        aria-hidden="true"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-foreground">
                          {run.agent_name}
                          <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                            T{run.tier}
                          </span>
                        </div>
                        <div className="mt-0.5 truncate text-xs text-muted-foreground">
                          {run.brief}
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                          <span>
                            Step {run.current_step + 1}/{Math.max(run.plan.length, 1)}
                          </span>
                          <span>·</span>
                          <span>{run.progress_percent}%</span>
                          <span>·</span>
                          <span className={STATUS_TONE[run.status]}>{run.status}</span>
                        </div>
                      </div>
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-md border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold text-foreground">Health</h2>
          <ul className="mt-3 space-y-3 text-sm">
            <HealthRow icon={Activity} label="Status" value="Healthy" tone="success" />
            <HealthRow icon={ClipboardCheck} label="Reviewer status" value="1 pending" />
            <HealthRow icon={GitBranch} label="Active workspace" value="main" />
            <HealthRow icon={Cog} label="Compute tier" value="Starter (nano)" />
            <HealthRow icon={FileText} label="Source repo" value="Not connected" tone="muted" />
          </ul>
        </section>
      </div>

      <section className="rounded-md border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">
          Recent runs
          <span className="ml-2 font-normal text-muted-foreground">last finished</span>
        </h2>
        {recent.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Completed runs land here with the producing agent, brief, and result summary.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {recent.map((run) => (
              <li key={run.id} className="flex items-start gap-3 py-3">
                <History className="mt-0.5 size-3.5 text-muted-foreground" aria-hidden="true" />
                <div className="flex-1">
                  <div className="text-sm text-foreground">
                    <span className="font-medium">{run.agent_name}</span>{" "}
                    <span className={STATUS_TONE[run.status]}>{run.status}</span>
                  </div>
                  <div className="mt-0.5 truncate text-xs text-muted-foreground">{run.brief}</div>
                  <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                    {new Date(run.updated_at).toLocaleString()}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-md border border-border bg-surface p-5">
        <div className="flex items-center gap-2">
          <MapPin className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-foreground">Primary region</h2>
        </div>
        <p className="mt-1 text-sm text-foreground-light">EU Central (Frankfurt)</p>
        <div className="mt-3 grid grid-cols-3 gap-3 text-[11px] text-muted-foreground">
          <span>CPU 3%</span>
          <span>Disk 4%</span>
          <span>RAM 46%</span>
        </div>
      </section>
    </div>
  );
}

function HealthRow({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  tone?: "muted" | "success";
}) {
  return (
    <li className="flex items-start justify-between gap-3">
      <span className="flex items-center gap-2 text-muted-foreground">
        <Icon className="size-3.5" aria-hidden="true" />
        {label}
      </span>
      <span
        className={
          tone === "muted"
            ? "text-muted-foreground"
            : tone === "success"
              ? "text-success"
              : "text-foreground"
        }
      >
        {value}
      </span>
    </li>
  );
}
