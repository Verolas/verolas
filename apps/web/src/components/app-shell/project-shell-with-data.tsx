"use client";

import { useEffect, useState } from "react";

import { ProjectShell } from "@/components/app-shell/project-shell";
import { ApiError, orgsApi, type Project } from "@/lib/api";

interface Props {
  slug: string;
  projectId: string;
  children: React.ReactNode;
}

/**
 * Fetches the project record so the project shell can show the real
 * name in the breadcrumb. Falls back to a short id while loading or
 * on error so the rail + header never render blank.
 */
export function ProjectShellWithData({ slug, projectId, children }: Props) {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      try {
        const list = await orgsApi.listProjects(slug);
        if (cancelled) return;
        const match = list.find((p) => p.id === projectId) ?? null;
        setProject(match);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : String(err));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [slug, projectId]);

  const projectName = project?.name ?? (error ? "Unknown project" : projectId.slice(0, 8));

  return (
    <ProjectShell slug={slug} projectId={projectId} projectName={projectName}>
      {children}
    </ProjectShell>
  );
}
