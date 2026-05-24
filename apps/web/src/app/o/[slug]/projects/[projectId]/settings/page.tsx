import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function ProjectSettingsPage() {
  return (
    <ProjectPlaceholder
      title="Project Settings"
      description="Project name, discipline, retention policy, archive."
      body="Renaming, archiving, deleting a project, and setting the data retention window for old reviewer findings and AI run history."
    />
  );
}
