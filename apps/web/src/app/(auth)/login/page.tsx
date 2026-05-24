"use client";

import { Building2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";

function LoginInner() {
  const { signIn } = useAuth();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const next = searchParams.get("next") ?? "/projects";
      await signIn(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-2 text-center">
          <div className="grid size-10 place-items-center rounded-md bg-brand-700 text-white">
            <Building2 className="size-5" aria-hidden="true" />
          </div>
          <span className="text-sm font-semibold text-foreground">Verolas</span>
        </div>
        <div className="rounded-lg border border-hairline bg-surface p-6 shadow-sm">
          <h1 className="text-lg font-semibold leading-snug text-foreground">
            Sign in to Verolas
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Verolas uses single sign on. Continue to be redirected to your identity provider.
          </p>
          <form className="mt-5 space-y-3" onSubmit={handleSubmit} aria-label="Sign in form">
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Redirecting..." : "Continue with single sign on"}
            </Button>
          </form>
          <p className="mt-4 text-xs text-muted-foreground">
            Local password sign in is not available. Each sign in is audited.
          </p>
        </div>
        <p className="mt-6 text-center text-xs text-muted-foreground">
          New here?{" "}
          <a
            href="https://verolas.com"
            className="text-foreground underline-offset-4 hover:underline"
          >
            Learn what Verolas does
          </a>
        </p>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}
