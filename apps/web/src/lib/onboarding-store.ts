/**
 * sessionStorage-backed scratch space for the three-step onboarding
 * wizard. We deliberately do not POST anything to the API until the
 * user finishes step three; the in-progress draft lives only in their
 * browser so a refresh doesn't lose state.
 */

import type { Discipline } from "./api";
import type { Region, Locale } from "./locales";

const KEY = "verolas_onboarding_draft";

export interface OnboardingDraft {
  organization_name?: string;
  organization_slug?: string;
  primary_discipline?: Discipline;
  first_project_name?: string;
  full_name?: string;
  region?: Region;
  locale?: Locale;
}

export function readDraft(): OnboardingDraft {
  if (typeof window === "undefined") return {};
  const raw = window.sessionStorage.getItem(KEY);
  if (!raw) return {};
  try {
    return JSON.parse(raw) as OnboardingDraft;
  } catch {
    return {};
  }
}

export function writeDraft(patch: OnboardingDraft): OnboardingDraft {
  const merged = { ...readDraft(), ...patch };
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(KEY, JSON.stringify(merged));
  }
  return merged;
}

export function clearDraft(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(KEY);
}

export function slugifyOrgName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || "workspace";
}
