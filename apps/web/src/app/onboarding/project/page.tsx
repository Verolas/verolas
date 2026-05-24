"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { OnboardingShell } from "@/components/onboarding-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, onboardingApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { clearDraft, readDraft } from "@/lib/onboarding-store";

export default function OnboardingProjectPage() {
  const router = useRouter();
  const { refreshMe } = useAuth();
  const [draftReady, setDraftReady] = useState(false);
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const draft = readDraft();
    if (!draft.organization_name) {
      router.replace("/onboarding/firm");
      return;
    }
    if (!draft.primary_discipline) {
      router.replace("/onboarding/discipline");
      return;
    }
    if (draft.first_project_name) setName(draft.first_project_name);
    setDraftReady(true);
  }, [router]);

  if (!draftReady) {
    return null;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const draft = readDraft();
    if (!draft.organization_name || !draft.primary_discipline) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload: Parameters<typeof onboardingApi.submit>[0] = {
        organization_name: draft.organization_name,
        primary_discipline: draft.primary_discipline,
        first_project_name: name.trim(),
      };
      if (draft.organization_slug) payload.organization_slug = draft.organization_slug;
      if (draft.full_name) payload.full_name = draft.full_name;
      const result = await onboardingApi.submit(payload);
      clearDraft();
      await refreshMe();
      router.replace(`/o/${result.organization_slug}/projects`);
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : String(err);
      setError(message);
      setSubmitting(false);
    }
  }

  return (
    <OnboardingShell
      step={3}
      title="Create your first project"
      description="A project is the top-level container for engineering work. You can add more from the sidebar."
    >
      <form className="space-y-5" onSubmit={handleSubmit} aria-label="First project form">
        <div className="space-y-2">
          <Label htmlFor="projectName">Project name</Label>
          <Input
            id="projectName"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="HQ Erweiterung"
          />
          <p className="text-xs text-muted-foreground">
            Name it after the building, site, or job so teammates recognise it.
          </p>
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="flex items-center justify-between">
          <Button type="button" variant="ghost" onClick={() => router.back()}>
            Back
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating workspace..." : "Create workspace"}
          </Button>
        </div>
      </form>
    </OnboardingShell>
  );
}
