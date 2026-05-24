"use client";

import { useEffect, useState } from "react";

import { ResearchSurface } from "@/components/research-surface";
import { useAuth } from "@/lib/auth-context";
import type { CodeId } from "@/lib/research-data";

interface Props {
  params: Promise<{ slug: string; projectId: string }>;
}

// Map a region to the codes that ship with a project pinned to it.
function codesForRegion(region: string): CodeId[] {
  switch (region) {
    case "de":
      return ["EN1990", "EN1991-1-1", "EN1992-1-1", "EN1993-1-1", "EN1997-1", "DIN_NA_EN1992"];
    case "ch":
      return ["EN1990", "EN1991-1-1", "EN1992-1-1", "EN1993-1-1", "EN1997-1", "SIA_262"];
    case "at":
    case "fr":
    case "nl":
    case "be":
    case "uk":
      return ["EN1990", "EN1991-1-1", "EN1992-1-1", "EN1993-1-1", "EN1997-1"];
    case "us":
      return ["ACI_318", "ASCE_7", "AISC_360"];
    default:
      return ["EN1992-1-1", "ACI_318", "ASCE_7"];
  }
}

export default function ResearchPage({ params }: Props) {
  const [resolved, setResolved] = useState<{ slug: string; projectId: string } | null>(null);
  const { me } = useAuth();

  useEffect(() => {
    void params.then(setResolved);
  }, [params]);

  const region =
    me?.memberships?.find((m) => m.organization_slug === resolved?.slug)?.organization_region ??
    "de";
  const scope = codesForRegion(region);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-8 py-8">
      <header>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Research</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Clause-level code search scoped to this project&rsquo;s pinned code set. Toggle to
          all codes for cross-region comparison.
        </p>
      </header>
      <ResearchSurface scopedCodeIds={scope} scopeLabel={`${region.toUpperCase()} codes`} />
    </div>
  );
}
