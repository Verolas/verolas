import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function ProjectAuditPage() {
  return (
    <ProjectPlaceholder
      title="Audit Log"
      description="Hash-chained record of every authenticated action in this project."
      body="Reviewer sign-offs, file uploads, advisor findings, every read of a sensitive document. The chain is verified on every load; any tamper attempt is detectable."
    />
  );
}
