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
      <div className="flex min-h-screen bg-background">
        <Sidebar activeOrgSlug={slug} />
        <div className="flex min-h-screen flex-1 flex-col">
          <Header />
          <div className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">{children}</div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
