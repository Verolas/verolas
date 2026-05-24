import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function ProjectIntegrationsPage() {
  return (
    <ProjectPlaceholder
      title="Integrations"
      description="Project-scoped connectors for AutoCAD, Revit, ProjectWise, Bluebeam, Teams, Slack."
      body="Configure which Integrations are mounted on this specific project. The org-level Integrations page sets the available providers; this page picks which ones are active here and on what scope."
    />
  );
}
