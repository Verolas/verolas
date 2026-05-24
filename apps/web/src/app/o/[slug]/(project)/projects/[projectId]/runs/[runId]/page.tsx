"use client";

import {
  ArrowLeft,
  Calendar,
  CheckCircle2,
  Circle,
  Clock,
  Loader2,
  Sparkles,
  User,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { type AgentRun, type AgentRunStatus, ApiError, runsApi } from "@/lib/api";

interface Props {
  params: Promise<{ slug: string; projectId: string; runId: string }>;
}

const STATUS_TONE: Record<AgentRunStatus, string> = {
  queued: "text-muted-foreground",
  running: "text-primary",
  blocked: "text-warning",
  completed: "text-success",
  failed: "text-destructive",
  cancelled: "text-muted-foreground",
};

const TIER_LABEL: Record<number, string> = {
  1: "Productivity",
  2: "Drafter",
  3: "Co-pilot",
  4: "Peer Review",
};

export default function RunViewPage({ params }: Props) {
  const [resolved, setResolved] = useState<{
    slug: string;
    projectId: string;
    runId: string;
  } | null>(null);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  useEffect(() => {
    if (!resolved) return;
    let cancelled = false;
    async function load(): Promise<void> {
      try {
        const r = await runsApi.get(resolved!.slug, resolved!.projectId, resolved!.runId);
        if (cancelled) return;
        setRun(r);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : String(err));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [resolved]);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-8 py-8">
      {resolved && (
        <Link
          href={`/o/${resolved.slug}/projects/${resolved.projectId}/runs`}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          prefetch={false}
        >
          <ArrowLeft className="size-3" aria-hidden="true" /> All runs
        </Link>
      )}

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {run && (
        <>
          <header className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="rounded border border-border bg-muted px-2 py-0.5 font-mono">
                {run.agent_id}
              </span>
              <span>Tier {run.tier}</span>
              <span>·</span>
              <span>{TIER_LABEL[run.tier]}</span>
              <span>·</span>
              <span className={STATUS_TONE[run.status]}>{run.status}</span>
            </div>
            <h1 className="text-2xl font-normal tracking-tight text-foreground">
              {run.agent_name}
            </h1>
            <p className="text-sm text-muted-foreground">{run.brief}</p>
          </header>

          <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
            <section className="rounded-md border border-border bg-surface p-5">
              <h2 className="mb-3 text-sm font-semibold text-foreground">Plan</h2>
              {run.plan.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  This agent has no pre-defined plan; it improvises step-by-step.
                </p>
              ) : (
                <ol className="space-y-2">
                  {run.plan.map((step, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm">
                      <StepIcon
                        status={index < run.current_step ? "done" : index === run.current_step ? "in_progress" : "pending"}
                        runStatus={run.status}
                      />
                      <div className="flex-1">
                        <div
                          className={
                            index < run.current_step
                              ? "text-foreground line-through opacity-70"
                              : index === run.current_step
                                ? "font-medium text-foreground"
                                : "text-muted-foreground"
                          }
                        >
                          {step.label}
                        </div>
                        {step.detail && (
                          <div className="mt-0.5 text-xs text-muted-foreground">{step.detail}</div>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              <div className="mt-4 border-t border-border pt-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Progress
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{ width: `${run.progress_percent}%` }}
                  />
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  Step {run.current_step + 1} of {Math.max(run.plan.length, 1)} ·{" "}
                  {run.progress_percent}%
                </div>
              </div>
            </section>

            <section className="space-y-4">
              <div className="rounded-md border border-border bg-surface p-5">
                <h2 className="text-sm font-semibold text-foreground">Metadata</h2>
                <dl className="mt-3 space-y-2 text-xs">
                  <Row icon={Sparkles} label="Tier" value={`T${run.tier} ${TIER_LABEL[run.tier]}`} />
                  <Row icon={User} label="Triggered by" value={run.triggered_by_user_id ?? "—"} mono />
                  <Row icon={Clock} label="Queued" value={new Date(run.queued_at).toLocaleString()} />
                  {run.started_at && (
                    <Row icon={Clock} label="Started" value={new Date(run.started_at).toLocaleString()} />
                  )}
                  {run.finished_at && (
                    <Row
                      icon={Clock}
                      label="Finished"
                      value={new Date(run.finished_at).toLocaleString()}
                    />
                  )}
                  <Row icon={Calendar} label="Trigger" value={run.trigger} />
                </dl>
              </div>

              <div className="rounded-md border border-border bg-surface p-5">
                <h2 className="text-sm font-semibold text-foreground">Result</h2>
                {Object.keys(run.result).length === 0 ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    The result payload is empty. Artefacts produced by this run will appear here.
                  </p>
                ) : (
                  <pre className="mt-2 overflow-x-auto rounded border border-border bg-muted/40 p-2 text-[11px] text-foreground">
                    {JSON.stringify(run.result, null, 2)}
                  </pre>
                )}
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function StepIcon({
  status,
  runStatus,
}: {
  status: "pending" | "in_progress" | "done";
  runStatus: AgentRunStatus;
}) {
  if (status === "done") {
    return <CheckCircle2 className="mt-0.5 size-4 text-success" aria-hidden="true" />;
  }
  if (status === "in_progress") {
    if (runStatus === "failed" || runStatus === "cancelled") {
      return <XCircle className="mt-0.5 size-4 text-destructive" aria-hidden="true" />;
    }
    return <Loader2 className="mt-0.5 size-4 animate-spin text-primary" aria-hidden="true" />;
  }
  return <Circle className="mt-0.5 size-4 text-muted-foreground" aria-hidden="true" />;
}

function Row({
  icon: Icon,
  label,
  value,
  mono,
}: {
  icon: typeof Sparkles;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="size-3" aria-hidden="true" />
        {label}
      </dt>
      <dd className={mono ? "max-w-[18ch] truncate font-mono text-foreground" : "text-foreground"}>
        {value}
      </dd>
    </div>
  );
}
