import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function GraphPage() {
  return (
    <ProjectPlaceholder
      title="Network Graph"
      description="Every dependency in this project as an interactive network."
      body="Each node is a project entity (a column, a calc run, a drawing sheet, a code clause, a material). Each edge is a derivation, citation, supersession, or sign-off. Move a column and the affected nodes light up. The interactive force-directed view ships in the next iteration."
    />
  );
}
