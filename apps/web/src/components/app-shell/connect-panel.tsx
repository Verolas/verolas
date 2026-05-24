"use client";

import { Copy, Cable } from "lucide-react";
import { useState } from "react";

const TABS = ["CLI", "API", "Python SDK", "Webhooks"] as const;

export function ConnectPanelBody({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("CLI");
  const baseUrl = "https://api.verolas.com";
  const snippet = snippetFor(tab, projectId, baseUrl);
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-md border border-border bg-muted/30 p-3">
        <Cable className="mt-0.5 size-4 text-primary" aria-hidden="true" />
        <p className="text-xs text-foreground-light">
          Drive this project from your tools of choice. Every Connect option is read-only by
          default; uploads and reviewer-finding writes require an explicit scope.
        </p>
      </div>
      <div className="segmented w-full">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            aria-pressed={tab === t}
            onClick={() => setTab(t)}
            className="flex-1"
          >
            {t}
          </button>
        ))}
      </div>
      <CodeBlock code={snippet} />
      <div>
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          Project reference
        </div>
        <div className="mt-1 flex items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 py-2">
          <span className="truncate font-mono text-xs text-foreground">{projectId}</span>
          <button
            type="button"
            aria-label="Copy project id"
            className="inline-flex items-center gap-1 rounded text-xs text-muted-foreground hover:text-foreground"
            onClick={() => navigator.clipboard?.writeText(projectId)}
          >
            <Copy className="size-3" aria-hidden="true" />
            Copy
          </button>
        </div>
      </div>
    </div>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <pre className="overflow-x-auto rounded-md border border-border bg-muted/40 px-3 py-2.5 font-mono text-xs leading-relaxed text-foreground">
      {code}
    </pre>
  );
}

function snippetFor(tab: (typeof TABS)[number], projectId: string, base: string): string {
  switch (tab) {
    case "CLI":
      return [
        "$ verolas login",
        `$ verolas project use ${projectId}`,
        "$ verolas drawings pull",
      ].join("\n");
    case "API":
      return [
        `curl ${base}/v1/projects/${projectId} \\`,
        '  -H "Authorization: Bearer $TOKEN"',
      ].join("\n");
    case "Python SDK":
      return [
        "from verolas import Verolas",
        "",
        `client = Verolas(token="VEROLAS_TOKEN")`,
        `project = client.projects.get("${projectId}")`,
        "print(project.name, project.discipline)",
      ].join("\n");
    case "Webhooks":
      return [
        "POST https://yourapp/webhook",
        "Content-Type: application/json",
        "Verolas-Signature: t=...,v1=...",
        "",
        '{"event": "reviewer.finding.created", "project_id": "..."}',
      ].join("\n");
  }
}
