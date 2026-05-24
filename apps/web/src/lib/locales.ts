/**
 * Region + locale catalog.
 *
 * Region is the primary onboarding choice; it drives the default
 * locale, the code set (Eurocode with regional NA, ACI, etc.), the
 * units (metric vs imperial), the date format, the fee schedule, the
 * drawing template, and the permit-pack format. A user can override
 * just the UI language in their profile settings without changing the
 * firm's code set.
 */

export type Region = "de" | "ch" | "at" | "fr" | "nl" | "be" | "uk" | "us" | "au" | "ca";

export type Locale =
  | "de-DE"
  | "de-CH"
  | "de-AT"
  | "fr-FR"
  | "nl-NL"
  | "nl-BE"
  | "en-US"
  | "en-GB"
  | "en-AU"
  | "en-CA";

export interface RegionMeta {
  region: Region;
  label: string;
  flag: string;
  locale: Locale;
  codeSet: string;
  units: "metric" | "imperial";
  feeSchedule: string;
  permitAuthority: string;
}

export const REGIONS: RegionMeta[] = [
  {
    region: "de",
    label: "Deutschland",
    flag: "🇩🇪",
    locale: "de-DE",
    codeSet: "Eurocode + DIN NA",
    units: "metric",
    feeSchedule: "HOAI",
    permitAuthority: "Bauamt (per Bundesland)",
  },
  {
    region: "ch",
    label: "Schweiz",
    flag: "🇨🇭",
    locale: "de-CH",
    codeSet: "SIA 260–267",
    units: "metric",
    feeSchedule: "SIA 103",
    permitAuthority: "Kanton (per Gemeinde)",
  },
  {
    region: "at",
    label: "Österreich",
    flag: "🇦🇹",
    locale: "de-AT",
    codeSet: "Eurocode + ÖNORM NA",
    units: "metric",
    feeSchedule: "HOA",
    permitAuthority: "Magistrat",
  },
  {
    region: "fr",
    label: "France",
    flag: "🇫🇷",
    locale: "fr-FR",
    codeSet: "Eurocode + NF NA + DTU",
    units: "metric",
    feeSchedule: "Loi MOP",
    permitAuthority: "Préfecture",
  },
  {
    region: "nl",
    label: "Nederland",
    flag: "🇳🇱",
    locale: "nl-NL",
    codeSet: "Eurocode + NEN NA",
    units: "metric",
    feeSchedule: "DNR",
    permitAuthority: "Gemeente",
  },
  {
    region: "be",
    label: "België",
    flag: "🇧🇪",
    locale: "nl-BE",
    codeSet: "Eurocode + NBN NA",
    units: "metric",
    feeSchedule: "KVIV",
    permitAuthority: "Gemeente",
  },
  {
    region: "uk",
    label: "United Kingdom",
    flag: "🇬🇧",
    locale: "en-GB",
    codeSet: "Eurocode + UK NA, BS 8500",
    units: "metric",
    feeSchedule: "RIBA",
    permitAuthority: "Local Authority",
  },
  {
    region: "us",
    label: "United States",
    flag: "🇺🇸",
    locale: "en-US",
    codeSet: "ASCE 7, ACI 318, AISC 360, IBC",
    units: "imperial",
    feeSchedule: "AIA",
    permitAuthority: "State + county",
  },
  {
    region: "au",
    label: "Australia",
    flag: "🇦🇺",
    locale: "en-AU",
    codeSet: "AS 3600, AS 4100, AS 1170",
    units: "metric",
    feeSchedule: "AS 4122",
    permitAuthority: "Council",
  },
  {
    region: "ca",
    label: "Canada",
    flag: "🇨🇦",
    locale: "en-CA",
    codeSet: "NBCC + CSA A23.3 / S16",
    units: "metric",
    feeSchedule: "CCDC",
    permitAuthority: "Municipal",
  },
];

const BY_REGION = new Map(REGIONS.map((r) => [r.region, r]));

export function metaForRegion(region: string): RegionMeta | undefined {
  return BY_REGION.get(region as Region);
}

export function defaultRegionFromBrowser(): Region {
  if (typeof navigator === "undefined") return "us";
  const lang = navigator.language?.toLowerCase() ?? "en-us";
  if (lang.startsWith("de-ch")) return "ch";
  if (lang.startsWith("de-at")) return "at";
  if (lang.startsWith("de")) return "de";
  if (lang.startsWith("fr")) return "fr";
  if (lang.startsWith("nl-be")) return "be";
  if (lang.startsWith("nl")) return "nl";
  if (lang.startsWith("en-gb")) return "uk";
  if (lang.startsWith("en-au")) return "au";
  if (lang.startsWith("en-ca")) return "ca";
  return "us";
}

export const SUPPORTED_LOCALES: Locale[] = REGIONS.map((r) => r.locale);
