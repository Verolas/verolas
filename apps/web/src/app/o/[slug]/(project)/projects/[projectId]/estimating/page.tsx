import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function EstimatingPage() {
  return (
    <ProjectPlaceholder
      title="Estimating"
      description="Quantity takeoff, cost estimation, and tender documents."
      body="Quantities derived directly from the BIM model and drawings per REB 23.003 or the regional standard, priced against BKI in Germany, RSMeans in the US, Spon's in the UK, or Rawlinsons in Australia. Generates VOB/A line items, AIA bid documents, or JCT/NEC packages."
    />
  );
}
