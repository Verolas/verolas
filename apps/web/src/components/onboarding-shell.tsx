"use client";

import type { ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ProtectedRoute } from "@/components/protected-route";

interface Props {
  step: 1 | 2 | 3;
  title: string;
  description: string;
  children: ReactNode;
}

const TOTAL_STEPS = 3;

export function OnboardingShell({ step, title, description, children }: Props) {
  return (
    <ProtectedRoute requireOrg={false}>
      <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-verolas-soft to-background p-6">
        <Card className="w-full max-w-xl">
          <CardHeader>
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <span>Step {step}</span>
              <span aria-hidden="true">of</span>
              <span>{TOTAL_STEPS}</span>
              <div className="ml-4 flex h-1 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary"
                  style={{ width: `${(step / TOTAL_STEPS) * 100}%` }}
                />
              </div>
            </div>
            <CardTitle className="mt-3 text-2xl">{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent>{children}</CardContent>
        </Card>
      </main>
    </ProtectedRoute>
  );
}
