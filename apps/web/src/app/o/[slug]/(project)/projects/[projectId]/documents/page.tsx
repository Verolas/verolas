import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function DocumentsPage() {
  return (
    <ProjectPlaceholder
      title="Documents"
      description="Specs, reports, datasheets, and correspondence."
      body="Drag in a PDF or sync a SharePoint folder. Verolas OCRs every page, links references between documents, and surfaces inconsistencies to the reviewer queue."
    />
  );
}
