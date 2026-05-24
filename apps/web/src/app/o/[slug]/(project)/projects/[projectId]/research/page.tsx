import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function CodesPage() {
  return (
    <ProjectPlaceholder
      title="Codes & Research"
      description="The Verolas Research surface, scoped to this project's pinned code version."
      body="Search Eurocode clauses with the regional National Annex applied. Cross-compare a clause against earlier editions or the US ASCE / ACI counterpart. An escape hatch lets you query across every code Verolas supports if you need to compare regions. Citations are inline-quotable where the licence permits."
    />
  );
}
