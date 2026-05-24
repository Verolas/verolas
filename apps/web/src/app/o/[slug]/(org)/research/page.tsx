"use client";

import { ResearchSurface } from "@/components/research-surface";

export default function OrgResearchPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <header>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Research</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Search every code Verolas supports. Bookmark frequently used clauses and get notified
          when a code that touches an active project is updated.
        </p>
      </header>
      <ResearchSurface />
    </div>
  );
}
