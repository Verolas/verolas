"use client";

import { ArrowRight, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import {
  ApiError,
  type AgentSummary,
  orgsApi,
  runsApi,
} from "@/lib/api";

interface Props {
  orgSlug: string;
  projectId: string;
  onRunCreated?: () => void;
}

const TIER_LABEL: Record<number, string> = {
  1: "Productivity",
  2: "Drafter",
  3: "Co-pilot",
  4: "Peer Review",
};

export function RunLauncher({ orgSlug, projectId, onRunCreated }: Props) {
  const [agents, setAgents] = useState<AgentSummary[] | null>(null);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [brief, setBrief] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await orgsApi.listAgents(orgSlug);
        if (cancelled) return;
        setAgents(list);
        setAgentId(list[0]?.id ?? null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orgSlug]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!agentId || !brief.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await runsApi.create(orgSlug, projectId, agentId, brief.trim());
      setBrief("");
      onRunCreated?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-5 shadow-xs">
      <div className="flex items-center gap-2 text-sm">
        <Sparkles className="size-4 text-primary" aria-hidden="true" />
        <span className="font-medium text-foreground">What would you like Verolas to do?</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Pick an agent and describe the work. The run lands in the Runs dashboard and audit trail.
      </p>
      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">Agent:</span>
          {agents === null && <span className="text-muted-foreground">loading…</span>}
          {agents !== null && agents.length === 0 && (
            <span className="text-muted-foreground">No agents available.</span>
          )}
          {agents?.map((a) => {
            const active = a.id === agentId;
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => setAgentId(a.id)}
                title={a.blurb}
                aria-pressed={active}
                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 ${
                  active
                    ? "border-primary bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground"
                    : "border-border text-foreground hover:bg-surface-hover"
                }`}
              >
                <span className="font-medium">{a.name}</span>
                <span className="text-[10px] uppercase text-muted-foreground">
                  T{a.tier}
                </span>
              </button>
            );
          })}
        </div>
        <div className="relative">
          <input
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder="e.g. Re-run the punching-shear check on calc package S-204"
            className="h-11 w-full rounded-md border border-input bg-surface pl-3 pr-12 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30"
            aria-label="Brief"
          />
          <button
            type="submit"
            disabled={submitting || !agentId || !brief.trim()}
            aria-label="Start run"
            className="absolute right-1.5 top-1.5 grid size-8 place-items-center rounded-md bg-primary text-primary-foreground hover:bg-primary-hover disabled:opacity-50"
          >
            <ArrowRight className="size-4" aria-hidden="true" />
          </button>
        </div>
        {error && (
          <p role="alert" className="text-xs text-destructive">
            {error}
          </p>
        )}
        {agentId && agents && (
          <p className="text-[11px] text-muted-foreground">
            Tier {TIER_LABEL[agents.find((a) => a.id === agentId)?.tier ?? 1] ?? ""} ·{" "}
            {agents.find((a) => a.id === agentId)?.blurb}
          </p>
        )}
      </form>
    </div>
  );
}
