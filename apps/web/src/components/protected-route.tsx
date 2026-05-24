"use client";

/**
 * Gate for app shells that need an authenticated + onboarded user.
 *
 * Behaviour:
 *  - while auth is loading or /v1/me is in flight: quiet status placeholder
 *  - no token: redirect to /login?next=<current path>
 *  - /v1/me returned successfully but with zero memberships: send to onboarding
 *  - /v1/me errored: show the error so we don't trap the user in onboarding
 *  - has memberships: render children
 *
 * `requireOrg=false` for shells (like /onboarding itself) that only
 * need a token and must not trigger the onboarding redirect.
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
  const { tokens, me, isLoading, meStatus, meError } = useAuth();
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
    // Only redirect once /v1/me has actually returned a payload that
    // says there are no memberships. Mid-flight `me === null` should
    // not trigger a redirect; an API error gets a visible message.
    if (meStatus === "loaded" && me && me.memberships.length === 0) {
      router.replace("/onboarding/firm");
    }
  }, [isLoading, tokens, me, meStatus, requireOrg, router]);

  if (isLoading || !tokens) {
    return <LoadingPlaceholder />;
  }

  if (requireOrg) {
    if (meStatus === "idle" || meStatus === "loading") {
      return <LoadingPlaceholder />;
    }
    if (meStatus === "error") {
      return (
        <div
          role="alert"
          className="mx-auto mt-20 max-w-md rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          Could not load your account: {meError ?? "unknown error"}. Try refreshing the page.
        </div>
      );
    }
    if (!me || me.memberships.length === 0) {
      return <LoadingPlaceholder />;
    }
  }

  return <>{children}</>;
}

function LoadingPlaceholder() {
  return (
    <div
      role="status"
      className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground"
    >
      Loading session...
    </div>
  );
}
