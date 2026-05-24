import type { ReactNode } from "react";

import { OrgShell } from "@/components/app-shell/org-shell";

export default async function OrgLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <OrgShell slug={slug}>{children}</OrgShell>;
}
