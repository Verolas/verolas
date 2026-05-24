import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function RunsPage() {
  return (
    <ProjectPlaceholder
      title="Runs"
      description="Every agent run on this project — active, queued, completed, scheduled."
      body="Each row links to a run view with the plan, live progress, tool calls, citations, and produced artefacts. The full surface ships in the next iteration along with the agent_runs backend table."
    />
  );
}
