import { redirect } from "next/navigation";

export default async function ProjectIndex({
  params,
}: {
  params: Promise<{ slug: string; projectId: string }>;
}) {
  const { slug, projectId } = await params;
  redirect(`/o/${slug}/projects/${projectId}/overview`);
}
