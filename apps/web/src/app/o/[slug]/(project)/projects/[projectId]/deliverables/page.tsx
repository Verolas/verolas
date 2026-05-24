import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function DeliverablesPage() {
  return (
    <ProjectPlaceholder
      title="Deliverables"
      description="Phase-based board: what is due, when, and who signs it."
      body="German projects see HOAI Leistungsphasen 1-9, UK projects see RIBA Stages 0-7, US projects see SD / DD / CD / CA. Each deliverable links to its source artefacts and tracks reviewer sign-off state."
    />
  );
}
