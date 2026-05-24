"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { OnboardingShell } from "@/components/onboarding-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { readDraft, slugifyOrgName, writeDraft } from "@/lib/onboarding-store";

export default function OnboardingFirmPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [fullName, setFullName] = useState("");

  useEffect(() => {
    const draft = readDraft();
    if (draft.organization_name) setName(draft.organization_name);
    if (draft.organization_slug) {
      setSlug(draft.organization_slug);
      setSlugTouched(true);
    }
    if (draft.full_name) setFullName(draft.full_name);
  }, []);

  function handleNameChange(value: string): void {
    setName(value);
    if (!slugTouched) setSlug(slugifyOrgName(value));
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const patch: Parameters<typeof writeDraft>[0] = {
      organization_name: name.trim(),
      organization_slug: slug.trim(),
    };
    const trimmedFullName = fullName.trim();
    if (trimmedFullName) patch.full_name = trimmedFullName;
    writeDraft(patch);
    router.push("/onboarding/discipline");
  }

  return (
    <OnboardingShell
      step={1}
      title="Set up your firm"
      description="Workspaces are scoped to an engineering firm. You can rename or add more later."
    >
      <form className="space-y-5" onSubmit={handleSubmit} aria-label="Firm details form">
        <div className="space-y-2">
          <Label htmlFor="orgName">Firm name</Label>
          <Input
            id="orgName"
            required
            value={name}
            onChange={(event) => handleNameChange(event.target.value)}
            placeholder="Kafle Engineering GmbH"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="orgSlug">Workspace URL</Label>
          <div className="flex items-center gap-2 rounded-md border border-input bg-background px-3">
            <span className="text-sm text-muted-foreground">verolas.com/o/</span>
            <Input
              id="orgSlug"
              required
              value={slug}
              onChange={(event) => {
                setSlug(event.target.value.toLowerCase());
                setSlugTouched(true);
              }}
              placeholder="kafle-engineering"
              className="border-0 px-0 shadow-none focus-visible:ring-0"
              pattern="[a-z0-9][a-z0-9-]{0,38}[a-z0-9]"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Lowercase letters, digits, and hyphens. Used in shareable URLs.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="fullName">Your full name (optional)</Label>
          <Input
            id="fullName"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            placeholder="Shramish Kafle"
          />
        </div>
        <div className="flex justify-end">
          <Button type="submit">Continue</Button>
        </div>
      </form>
    </OnboardingShell>
  );
}
