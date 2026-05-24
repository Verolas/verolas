import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function SubmissionsPage() {
  return (
    <ProjectPlaceholder
      title="Submissions"
      description="Permit packs assembled per jurisdiction."
      body="Bauantrag per Bundesland in Germany, Building Permit per state and county in the US, Planning Application per Local Authority in the UK. Each pack pulls drawings, the calc summary, and the compliance matrix in the local format and produces a stamp-ready PDF/A."
    />
  );
}
