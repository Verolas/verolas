/**
 * Light-weight translation helper for the marketing + onboarding pages.
 *
 * We resolve a Locale string to a fully-translated namespace; locales
 * that are not yet QA'd by a senior structural engineer fall back to
 * en-US so we never ship machine-translated engineering terms.
 *
 * The shell uses this synchronously on the client. Server-side
 * messages go through `next-intl` later when we add per-locale URL
 * routing.
 */

import deDE from "../../messages/de-DE.json";
import enUS from "../../messages/en-US.json";
import { SUPPORTED_LOCALES, type Locale } from "./locales";

type Messages = typeof enUS;

const BUNDLES: Partial<Record<Locale, Messages>> = {
  "en-US": enUS,
  "de-DE": deDE,
};

export function resolveLocaleBundle(locale: string): Messages {
  if (BUNDLES[locale as Locale]) return BUNDLES[locale as Locale]!;
  if (locale.startsWith("de-")) return deDE;
  if (SUPPORTED_LOCALES.includes(locale as Locale)) return enUS;
  return enUS;
}

export function t(locale: string, path: string): string {
  const messages = resolveLocaleBundle(locale);
  const parts = path.split(".");
  let cursor: unknown = messages;
  for (const part of parts) {
    if (typeof cursor !== "object" || cursor === null) return path;
    cursor = (cursor as Record<string, unknown>)[part];
  }
  return typeof cursor === "string" ? cursor : path;
}
