/**
 * Map from connector class id to a Simple Icons slug.
 *
 * Simple Icons (https://simpleicons.org) ships MIT-licensed SVG marks for
 * thousands of brands and serves them off a CDN. Each card on the
 * integrations page renders the brand's official logo where one exists;
 * vendors that Simple Icons doesn't cover (smaller engineering SaaS,
 * regional certificate authorities) fall back to a two-letter initial
 * tile rendered by the page component.
 *
 * The slug is the kebab-case product name. See
 * https://simpleicons.org/?q=<vendor> to confirm a match before adding.
 */

export const CONNECTOR_LOGO_SLUGS: Record<string, string> = {
  // Microsoft products — each has its own brand mark
  "ms-sharepoint": "microsoftsharepoint",
  "ms-onedrive": "microsoftonedrive",
  "ms-teams": "microsoftteams",
  "ms-outlook": "microsoftoutlook",
  "ms-excel": "microsoftexcel",

  // Google products
  "google-drive": "googledrive",
  "google-sheets": "googlesheets",
  gmail: "gmail",

  // Other vendors
  "autodesk-aps": "autodesk",
  slack: "slack",
  procore: "procore",
  box: "box",
  dropbox: "dropbox",
  docusign: "docusign",
  "adobe-sign": "adobeacrobatreader",
  allplan: "nemetschek",
  rhino: "rhinoceros",
  "bentley-projectwise": "bentley",
  "dlubal-rfem": "dlubal",
  "csi-suite": "computersandstructuresinc",
  staad: "bentley",
  plaxis: "bentley",
  "idea-statica": "ideastatica",
  "bluebeam-studio": "bluebeam",
  egnyte: "egnyte",
  tekla: "trimble",
  // No widely-recognised brand mark in Simple Icons — fall back to initials:
  //   sofistik, newforma, d-trust-qes, verolas-library
};

export function logoUrlForConnector(classId: string): string | null {
  const slug = CONNECTOR_LOGO_SLUGS[classId];
  if (!slug) return null;
  return `https://cdn.simpleicons.org/${slug}`;
}
