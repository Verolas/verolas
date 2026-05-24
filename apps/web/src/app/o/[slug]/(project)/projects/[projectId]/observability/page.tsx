import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function ObservabilityPage() {
  return (
    <ProjectPlaceholder
      title="Observability"
      description="Run metrics, AI reviewer pass-rate, reviewer-hour spend."
      body="Charts for ongoing AI runs, p95 reviewer cycle time, finding-resolution rate, and cost per deliverable. Filter by reviewer, discipline, or document type."
    />
  );
}
