"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { type AgentSummary, ApiError, orgsApi } from "@/lib/api";

interface Props {
  params: Promise<{ slug: string; projectId: string }>;
}

const TIER_LABEL: Record<number, string> = {
  1: "Productivity",
  2: "Drafter",
  3: "Co-pilot",
  4: "Peer Review",
};

const TIER_TONE: Record<number, string> = {
  1: "border-brand-200 text-brand-700",
  2: "border-discipline-water/40 text-discipline-water",
  3: "border-discipline-structural/40 text-discipline-structural",
  4: "border-discipline-review/40 text-discipline-review",
};

export default function WorkflowsPage({ params }: Props) {
  const [resolved, setResolved] = useState<{ slug: string; projectId: string } | null>(null);
  const [agents, setAgents] = useState<AgentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  useEffect(() => {
    if (!resolved) return;
    let cancelled = false;
    void (async () => {
      try {
        const list = await orgsApi.listAgents(resolved.slug);
        if (cancelled) return;
        setAgents(list);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [resolved]);

  const grouped: Record<number, AgentSummary[]> = {};
  (agents ?? []).forEach((a) => {
    const key = a.tier;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(a);
  });

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-8 py-8">
      <header>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Workflows</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          End-to-end engineering sequences and individual agents available on this project.
          Tier 3 co-pilots, Tier 2 drafters, Tier 1 productivity, and the Tier 4 peer-review
          loop are grouped below with run counts and success rates.
        </p>
      </header>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {agents === null && (
        <div className="rounded-md border border-border bg-surface p-10 text-center text-sm text-muted-foreground">
          Loading agents...
        </div>
      )}

      {[3, 2, 1, 4].map((tier) =>
        grouped[tier] && grouped[tier]!.length > 0 ? (
          <section key={tier}>
            <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Tier {tier} · {TIER_LABEL[tier]}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {grouped[tier]!.map((agent) => (
                <Link
                  key={agent.id}
                  href={
                    resolved
                      ? `/o/${resolved.slug}/projects/${resolved.projectId}/runs?agent=${agent.id}`
                      : "#"
                  }
                  className="group flex flex-col gap-3 rounded-md border border-border bg-surface p-4 hover:shadow-sm"
                  prefetch={false}
                >
                  <div className="flex items-start gap-2">
                    <div className="grid size-8 place-items-center rounded bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground">
                      <Sparkles className="size-4" aria-hidden="true" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-foreground">
                        {agent.name}
                      </div>
                      <div className={`mt-1 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${TIER_TONE[tier]}`}>
                        T{tier}
                      </div>
                    </div>
                  </div>
                  <p className="text-xs text-foreground-light">{agent.blurb}</p>
                  {agent.region_tags.length > 0 && (
                    <div className="mt-auto flex flex-wrap gap-1 text-[10px] font-mono text-muted-foreground">
                      {agent.region_tags.slice(0, 5).map((r) => (
                        <span
                          key={r}
                          className="rounded border border-border bg-muted px-1.5 py-0.5 uppercase"
                        >
                          {r}
                        </span>
                      ))}
                      {agent.region_tags.length > 5 && (
                        <span className="text-muted-foreground">+{agent.region_tags.length - 5}</span>
                      )}
                    </div>
                  )}
                </Link>
              ))}
            </div>
          </section>
        ) : null,
      )}
    </div>
  );
}
