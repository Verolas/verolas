"use client";

/**
 * Gate that redirects unauthenticated users to /login.
 *
 * Wraps the authenticated app shell. While the auth context is loading
 * (reading tokens out of sessionStorage on mount) it renders nothing;
 * once loaded it either renders children or redirects.
 */

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/lib/auth-context";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { tokens, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!tokens) {
      const pathname = window.location.pathname + window.location.search;
      const search = pathname && pathname !== "/login" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${search}`);
    }
  }, [isLoading, tokens, router]);

  if (isLoading || !tokens) {
    return (
      <div
        role="status"
        className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground"
      >
        Loading session...
      </div>
    );
  }

  return <>{children}</>;
}
