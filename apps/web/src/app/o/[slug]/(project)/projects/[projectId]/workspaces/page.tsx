import { ProjectPlaceholder } from "@/components/app-shell/project-placeholder";

export default function WorkspacesPage() {
  return (
    <ProjectPlaceholder
      title="Workspaces"
      description="Parallel design variants of the same project, like branches in source control."
      body="Spin up a workspace from main to explore an alternative scheme. Run reviewers on it, compare results to the baseline, and merge a workspace back into the live design once it's approved."
    />
  );
}
