import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function VaultPage() {
  return (
    <ProjectPlaceholder
      title="Vault"
      description="Every project file in one place — versioned, audit-logged, lineage-aware."
      body="Full-text search across drawings, calcs, BIM models, soil reports, and email attachments. Lineage view shows which run produced which artefact. The distribution matrix tracks who has been sent what version, and transmittal records double as the legal record of delivery to clients and authorities."
    />
  );
}
