import type { Metadata } from "next";

import { ProjectsPanel } from "@/components/projects-panel";

export const metadata: Metadata = {
  title: "Projects",
};

export default async function OrgProjectsPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return (
    <main>
      <ProjectsPanel orgSlug={slug} />
    </main>
  );
}
