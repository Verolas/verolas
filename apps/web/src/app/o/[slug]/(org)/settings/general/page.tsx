"use client";

import { Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";

export default function GeneralSettingsPage() {
  const { me } = useAuth();
  const activeOrg = me?.memberships?.[0];

  return (
    <div className="mx-auto w-full max-w-3xl space-y-10">
      <div>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">
          Organization Settings
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          General configuration, privacy, and lifecycle controls.
        </p>
      </div>

      <Section title="Organization details">
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-[160px_1fr] sm:items-center">
            <Label htmlFor="orgName">Organization name</Label>
            <Input
              id="orgName"
              defaultValue={activeOrg?.organization_name ?? ""}
              placeholder="Your firm"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-[160px_1fr] sm:items-center">
            <Label htmlFor="orgSlug">Organization slug</Label>
            <div className="relative">
              <Input
                id="orgSlug"
                defaultValue={activeOrg?.organization_slug ?? ""}
                placeholder="firm-slug"
                className="pr-20"
              />
              <button
                type="button"
                aria-label="Copy slug"
                className="absolute right-1.5 top-1.5 inline-flex h-6 items-center gap-1 rounded px-2 text-xs text-muted-foreground hover:bg-surface-hover hover:text-foreground"
              >
                <Copy className="size-3" aria-hidden="true" />
                Copy
              </button>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost">Cancel</Button>
            <Button>Save</Button>
          </div>
        </div>
      </Section>

      <Section title="Data privacy">
        <div className="grid gap-4 sm:grid-cols-[1fr_1fr]">
          <div>
            <h3 className="text-sm font-medium text-foreground">
              Verolas Assistant Opt-in Level
            </h3>
            <p className="mt-1 text-sm text-foreground-light">
              The Verolas Assistant can provide more relevant answers if you choose to share
              different levels of data. This feature is powered by third-party AI providers.
              This is an organisation-wide setting, so please select the level of data you are
              comfortable sharing.
            </p>
            <p className="mt-2 text-sm text-foreground-light">
              For organisations with regulated data, anonymised consented information will only
              be shared with third-party AI providers with whom Verolas has established a
              Business Associate Agreement (BAA).
            </p>
            <button
              type="button"
              className="mt-3 inline-flex text-sm text-primary underline-offset-4 hover:underline"
            >
              Learn more about data privacy
            </button>
          </div>
          <RadioGroup
            options={[
              {
                value: "disabled",
                label: "Disabled",
                description:
                  "You do not consent to sharing any project information with third-party AI providers; responses will be generic and not tailored to your data.",
                checked: true,
              },
              {
                value: "schema-only",
                label: "Schema Only",
                description:
                  "You consent to sharing your project's metadata (file names, types, drawing sheet titles, model element names) but not actual file contents.",
              },
              {
                value: "schema-logs",
                label: "Schema & Logs",
                description:
                  "Schema plus reviewer-finding history and audit-log events. Useful for the assistant to reason about review patterns.",
              },
            ]}
          />
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-border bg-surface p-6">
      <h2 className="text-base font-medium text-foreground">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function RadioGroup({
  options,
}: {
  options: { value: string; label: string; description: string; checked?: boolean }[];
}) {
  return (
    <div className="space-y-3">
      {options.map((opt) => (
        <label
          key={opt.value}
          className="flex cursor-pointer items-start gap-3 rounded-md border border-border p-3 text-sm hover:bg-surface-hover"
        >
          <input
            type="radio"
            name="privacy"
            value={opt.value}
            defaultChecked={opt.checked}
            aria-label={opt.label}
            className="mt-1 size-3.5 accent-primary"
          />
          <div>
            <div className="font-medium text-foreground">{opt.label}</div>
            <p className="mt-0.5 text-xs text-foreground-light">{opt.description}</p>
          </div>
        </label>
      ))}
    </div>
  );
}
