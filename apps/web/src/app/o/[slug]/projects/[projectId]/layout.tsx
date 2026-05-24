import type { ReactNode } from "react";

import { ProjectShellWithData } from "@/components/app-shell/project-shell-with-data";

export default async function ProjectLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ slug: string; projectId: string }>;
}) {
  const { slug, projectId } = await params;
  return (
    <ProjectShellWithData slug={slug} projectId={projectId}>
      {children}
    </ProjectShellWithData>
  );
}
