import type { ReactNode } from "react";

import { Header } from "@/components/header";
import { ProtectedRoute } from "@/components/protected-route";
import { Sidebar } from "@/components/sidebar";

export default async function OrgLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return (
    <ProtectedRoute>
      <div className="flex min-h-screen">
        <Sidebar activeOrgSlug={slug} />
        <div className="flex flex-1 flex-col">
          <Header />
          <div className="flex-1 p-6">{children}</div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
