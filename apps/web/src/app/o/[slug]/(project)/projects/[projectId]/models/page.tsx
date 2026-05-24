import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function ModelsPage() {
  return (
    <ProjectPlaceholder
      title="Models & BIM"
      description="3D models, IFC exports, and Revit-linked geometry."
      body="Once BIM 360 or ProjectWise is connected, your federated model appears here. The AI reviewer can run clash detection and report findings as reviewer items."
    />
  );
}
