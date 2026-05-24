"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
    <main className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>{error ? "Sign in failed" : "Signing you in"}</CardTitle>
          <CardDescription>
            {error
              ? error
              : "Exchanging the authorization code with the identity provider. This takes a moment."}
          </CardDescription>
        </CardHeader>
        {error && (
          <CardContent>
            <p className="text-sm">
              Return to <a className="underline" href="/login">the sign in page</a> to try again.
            </p>
          </CardContent>
        )}
      </Card>
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
