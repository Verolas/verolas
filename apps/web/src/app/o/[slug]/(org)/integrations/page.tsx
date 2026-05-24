"use client";

import { ExternalLink } from "lucide-react";

interface Integration {
  key: string;
  name: string;
  blurb: string;
  partnerCopy: string;
  ctaCopy: string;
  ctaVariant: "install" | "connect";
  icon: string;
  iconBg: string;
}

const INTEGRATIONS: Integration[] = [
  {
    key: "autocad",
    name: "Autodesk AutoCAD",
    blurb: "Connect AutoCAD drawings to a Verolas project.",
    partnerCopy:
      "Verolas pulls drawing revisions from your Autodesk Construction Cloud project so AI reviewers can diff geometry between submissions and flag clash-prone changes.",
    ctaCopy: "Install AutoCAD integration",
    ctaVariant: "install",
    icon: "AC",
    iconBg: "#cc0000",
  },
  {
    key: "revit",
    name: "Autodesk Revit / BIM 360",
    blurb: "Sync BIM models, sheets, and IFC exports.",
    partnerCopy:
      "Revit models and BIM 360 issues land as native Verolas resources. Reviewers can comment on a model element and the comment shows up in BIM 360 too.",
    ctaCopy: "Install BIM 360 integration",
    ctaVariant: "install",
    icon: "BIM",
    iconBg: "#2a4d7c",
  },
  {
    key: "bentley",
    name: "Bentley ProjectWise",
    blurb: "Read documents and models from your ProjectWise datasource.",
    partnerCopy:
      "Verolas reads designs, calc reports, and specs from ProjectWise. New file versions trigger a supervised AI review pass without copying data out of Bentley.",
    ctaCopy: "Connect ProjectWise",
    ctaVariant: "connect",
    icon: "PW",
    iconBg: "#003a70",
  },
  {
    key: "bluebeam",
    name: "Bluebeam Studio",
    blurb: "Two-way markups + reviewer comments.",
    partnerCopy:
      "PDF markups from Bluebeam Studio sync into the Verolas reviewer queue so independent checkers can act on them without leaving their tool.",
    ctaCopy: "Install Bluebeam integration",
    ctaVariant: "install",
    icon: "BB",
    iconBg: "#2b6cb0",
  },
  {
    key: "sharepoint",
    name: "Microsoft SharePoint",
    blurb: "Mount SharePoint document libraries as Verolas folders.",
    partnerCopy:
      "Point Verolas at a SharePoint library; we mirror specs, drawings, and reports without duplicating storage. Permissions follow your AAD groups.",
    ctaCopy: "Install SharePoint integration",
    ctaVariant: "install",
    icon: "SP",
    iconBg: "#0364b8",
  },
  {
    key: "teams",
    name: "Microsoft Teams",
    blurb: "Reviewer findings, audit pings, and project updates in Teams channels.",
    partnerCopy:
      "Pick a channel per project. Verolas posts when reviewer findings change, when an audit-relevant event happens, or when a deliverable is signed off.",
    ctaCopy: "Add to Teams",
    ctaVariant: "install",
    icon: "MT",
    iconBg: "#4b53bc",
  },
  {
    key: "slack",
    name: "Slack",
    blurb: "Project alerts to a Slack workspace.",
    partnerCopy:
      "Same as Teams: pick a channel per project, Verolas posts reviewer-finding deltas, audit pings, and sign-offs.",
    ctaCopy: "Add to Slack",
    ctaVariant: "install",
    icon: "SL",
    iconBg: "#4a154b",
  },
  {
    key: "onedrive",
    name: "OneDrive / Box / Dropbox",
    blurb: "Folder-level sync for ad-hoc engineering files.",
    partnerCopy:
      "When a CAD or PDF lands in the synced folder it shows up in the right project. Useful for firms that have not standardised on ProjectWise yet.",
    ctaCopy: "Connect storage provider",
    ctaVariant: "connect",
    icon: "OD",
    iconBg: "#0078d4",
  },
];

export default function IntegrationsPage() {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-8">
      <h1 className="text-2xl font-normal tracking-tight text-foreground">Integrations</h1>

      <div className="space-y-px overflow-hidden rounded-md border border-border">
        {INTEGRATIONS.map((item, index) => (
          <IntegrationRow
            key={item.key}
            item={item}
            divider={index < INTEGRATIONS.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

function IntegrationRow({ item, divider }: { item: Integration; divider: boolean }) {
  return (
    <section
      className={`grid gap-8 bg-surface px-6 py-8 sm:grid-cols-[1fr_2fr] ${
        divider ? "border-b border-border" : ""
      }`}
    >
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-medium text-foreground">{item.name}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{item.blurb}</p>
        </div>
        <div
          className="flex h-24 items-center justify-center rounded-md border border-border text-2xl font-semibold tracking-wider text-white"
          style={{ backgroundColor: item.iconBg }}
          aria-hidden="true"
        >
          {item.icon}
        </div>
      </div>
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium text-foreground">
            How does the {item.name} integration work?
          </h3>
          <p className="mt-1 text-sm text-foreground-light">{item.partnerCopy}</p>
        </div>
        <div className="rounded-md border border-border bg-surface-hover/40 p-6 text-center">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground hover:bg-surface-hover"
          >
            <ExternalLink className="size-3.5" aria-hidden="true" />
            {item.ctaCopy}
          </button>
        </div>
      </div>
    </section>
  );
}
