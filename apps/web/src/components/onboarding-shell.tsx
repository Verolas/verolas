"use client";

import { Building2 } from "lucide-react";
import type { ReactNode } from "react";

import { ProtectedRoute } from "@/components/protected-route";

interface Props {
  step: 1 | 2 | 3;
  title: string;
  description: string;
  children: ReactNode;
}

const STEP_LABELS = ["Firm", "Discipline", "First project"] as const;

export function OnboardingShell({ step, title, description, children }: Props) {
  return (
    <ProtectedRoute requireOrg={false}>
      <main className="flex min-h-screen items-stretch bg-background">
        <aside className="hidden w-80 flex-col justify-between border-r border-hairline bg-surface px-8 py-10 lg:flex">
          <div>
            <div className="flex items-center gap-2">
              <div className="grid size-8 place-items-center rounded-md bg-brand-700 text-white">
                <Building2 className="size-4" aria-hidden="true" />
              </div>
              <div className="flex flex-col leading-tight">
                <span className="text-sm font-semibold text-foreground">Verolas</span>
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Civil AI
                </span>
              </div>
            </div>
            <h2 className="mt-10 text-xl font-semibold leading-snug text-foreground">
              Set up your firm&rsquo;s workspace
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Three quick steps. Your work stays scoped to your firm, audited at every step,
              and surfaced through engineering-grade reviewers.
            </p>
            <ol className="mt-8 space-y-2">
              {STEP_LABELS.map((label, index) => {
                const i = (index + 1) as 1 | 2 | 3;
                const active = i === step;
                const done = i < step;
                return (
                  <li key={label} className="flex items-center gap-3">
                    <span
                      className={`grid size-6 place-items-center rounded-full border text-[11px] font-semibold ${
                        active
                          ? "border-brand-600 bg-brand-600 text-white"
                          : done
                            ? "border-brand-600 bg-brand-50 text-brand-700"
                            : "border-hairline bg-muted text-muted-foreground"
                      }`}
                    >
                      {i}
                    </span>
                    <span
                      className={`text-sm ${
                        active
                          ? "font-medium text-foreground"
                          : done
                            ? "text-foreground"
                            : "text-muted-foreground"
                      }`}
                    >
                      {label}
                    </span>
                  </li>
                );
              })}
            </ol>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Verolas is the vertical AI platform for civil engineering.
          </p>
        </aside>
        <div className="flex flex-1 items-start justify-center px-6 py-10 sm:py-16">
          <div className="w-full max-w-lg">
            <div className="mb-6 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground lg:hidden">
              <span>
                Step {step} of {STEP_LABELS.length}
              </span>
              <div className="ml-2 flex h-1 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-brand-600"
                  style={{ width: `${(step / STEP_LABELS.length) * 100}%` }}
                />
              </div>
            </div>
            <h1 className="text-2xl font-semibold leading-tight tracking-tight text-foreground">
              {title}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">{description}</p>
            <div className="mt-6">{children}</div>
          </div>
        </div>
      </main>
    </ProtectedRoute>
  );
}
