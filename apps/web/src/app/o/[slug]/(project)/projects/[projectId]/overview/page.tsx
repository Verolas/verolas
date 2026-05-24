"use client";

import {
  Activity,
  ClipboardCheck,
  Cog,
  Copy,
  FileText,
  GitBranch,
  History,
  MapPin,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError, orgsApi, type Project } from "@/lib/api";

interface Props {
  params: Promise<{ slug: string; projectId: string }>;
}

export default function ProjectOverviewPage({ params }: Props) {
  const [resolved, setResolved] = useState<{ slug: string; projectId: string } | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  useEffect(() => {
    if (!resolved) return;
    let cancelled = false;
    async function load(): Promise<void> {
      try {
        const list = await orgsApi.listProjects(resolved!.slug);
        if (cancelled) return;
        const match = list.find((p) => p.id === resolved!.projectId) ?? null;
        setProject(match);
        if (!match) setError("Project not found.");
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
    <div className="mx-auto w-full max-w-6xl px-8 py-8 space-y-8">
      <header className="space-y-3">
        <h1 className="text-3xl font-normal tracking-tight text-foreground">
          {project?.name ?? "Loading..."}
        </h1>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="font-mono text-xs">
            verolas.com/o/{resolved?.slug ?? "..."}/projects/{resolved?.projectId.slice(0, 12) ?? "..."}
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

      <div className="grid gap-4 lg:grid-cols-[2fr_3fr]">
        <div className="space-y-3">
          <Stat icon={Activity} label="Status" value="Healthy" valueTone="success" />
          <Stat icon={Cog} label="Compute tier" value="Starter" badge="nano" />
          <Stat
            icon={GitBranch}
            label="Source repo"
            value={project ? "No repository connected" : "—"}
            valueTone="muted"
          />
          <Stat icon={FileText} label="Active workspace" value="main" />
          <Stat icon={History} label="Last reviewer pass" value="No runs yet" valueTone="muted" />
          <Stat icon={ClipboardCheck} label="Last backup" value="No snapshots" valueTone="muted" />
        </div>
        <div className="relative overflow-hidden rounded-md border border-border bg-surface p-4">
          <div className="grid h-full place-items-center">
            <div className="rounded-md border border-border bg-background p-3 text-center shadow-xs">
              <div className="flex items-center gap-2">
                <MapPin className="size-4 text-primary" aria-hidden="true" />
                <span className="font-medium text-foreground">Primary region</span>
              </div>
              <div className="mt-1 text-sm text-foreground-light">EU Central (Frankfurt)</div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-muted-foreground">
                <span>CPU 3%</span>
                <span>Disk 4%</span>
                <span>RAM 46%</span>
              </div>
            </div>
          </div>
          <div
            className="absolute inset-0 -z-0 opacity-30"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, var(--color-border) 1px, transparent 0)",
              backgroundSize: "10px 10px",
            }}
            aria-hidden="true"
          />
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-medium text-foreground">
          0 Total events
          <span className="ml-2 font-normal text-sm text-muted-foreground">
            in the last 60 minutes
          </span>
        </h2>
        <div className="grid gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-4">
          {[
            { label: "Reviewer findings", value: 0 },
            { label: "Drawing uploads", value: 0 },
            { label: "Calc runs", value: 0 },
            { label: "Document edits", value: 0 },
          ].map((card) => (
            <div key={card.label} className="bg-surface px-4 py-3">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {card.label}
              </div>
              <div className="mt-1 text-2xl font-medium text-foreground">{card.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  valueTone,
  badge,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  valueTone?: "muted" | "success";
  badge?: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-border bg-surface px-4 py-3">
      <span className="grid size-8 place-items-center rounded-md border border-border bg-muted text-muted-foreground">
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div
          className={`mt-0.5 truncate text-sm ${
            valueTone === "muted"
              ? "text-muted-foreground"
              : valueTone === "success"
                ? "text-success"
                : "text-foreground"
          }`}
        >
          {value}
        </div>
      </div>
      {badge && <span className="badge">{badge}</span>}
    </div>
  );
}
