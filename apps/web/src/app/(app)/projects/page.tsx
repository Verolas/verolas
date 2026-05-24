import type { Metadata } from "next";

import { ProjectsPanel } from "@/components/projects-panel";

export const metadata: Metadata = {
  title: "Projects",
};

export default function ProjectsPage() {
  return (
    <main>
      <ProjectsPanel />
    </main>
  );
}
