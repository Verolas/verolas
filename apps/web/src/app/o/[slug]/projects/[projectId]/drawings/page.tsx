import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function DrawingsPage() {
  return (
    <ProjectPlaceholder
      title="Drawings"
      description="CAD and BIM file browser with sheet-level diff and reviewer markup."
      body="Once a drawing source is connected via Integrations (AutoCAD, Revit, ProjectWise), every sheet lands here with revision history and the AI reviewer's automated findings."
    />
  );
}
