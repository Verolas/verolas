import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function DeliverablesPage() {
  return (
    <ProjectPlaceholder
      title="Deliverables"
      description="Everything stampable on this project — calc packages, drawings, permit packs, reports."
      body="Tabs ship next: All, Pending Review (reviewer queue with QES sign-off state), Signed, Submitted (Bauamt / building-control transmission). Estimating outputs (QTO, cost, tender) and sustainability reports (LCA, energy code) appear here too as deliverable types — every output of an agent run that ends in a stamp."
    />
  );
}
