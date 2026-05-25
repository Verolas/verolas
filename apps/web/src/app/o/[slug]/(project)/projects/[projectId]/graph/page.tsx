import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function GraphPage() {
  return (
    <ProjectPlaceholder
      title="Knowledge Graph"
      description="Cross-artifact dependency view. What's affected when something upstream changes."
      body="Full-screen force-directed graph of every artifact on the project and the edges between them: which calc depends on which load case, which drawing was generated from which BIM model, which deliverable cites which code clause. Drag any node to see its downstream blast radius. The same engine powers the Overview impact card; this page is the zoom-in."
    />
  );
}
