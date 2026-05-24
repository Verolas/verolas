"use client";

import { ChevronsUpDown, Cable, GitBranch } from "lucide-react";
import Link from "next/link";

export interface ProjectBreadcrumbProps {
  orgSlug: string;
  projectId: string;
  projectName: string;
  branch?: string;
  branchTag?: string;
  onOpenConnect?: () => void;
}

export function ProjectBreadcrumb({
  orgSlug,
  projectId,
  projectName,
  branch = "main",
  branchTag = "PRODUCTION",
  onOpenConnect,
}: ProjectBreadcrumbProps) {
  return (
    <>
      <span className="text-muted-foreground" aria-hidden="true">
        /
      </span>
      <Link
        href={`/o/${orgSlug}/projects/${projectId}/overview`}
        className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-sm hover:bg-surface-hover"
      >
        <span
          className="grid size-4 place-items-center rounded text-[10px] font-semibold text-white"
          style={{ backgroundColor: stringToColor(projectId) }}
        >
          {projectName[0]?.toUpperCase() ?? "?"}
        </span>
        <span className="max-w-[180px] truncate font-medium text-foreground">{projectName}</span>
        <ChevronsUpDown className="size-3 text-muted-foreground" aria-hidden="true" />
      </Link>
      <button
        type="button"
        className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-sm text-foreground hover:bg-surface-hover"
      >
        <GitBranch className="size-3 text-muted-foreground" aria-hidden="true" />
        <span className="font-medium">{branch}</span>
        <span className="badge" data-tone="warning">
          {branchTag}
        </span>
        <ChevronsUpDown className="size-3 text-muted-foreground" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={onOpenConnect}
        className="inline-flex h-7 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 text-xs text-foreground hover:bg-surface-hover"
      >
        <Cable className="size-3 text-muted-foreground" aria-hidden="true" />
        Connect
      </button>
    </>
  );
}

function stringToColor(value: string): string {
  let h = 0;
  for (let i = 0; i < value.length; i += 1) {
    h = value.charCodeAt(i) + ((h << 5) - h);
  }
  const hue = Math.abs(h) % 360;
  return `hsl(${hue}, 35%, 45%)`;
}
