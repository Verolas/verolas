"use client";

import {
  ArrowUpDown,
  LayoutGrid,
  List,
  MoreHorizontal,
  Plus,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ApiError,
  type Discipline,
  type Project,
  type ProjectStatus,
  orgsApi,
} from "@/lib/api";

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

type View = "grid" | "list";

const STATUS_LABEL: Record<ProjectStatus, string> = {
  active: "Active",
  archived: "Archived",
  deleted: "Deleted",
};

export function ProjectsPanel({ orgSlug }: { orgSlug: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [search, setSearch] = useState("");
  const [view, setView] = useState<View>("grid");
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

  const filtered = useMemo(() => {
    if (state.kind !== "ready") return [];
    const q = search.trim().toLowerCase();
    if (!q) return state.projects;
    return state.projects.filter((p) => p.name.toLowerCase().includes(q));
  }, [state, search]);

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
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <h1 className="text-2xl font-normal tracking-tight text-foreground">Projects</h1>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search for a project"
            className="pl-8"
          />
        </div>
        <button
          type="button"
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-dashed border-border bg-surface px-3 text-sm text-foreground hover:bg-surface-hover"
        >
          Status
          <ArrowUpDown className="size-3 text-muted-foreground" aria-hidden="true" />
        </button>
        <button
          type="button"
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-surface px-3 text-sm text-foreground hover:bg-surface-hover"
        >
          <ArrowUpDown className="size-3 text-muted-foreground" aria-hidden="true" />
          Sorted by name
        </button>
        <div className="ml-auto inline-flex h-9 overflow-hidden rounded-md border border-border">
          <button
            type="button"
            aria-pressed={view === "grid"}
            onClick={() => setView("grid")}
            className={`grid w-9 place-items-center ${
              view === "grid" ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-surface-hover"
            }`}
            aria-label="Grid view"
          >
            <LayoutGrid className="size-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
            className={`grid w-9 place-items-center border-l border-border ${
              view === "list" ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-surface-hover"
            }`}
            aria-label="List view"
          >
            <List className="size-3.5" aria-hidden="true" />
          </button>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>
          <Plus className="size-3.5" aria-hidden="true" />
          {showForm ? "Cancel" : "New project"}
        </Button>
      </div>

      {showForm && (
        <form
          className="rounded-md border border-border bg-surface p-4"
          onSubmit={handleCreate}
          aria-label="New project form"
        >
          <div className="grid gap-3 sm:grid-cols-[2fr_1fr_auto] sm:items-end">
            <div className="space-y-1.5">
              <Label htmlFor="name" className="text-[11px] uppercase tracking-wider">
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
              <Label htmlFor="discipline" className="text-[11px] uppercase tracking-wider">
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
            <Button type="submit" disabled={submitting}>
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

      <ProjectsView state={state} projects={filtered} view={view} orgSlug={orgSlug} />
    </div>
  );
}

function ProjectsView({
  state,
  projects,
  view,
  orgSlug,
}: {
  state: LoadState;
  projects: Project[];
  view: View;
  orgSlug: string;
}) {
  if (state.kind === "loading") {
    return (
      <div className="rounded-md border border-border bg-surface p-10 text-center text-sm text-muted-foreground">
        Loading projects...
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div className="rounded-md border border-border bg-surface p-6 text-sm">
        <div className="font-medium text-foreground">Could not load projects</div>
        <div className="mt-1 text-muted-foreground">
          {state.status === 401
            ? "Sign in with a Verolas account to view projects."
            : state.detail}
        </div>
      </div>
    );
  }
  if (projects.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface p-12 text-center">
        <div className="text-lg font-medium text-foreground">Create a project</div>
        <p className="mt-1 text-sm text-muted-foreground">
          Launch a supervised engineering workspace built for civil teams.
        </p>
        <Button className="mt-4">
          <Plus className="size-3.5" aria-hidden="true" />
          New project
        </Button>
      </div>
    );
  }
  if (view === "grid") {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <ProjectCard key={project.id} project={project} orgSlug={orgSlug} />
        ))}
      </div>
    );
  }
  return <ProjectsTable projects={projects} orgSlug={orgSlug} />;
}

function ProjectCard({ project, orgSlug }: { project: Project; orgSlug: string }) {
  return (
    <Link
      href={`/o/${orgSlug}/projects/${project.id}`}
      className="group relative flex flex-col gap-3 rounded-md border border-border bg-surface p-4 transition-shadow hover:shadow-sm"
      prefetch={false}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-foreground">{project.name}</div>
          <div className="mt-1 truncate text-xs text-muted-foreground">
            {capitalize(project.discipline)} workspace
          </div>
        </div>
        <button
          type="button"
          aria-label={`Actions for ${project.name}`}
          className="invisible grid size-7 place-items-center rounded text-muted-foreground hover:bg-surface-hover hover:text-foreground group-hover:visible"
          onClick={(event) => {
            event.preventDefault();
          }}
        >
          <MoreHorizontal className="size-4" aria-hidden="true" />
        </button>
      </div>
      <div className="flex items-center gap-2">
        <span className="pill" data-discipline={project.discipline}>
          {project.discipline}
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="status-dot" data-status={project.status} />
          {STATUS_LABEL[project.status]}
        </span>
      </div>
      <div className="mt-auto pt-3 text-[11px] font-mono text-muted-foreground">
        {formatDate(project.created_at)}
      </div>
    </Link>
  );
}

function ProjectsTable({ projects, orgSlug }: { projects: Project[]; orgSlug: string }) {
  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-2.5">Name</th>
            <th className="px-4 py-2.5">Discipline</th>
            <th className="px-4 py-2.5">Status</th>
            <th className="px-4 py-2.5">Created</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {projects.map((project, index) => (
            <tr
              key={project.id}
              className={`group transition-colors hover:bg-surface-hover ${
                index === projects.length - 1 ? "" : "border-b border-border"
              }`}
            >
              <td className="px-4 py-3">
                <Link
                  href={`/o/${orgSlug}/projects/${project.id}`}
                  className="font-medium text-foreground hover:text-primary"
                  prefetch={false}
                >
                  {project.name}
                </Link>
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
                  className="invisible inline-grid size-7 place-items-center rounded text-muted-foreground hover:bg-surface-hover hover:text-foreground group-hover:visible"
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

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}
