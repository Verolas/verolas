"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, type Discipline, type Project, orgsApi } from "@/lib/api";

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

export function ProjectsPanel({ orgSlug }: { orgSlug: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
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
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="text-sm text-muted-foreground">
            A project is the top level container for engineering work. Create one per building,
            site, or infrastructure piece.
          </p>
        </div>
        <Button onClick={() => setShowForm((value) => !value)}>
          {showForm ? "Cancel" : "New project"}
        </Button>
      </header>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>New project</CardTitle>
            <CardDescription>Pick a discipline so the right workflows surface.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleCreate} aria-label="New project form">
              <div className="space-y-2">
                <Label htmlFor="name">Project name</Label>
                <Input
                  id="name"
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="HQ Erweiterung"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="discipline">Discipline</Label>
                <select
                  id="discipline"
                  value={discipline}
                  onChange={(event) => setDiscipline(event.target.value as Discipline)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  {DISCIPLINES.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
              {formError && (
                <p role="alert" className="text-sm text-destructive">
                  {formError}
                </p>
              )}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating..." : "Create project"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <section aria-label="Project list">
        {state.kind === "loading" && (
          <p role="status" className="text-sm text-muted-foreground">
            Loading projects...
          </p>
        )}
        {state.kind === "error" && (
          <Card>
            <CardHeader>
              <CardTitle>Could not load projects</CardTitle>
              <CardDescription>
                {state.status === 401
                  ? "Sign in with a Verolas account to view projects."
                  : state.detail}
              </CardDescription>
            </CardHeader>
          </Card>
        )}
        {state.kind === "ready" && state.projects.length === 0 && (
          <Card>
            <CardHeader>
              <CardTitle>No projects yet</CardTitle>
              <CardDescription>
                Create your first project above and it will appear here with its discipline and
                last activity.
              </CardDescription>
            </CardHeader>
          </Card>
        )}
        {state.kind === "ready" && state.projects.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {state.projects.map((project) => (
              <Card key={project.id}>
                <CardHeader>
                  <CardTitle>{project.name}</CardTitle>
                  <CardDescription>
                    {project.discipline} · {project.status}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground">
                    Created {new Date(project.created_at).toLocaleString()}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
