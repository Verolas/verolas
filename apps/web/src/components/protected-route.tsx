"use client";

/**
 * Gate for app shells that require both an authenticated user and an
 * onboarded one. Behaviour:
 *  - while auth is loading: render a quiet status placeholder
 *  - no token: redirect to /login?next=<current path>
 *  - token but no /v1/me memberships: redirect to /onboarding/firm
 *  - token + memberships: render children
 *
 * Use `requireOrg=false` for shells (like /onboarding itself) that
 * only need a token and must not trigger the onboarding redirect.
 */

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/lib/auth-context";

export function ProtectedRoute({
  children,
  requireOrg = true,
}: {
  children: ReactNode;
  requireOrg?: boolean;
}) {
  const { tokens, me, isLoading, isLoadingMe } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!tokens) {
      const pathname = window.location.pathname + window.location.search;
      const search =
        pathname && pathname !== "/login" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${search}`);
      return;
    }
    if (!requireOrg) return;
    if (isLoadingMe) return;
    // Either /v1/me errored (me === null) or returned no memberships:
    // both mean the caller hasn't onboarded yet, so send them to step one.
    if (!me || me.memberships.length === 0) {
      router.replace("/onboarding/firm");
    }
  }, [isLoading, isLoadingMe, tokens, me, requireOrg, router]);

  const blocked =
    isLoading ||
    !tokens ||
    (requireOrg && (isLoadingMe || !me || me.memberships.length === 0));

  if (blocked) {
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
