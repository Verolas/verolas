"use client";

import { ChevronDown } from "lucide-react";

const METRICS = [
  { name: "Project storage", used: 0.149, total: 1, unit: "GB" },
  { name: "AI reviewer runs", used: 0.037, total: 0.5, unit: "k runs" },
  { name: "Document pages OCR'd", used: 0.008, total: 5, unit: "k pages" },
  { name: "Cached AI responses", used: 0.002, total: 5, unit: "k calls" },
  { name: "Active users (MAU)", used: 0, total: 50, unit: "" },
  { name: "Reviewer-hours", used: 0, total: 25, unit: "h" },
  { name: "Concurrent jobs", used: 0, total: 5, unit: "" },
  { name: "Audit chain entries", used: 0, total: 100, unit: "k" },
  { name: "Webhook deliveries", used: 0, total: 50, unit: "k" },
  { name: "Outbound model API calls", used: 0, total: 0, unit: "", unavailable: true },
] as const;

export default function UsagePage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <h1 className="text-2xl font-normal tracking-tight text-foreground">Usage</h1>

      <div className="flex flex-wrap items-center gap-3">
        <Dropdown label="Current billing cycle" />
        <Dropdown label="All projects" />
        <div className="ml-auto flex items-center gap-3 text-xs">
          <span className="text-foreground-light">
            Organization is on the{" "}
            <button
              type="button"
              className="font-semibold text-primary underline-offset-4 hover:underline"
            >
              Free Plan
            </button>
          </span>
          <span className="font-mono text-muted-foreground">15 May 2026 - 15 Jun 2026</span>
        </div>
      </div>

      <div className="grid gap-8 sm:grid-cols-[1fr_2fr]">
        <aside className="rounded-md border border-border bg-surface p-4">
          <h2 className="text-sm font-medium text-foreground">Usage Summary</h2>
          <p className="mt-2 text-xs text-foreground-light">
            Your plan includes a limited amount of usage. If exceeded, you may experience
            restrictions, as you are currently not billed for overages. It may take up to one
            hour to refresh.
          </p>
          <div className="mt-4 text-[11px] uppercase tracking-wider text-muted-foreground">
            More information
          </div>
          <ul className="mt-1 space-y-1 text-xs">
            <li>
              <button type="button" className="text-primary hover:underline">
                How billing works
              </button>
            </li>
            <li>
              <button type="button" className="text-primary hover:underline">
                Verolas plans
              </button>
            </li>
          </ul>
        </aside>

        <div>
          <p className="mb-4 text-sm text-foreground-light">
            You have not exceeded your{" "}
            <span className="font-semibold text-foreground">Free Plan</span> quota in this
            billing cycle.
          </p>
          <div className="grid gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-2">
            {METRICS.map((metric) => (
              <Metric key={metric.name} metric={metric} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Dropdown({ label }: { label: string }) {
  return (
    <button
      type="button"
      className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-foreground hover:bg-surface-hover"
    >
      {label}
      <ChevronDown className="size-3.5 text-muted-foreground" aria-hidden="true" />
    </button>
  );
}

function Metric({
  metric,
}: {
  metric: { name: string; used: number; total: number; unit: string; unavailable?: boolean };
}) {
  const percent = metric.total > 0 ? Math.min(100, Math.round((metric.used / metric.total) * 100)) : 0;
  return (
    <div className="flex items-center justify-between gap-3 bg-surface px-4 py-3.5">
      <div>
        <div className="text-sm font-medium text-foreground">{metric.name}</div>
        {metric.unavailable ? (
          <div className="mt-0.5 text-xs text-muted-foreground">Unavailable in plan</div>
        ) : (
          <div className="mt-0.5 font-mono text-xs text-muted-foreground">
            {metric.used} / {metric.total} {metric.unit} ({percent}%)
          </div>
        )}
      </div>
      <CircleProgress percent={metric.unavailable ? 0 : percent} />
    </div>
  );
}

function CircleProgress({ percent }: { percent: number }) {
  const radius = 12;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;
  return (
    <svg viewBox="0 0 32 32" className="size-7 -rotate-90" aria-hidden="true">
      <circle cx="16" cy="16" r={radius} stroke="var(--color-border)" strokeWidth="3" fill="none" />
      <circle
        cx="16"
        cy="16"
        r={radius}
        stroke="var(--color-primary)"
        strokeWidth="3"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
