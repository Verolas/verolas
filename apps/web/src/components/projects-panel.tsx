"use client";

import { ChevronDown, FolderPlus, MoreHorizontal, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, type Discipline, type Project, type ProjectStatus, orgsApi } from "@/lib/api";

const DISCIPLINES: Discipline[] = [
  "structural",
  "geotech",
  "water",
  "transport",
  "review",
  "practice",
];

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; projects: Project[] }
  | { kind: "error"; status: number; detail: string };

type Filter = "all" | "active" | "archived";

const STATUS_LABEL: Record<ProjectStatus, string> = {
  active: "Active",
  archived: "Archived",
  deleted: "Deleted",
};

export function ProjectsPanel({ orgSlug }: { orgSlug: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [filter, setFilter] = useState<Filter>("all");
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [discipline, setDiscipline] = useState<Discipline>("structural");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    setState({ kind: "loading" });
    try {
      const projects = await orgsApi.listProjects(orgSlug);
      setState({ kind: "ready", projects });
    } catch (err) {
      if (err instanceof ApiError) {
        setState({ kind: "error", status: err.status, detail: err.detail });
      } else {
        setState({ kind: "error", status: 0, detail: String(err) });
      }
    }
  }, [orgSlug]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const visible = useMemo(() => {
    if (state.kind !== "ready") return [];
    if (filter === "all") return state.projects;
    return state.projects.filter((p) => p.status === filter);
  }, [state, filter]);

  const counts = useMemo(() => {
    if (state.kind !== "ready") return { all: 0, active: 0, archived: 0 };
    return {
      all: state.projects.length,
      active: state.projects.filter((p) => p.status === "active").length,
      archived: state.projects.filter((p) => p.status === "archived").length,
    };
  }, [state]);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await orgsApi.createProject(orgSlug, name, discipline);
      setName("");
      setDiscipline("structural");
      setShowForm(false);
      await refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : String(err);
      setFormError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold leading-tight text-foreground">Projects</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Each project groups deliverables, files, and the supervised AI runs for one
            engineering job.
          </p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>
          <Plus className="size-3.5" aria-hidden="true" />
          {showForm ? "Cancel" : "New project"}
        </Button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="segmented">
          <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>
            All <span className="ml-1 font-mono text-[10px] opacity-70">{counts.all}</span>
          </button>
          <button
            type="button"
            aria-pressed={filter === "active"}
            onClick={() => setFilter("active")}
          >
            Active <span className="ml-1 font-mono text-[10px] opacity-70">{counts.active}</span>
          </button>
          <button
            type="button"
            aria-pressed={filter === "archived"}
            onClick={() => setFilter("archived")}
          >
            Archived{" "}
            <span className="ml-1 font-mono text-[10px] opacity-70">{counts.archived}</span>
          </button>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md border border-hairline bg-surface px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground"
        >
          Sort: Most recent
          <ChevronDown className="size-3" aria-hidden="true" />
        </button>
      </div>

      {showForm && (
        <form
          className="rounded-lg border border-hairline bg-surface p-4 shadow-xs"
          onSubmit={handleCreate}
          aria-label="New project form"
        >
          <div className="grid gap-3 sm:grid-cols-[2fr_1fr_auto] sm:items-end">
            <div className="space-y-1.5">
              <Label htmlFor="name" className="text-xs uppercase tracking-wider">
                Project name
              </Label>
              <Input
                id="name"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="HQ Erweiterung"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="discipline" className="text-xs uppercase tracking-wider">
                Discipline
              </Label>
              <select
                id="discipline"
                value={discipline}
                onChange={(event) => setDiscipline(event.target.value as Discipline)}
                className="flex h-9 w-full rounded-md border border-input bg-surface px-2.5 text-sm capitalize text-foreground"
              >
                {DISCIPLINES.map((option) => (
                  <option key={option} value={option} className="capitalize">
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" disabled={submitting} className="h-9">
              {submitting ? "Creating..." : "Create"}
            </Button>
          </div>
          {formError && (
            <p role="alert" className="mt-3 text-sm text-destructive">
              {formError}
            </p>
          )}
        </form>
      )}

      <ProjectsTable state={state} visible={visible} filter={filter} onCreate={() => setShowForm(true)} />
    </div>
  );
}

function ProjectsTable({
  state,
  visible,
  filter,
  onCreate,
}: {
  state: LoadState;
  visible: Project[];
  filter: Filter;
  onCreate: () => void;
}) {
  if (state.kind === "loading") {
    return (
      <div className="rounded-lg border border-hairline bg-surface p-10 text-center text-sm text-muted-foreground">
        Loading projects...
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div className="rounded-lg border border-hairline bg-surface p-6 text-sm">
        <div className="font-medium text-foreground">Could not load projects</div>
        <div className="mt-1 text-muted-foreground">
          {state.status === 401
            ? "Sign in with a Verolas account to view projects."
            : state.detail}
        </div>
      </div>
    );
  }
  if (visible.length === 0) {
    return (
      <div className="rounded-lg border border-hairline bg-surface p-10 text-center">
        <div className="mx-auto mb-3 grid size-10 place-items-center rounded-full bg-muted text-muted-foreground">
          <FolderPlus className="size-5" aria-hidden="true" />
        </div>
        <div className="text-sm font-medium text-foreground">
          {filter === "all" ? "No projects yet" : `No ${filter} projects`}
        </div>
        <div className="mt-1 text-sm text-muted-foreground">
          Create the first one to start tracking deliverables, files, and supervised AI runs.
        </div>
        <Button onClick={onCreate} className="mt-4">
          <Plus className="size-3.5" aria-hidden="true" />
          New project
        </Button>
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-lg border border-hairline bg-surface shadow-xs">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-hairline bg-muted/40 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-2.5">Project</th>
            <th className="px-4 py-2.5">Discipline</th>
            <th className="px-4 py-2.5">Status</th>
            <th className="px-4 py-2.5">Created</th>
            <th className="px-4 py-2.5 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((project, index) => (
            <tr
              key={project.id}
              className={`group transition-colors hover:bg-muted/40 ${
                index === visible.length - 1 ? "" : "border-b border-hairline"
              }`}
            >
              <td className="px-4 py-3">
                <div className="font-medium text-foreground">{project.name}</div>
                <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                  {project.id.slice(0, 8)}
                </div>
              </td>
              <td className="px-4 py-3">
                <span className="pill" data-discipline={project.discipline}>
                  {project.discipline}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="inline-flex items-center gap-1.5 text-sm text-foreground">
                  <span className="status-dot" data-status={project.status} />
                  {STATUS_LABEL[project.status]}
                </span>
              </td>
              <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                {formatDate(project.created_at)}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  type="button"
                  aria-label={`Actions for ${project.name}`}
                  className="invisible inline-grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground group-hover:visible"
                >
                  <MoreHorizontal className="size-4" aria-hidden="true" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
