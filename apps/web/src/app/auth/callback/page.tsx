"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { handleCallback } from "@/lib/oidc/client";
import { takePostLoginRedirect } from "@/lib/oidc/session-storage";

function CallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setTokens } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    handleCallback(params)
      .then((tokens) => {
        setTokens(tokens);
        const redirect = takePostLoginRedirect() ?? "/projects";
        router.replace(redirect);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : String(err));
      });
  }, [router, searchParams, setTokens]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-10">
      <div className="w-full max-w-md rounded-lg border border-hairline bg-surface p-6 shadow-sm">
        <h1 className="text-lg font-semibold leading-snug text-foreground">
          {error ? "Sign in failed" : "Signing you in"}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {error
            ? error
            : "Exchanging the authorization code with the identity provider. This usually takes a moment."}
        </p>
        {error && (
          <p className="mt-4 text-sm">
            Return to{" "}
            <a
              className="text-foreground underline-offset-4 hover:underline"
              href="/login"
            >
              the sign in page
            </a>{" "}
            to try again.
          </p>
        )}
      </div>
    </main>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={null}>
      <CallbackInner />
    </Suspense>
  );
}
