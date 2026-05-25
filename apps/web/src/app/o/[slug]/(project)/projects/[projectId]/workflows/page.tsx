"use client";

import {
  FilePlus2,
  FolderClosed,
  Loader2,
  Workflow as WorkflowIcon,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type WorkflowDocument,
  type WorkflowRun,
  type WorkflowTemplate,
  workflowDocumentsApi,
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
  const [documents, setDocuments] = useState<WorkflowDocument[] | null>(null);
  const [runs, setRuns] = useState<WorkflowRun[] | null>(null);
  const [templates, setTemplates] = useState<WorkflowTemplate[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState<"blank" | "template" | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  const reload = useCallback(async () => {
    if (!resolved) return;
    try {
      const [docs, runList, tpls] = await Promise.all([
        workflowDocumentsApi.list(resolved.slug, resolved.projectId),
        workflowsApi.listRuns(resolved.slug, resolved.projectId),
        workflowsApi.listTemplates(resolved.slug),
      ]);
      setDocuments(docs);
      setRuns(runList);
      setTemplates(tpls);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }, [resolved]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const groupedDocs = useMemo(() => {
    const groups = new Map<string, WorkflowDocument[]>();
    (documents ?? []).forEach((doc) => {
      const key = doc.folder || "/";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(doc);
    });
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [documents]);

  const handleCreate = useCallback(
    async (input: {
      name: string;
      folder: string;
      template_slug?: string | null;
    }) => {
      if (!resolved) return;
      setBusy(true);
      setError(null);
      try {
        const doc = await workflowDocumentsApi.create(
          resolved.slug,
          resolved.projectId,
          {
            name: input.name,
            folder: input.folder || "/",
            template_slug: input.template_slug ?? null,
          },
        );
        window.location.href = `/o/${resolved.slug}/projects/${resolved.projectId}/workflows/documents/${doc.id}`;
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
        setBusy(false);
      }
    },
    [resolved],
  );

  return (
    <div className="mx-auto w-full max-w-6xl space-y-8 px-8 py-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-normal tracking-tight text-foreground">
            Workflows
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Each workflow document is a graph of components your team executes on this
            project. Pick a template for your jurisdiction or start with a blank canvas.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setCreateOpen("blank")}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-surface-hover disabled:opacity-50"
          >
            <FilePlus2 className="size-3.5" aria-hidden="true" />
            Create blank
          </button>
          <button
            type="button"
            onClick={() => setCreateOpen("template")}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded border border-brand-300 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-100 disabled:opacity-50 dark:bg-accent dark:text-accent-foreground"
          >
            <WorkflowIcon className="size-3.5" aria-hidden="true" />
            From template
          </button>
        </div>
      </header>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Documents
        </h2>
        {documents === null ? (
          <div className="rounded-md border border-border bg-surface p-10 text-center text-sm text-muted-foreground">
            Loading workflows...
          </div>
        ) : documents.length === 0 ? (
          <div className="rounded-md border border-dashed border-border bg-surface p-10 text-center">
            <p className="text-sm text-muted-foreground">
              No workflows yet on this project.
            </p>
            <div className="mt-4 flex justify-center gap-2">
              <button
                type="button"
                onClick={() => setCreateOpen("blank")}
                className="inline-flex items-center gap-1.5 rounded border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-surface-hover"
              >
                <FilePlus2 className="size-3.5" aria-hidden="true" />
                Create blank workflow
              </button>
              <button
                type="button"
                onClick={() => setCreateOpen("template")}
                className="inline-flex items-center gap-1.5 rounded border border-brand-300 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-100 dark:bg-accent dark:text-accent-foreground"
              >
                <WorkflowIcon className="size-3.5" aria-hidden="true" />
                Start from template
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            {groupedDocs.map(([folder, docs]) => (
              <div key={folder} className="space-y-2">
                <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
                  <FolderClosed className="size-3" aria-hidden="true" />
                  {folder === "/" ? "Root" : folder}
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {docs.map((doc) => (
                    <Link
                      key={doc.id}
                      href={
                        resolved
                          ? `/o/${resolved.slug}/projects/${resolved.projectId}/workflows/documents/${doc.id}`
                          : "#"
                      }
                      prefetch={false}
                      className="group flex flex-col gap-3 rounded-md border border-border bg-surface p-4 hover:shadow-sm"
                    >
                      <div className="flex items-start gap-2">
                        <div className="grid size-8 place-items-center rounded bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground">
                          <WorkflowIcon className="size-4" aria-hidden="true" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-foreground">
                            {doc.name}
                          </div>
                          <div className="mt-0.5 text-[10px] text-muted-foreground">
                            {doc.node_count} nodes
                            {doc.source_template_id ? " · from template" : " · blank"}
                          </div>
                        </div>
                      </div>
                      {doc.description && (
                        <p className="text-xs text-foreground-light line-clamp-2">
                          {doc.description}
                        </p>
                      )}
                    </Link>
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
            No runs yet on this project.
          </div>
        ) : (
          <div className="overflow-hidden rounded-md border border-border bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/40 text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-medium">Workflow</th>
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
                        {run.template_name ?? run.template_slug ?? "Run"}
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

      {createOpen && (
        <CreateDocumentDialog
          kind={createOpen}
          templates={templates ?? []}
          busy={busy}
          onClose={() => setCreateOpen(null)}
          onSubmit={(input) => handleCreate(input)}
        />
      )}
    </div>
  );
}

function CreateDocumentDialog({
  kind,
  templates,
  busy,
  onClose,
  onSubmit,
}: {
  kind: "blank" | "template";
  templates: WorkflowTemplate[];
  busy: boolean;
  onClose: () => void;
  onSubmit: (input: {
    name: string;
    folder: string;
    template_slug?: string | null;
  }) => void;
}) {
  const [name, setName] = useState("");
  const [folder, setFolder] = useState("/");
  const [templateSlug, setTemplateSlug] = useState<string>(
    templates[0]?.slug ?? "",
  );

  const canSubmit =
    name.trim().length > 0 && (kind === "blank" || templateSlug.length > 0);

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-40 flex items-center justify-center px-4"
    >
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-foreground/40"
      />
      <div className="relative w-full max-w-md rounded-lg border border-border bg-background p-5 shadow-lg">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-base font-medium text-foreground">
            {kind === "blank" ? "Create blank workflow" : "Workflow from template"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-surface-hover"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!canSubmit) return;
            onSubmit({
              name: name.trim(),
              folder: folder.trim() || "/",
              template_slug: kind === "template" ? templateSlug : null,
            });
          }}
          className="mt-4 space-y-3"
        >
          <label className="block text-xs">
            <span className="text-foreground">Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="DE Statik Wohngebäude"
              className="mt-1 w-full rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:border-brand-300 focus:outline-none"
            />
          </label>
          <label className="block text-xs">
            <span className="text-foreground">Folder</span>
            <input
              type="text"
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              placeholder="/Statik"
              className="mt-1 w-full rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:border-brand-300 focus:outline-none"
            />
          </label>
          {kind === "template" && (
            <label className="block text-xs">
              <span className="text-foreground">Template</span>
              <select
                value={templateSlug}
                onChange={(e) => setTemplateSlug(e.target.value)}
                className="mt-1 w-full rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:border-brand-300 focus:outline-none"
              >
                {templates.length === 0 && <option value="">No templates available</option>}
                {templates.map((t) => (
                  <option key={t.id} value={t.slug}>
                    {t.name} {t.is_global ? "(Verolas)" : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-border bg-background px-3 py-1.5 text-xs hover:bg-surface-hover"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit || busy}
              className="inline-flex items-center gap-1.5 rounded border border-brand-300 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-100 disabled:opacity-50 dark:bg-accent dark:text-accent-foreground"
            >
              {busy && <Loader2 className="size-3 animate-spin" aria-hidden="true" />}
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
