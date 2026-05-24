import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function AgentsPage() {
  return (
    <ProjectPlaceholder
      title="Agents"
      description="The Verolas workforce available to this project."
      body="Tier 1 productivity agents (HOAI fee, QTO, permit pack), Tier 2 drafters (reinforcement, formwork, geotech report), Tier 3 co-pilots (structural calc, FEA, code-check), and the always-on advisors. Each agent card shows capability, run count, success rate, and a one-click run button."
    />
  );
}
