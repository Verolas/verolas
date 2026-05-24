import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function ReviewersPage() {
  return (
    <ProjectPlaceholder
      title="Reviewers"
      description="Independent check assignments, findings, and sign-off."
      body="Assign a reviewer (internal or external), see their open findings, and capture the signed sign-off that closes a deliverable. Every finding links back to the drawing, calc, or document that triggered it."
    />
  );
}
