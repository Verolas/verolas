"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth-context";

export default function LegacyProjectsRedirect() {
  const router = useRouter();
  const { me, meStatus } = useAuth();

  useEffect(() => {
    if (meStatus !== "loaded") return;
    const slug = me?.memberships?.[0]?.organization_slug;
    if (slug) {
      router.replace(`/o/${slug}/projects`);
    } else {
      router.replace("/onboarding/firm");
    }
  }, [meStatus, me, router]);

  return (
    <main
      role="status"
      className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground"
    >
      Routing you to your workspace...
    </main>
  );
}
