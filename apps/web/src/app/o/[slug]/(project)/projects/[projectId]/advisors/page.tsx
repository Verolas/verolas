import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function AdvisorsPage() {
  return (
    <ProjectPlaceholder
      title="Advisors"
      description="Automated checks: code-compliance, drawing-standards, calc-sanity, missing data."
      body="Each advisor runs continuously and surfaces issues in the reviewer queue. Think of it as a linter for engineering deliverables: open findings, severity, and a link to the exact line of evidence."
    />
  );
}
