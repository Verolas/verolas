"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { OnboardingShell } from "@/components/onboarding-shell";
import { Button } from "@/components/ui/button";
import { type Discipline } from "@/lib/api";
import { readDraft, writeDraft } from "@/lib/onboarding-store";

const DISCIPLINE_OPTIONS: { value: Discipline; label: string; helper: string }[] = [
  {
    value: "structural",
    label: "Structural",
    helper: "Buildings, bridges, retrofit, load paths.",
  },
  {
    value: "geotech",
    label: "Geotech",
    helper: "Soil mechanics, foundations, slope stability.",
  },
  {
    value: "water",
    label: "Water",
    helper: "Hydraulics, drainage, treatment, flood.",
  },
  {
    value: "transport",
    label: "Transport",
    helper: "Roads, rail, intersections, traffic studies.",
  },
  {
    value: "review",
    label: "Review",
    helper: "Independent checking, third-party reviewer.",
  },
  {
    value: "practice",
    label: "Practice management",
    helper: "Multi-discipline firm, mixed workload.",
  },
];

export default function OnboardingDisciplinePage() {
  const router = useRouter();
  const [discipline, setDiscipline] = useState<Discipline | null>(null);

  useEffect(() => {
    const draft = readDraft();
    if (!draft.organization_name) {
      router.replace("/onboarding/firm");
      return;
    }
    if (draft.primary_discipline) setDiscipline(draft.primary_discipline);
  }, [router]);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!discipline) return;
    writeDraft({ primary_discipline: discipline });
    router.push("/onboarding/project");
  }

  return (
    <OnboardingShell
      step={2}
      title="Pick your primary discipline"
      description="We tune the agents and workflows to your discipline. You can change this later."
    >
      <form className="space-y-5" onSubmit={handleSubmit} aria-label="Primary discipline form">
        <div className="grid gap-2 sm:grid-cols-2">
          {DISCIPLINE_OPTIONS.map((option) => {
            const active = discipline === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setDiscipline(option.value)}
                aria-pressed={active}
                className={`flex flex-col items-start gap-1 rounded-md border p-4 text-left transition-colors ${
                  active
                    ? "border-primary bg-verolas-soft"
                    : "border-input hover:border-primary/60"
                }`}
              >
                <span className="text-sm font-semibold">{option.label}</span>
                <span className="text-xs text-muted-foreground">{option.helper}</span>
              </button>
            );
          })}
        </div>
        <div className="flex items-center justify-between">
          <Button type="button" variant="ghost" onClick={() => router.back()}>
            Back
          </Button>
          <Button type="submit" disabled={!discipline}>
            Continue
          </Button>
        </div>
      </form>
    </OnboardingShell>
  );
}
