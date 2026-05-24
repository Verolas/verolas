"use client";

import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Loader2,
  Plug,
  Trash2,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  connectorsApi,
  type ConnectorCategory,
  type ConnectorClass,
  type ConnectorInstallation,
} from "@/lib/api";

const CATEGORY_LABEL: Record<ConnectorCategory, string> = {
  cad_bim: "CAD & BIM",
  structural_fea: "Structural FEA",
  geotech_fea: "Geotechnical FEA",
  documents: "Document repositories",
  construction_mgmt: "Construction management",
  markup: "Markup & review",
  spreadsheets: "Spreadsheets",
  communication: "Communication",
  signing: "Signing & QES",
  internal: "Verolas",
};

const CATEGORY_ORDER: ConnectorCategory[] = [
  "internal",
  "documents",
  "cad_bim",
  "structural_fea",
  "geotech_fea",
  "construction_mgmt",
  "spreadsheets",
  "communication",
  "markup",
  "signing",
];

const TIER_LABEL: Record<string, string> = {
  A: "Self-serve",
  B: "Self-serve (vendor key)",
  C: "Partner / on-prem",
  internal: "Built-in",
};

export default function IntegrationsPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const [catalog, setCatalog] = useState<ConnectorClass[]>([]);
  const [installs, setInstalls] = useState<ConnectorInstallation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<ConnectorCategory | "all">("all");

  const refresh = useCallback(async () => {
    try {
      const [cat, ins] = await Promise.all([
        connectorsApi.catalog(),
        connectorsApi.listInstallations(slug),
      ]);
      setCatalog(cat);
      setInstalls(ins);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const installByClassId = useMemo(() => {
    const map = new Map<string, ConnectorInstallation>();
    for (const i of installs) map.set(i.class_id, i);
    return map;
  }, [installs]);

  const grouped = useMemo(() => {
    const out = new Map<ConnectorCategory, ConnectorClass[]>();
    for (const c of catalog) {
      const arr = out.get(c.category) ?? [];
      arr.push(c);
      out.set(c.category, arr);
    }
    return out;
  }, [catalog]);

  const visibleCategories = useMemo(() => {
    if (activeCategory === "all") return CATEGORY_ORDER.filter((c) => grouped.has(c));
    return [activeCategory];
  }, [activeCategory, grouped]);

  const onInstall = useCallback(
    async (cls: ConnectorClass) => {
      setBusy(cls.id);
      try {
        if (cls.tier === "C") {
          await connectorsApi.waitlist(slug, cls.id);
        } else {
          await connectorsApi.install(slug, cls.id);
        }
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusy(null);
      }
    },
    [slug, refresh],
  );

  const onUninstall = useCallback(
    async (install: ConnectorInstallation) => {
      setBusy(install.class_id);
      try {
        await connectorsApi.uninstall(slug, install.id);
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusy(null);
      }
    },
    [slug, refresh],
  );

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Integrations</h1>
        <p className="text-sm text-muted-foreground">
          Install a connector once for the firm. Project managers then bind specific resources
          per project.
        </p>
      </header>

      <CategoryTabs
        active={activeCategory}
        onChange={setActiveCategory}
        available={Array.from(grouped.keys())}
      />

      {error ? (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 size-4" aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Loading catalog
        </div>
      ) : (
        <div className="space-y-10">
          {visibleCategories.map((category) => {
            const entries = grouped.get(category);
            if (!entries) return null;
            return (
              <section key={category} className="space-y-3">
                <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {CATEGORY_LABEL[category]}
                </h2>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {entries.map((cls) => (
                    <ConnectorCard
                      key={cls.id}
                      cls={cls}
                      install={installByClassId.get(cls.id) ?? null}
                      busy={busy === cls.id}
                      onInstall={() => onInstall(cls)}
                      onUninstall={(i) => onUninstall(i)}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

function CategoryTabs({
  active,
  onChange,
  available,
}: {
  active: ConnectorCategory | "all";
  onChange: (next: ConnectorCategory | "all") => void;
  available: ConnectorCategory[];
}) {
  const ordered = CATEGORY_ORDER.filter((c) => available.includes(c));
  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-border pb-1">
      <TabButton active={active === "all"} onClick={() => onChange("all")}>
        All
      </TabButton>
      {ordered.map((c) => (
        <TabButton key={c} active={active === c} onClick={() => onChange(c)}>
          {CATEGORY_LABEL[c]}
        </TabButton>
      ))}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "rounded-md bg-surface-hover px-3 py-1.5 text-xs font-medium text-foreground"
          : "rounded-md px-3 py-1.5 text-xs text-muted-foreground hover:bg-surface-hover hover:text-foreground"
      }
    >
      {children}
    </button>
  );
}

function ConnectorCard({
  cls,
  install,
  busy,
  onInstall,
  onUninstall,
}: {
  cls: ConnectorClass;
  install: ConnectorInstallation | null;
  busy: boolean;
  onInstall: () => void;
  onUninstall: (install: ConnectorInstallation) => void;
}) {
  return (
    <article className="flex h-full flex-col gap-3 rounded-md border border-border bg-surface p-4">
      <header className="flex items-start gap-3">
        <div
          className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-surface-hover text-xs font-semibold text-foreground"
          aria-hidden="true"
        >
          {initials(cls.name)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="truncate text-sm font-medium text-foreground">{cls.name}</h3>
            <TierBadge tier={cls.tier} />
          </div>
          <p className="text-[11px] text-muted-foreground">{cls.vendor}</p>
        </div>
      </header>

      <p className="text-xs text-foreground-light line-clamp-3">{cls.blurb}</p>

      <footer className="mt-auto space-y-2 pt-1">
        <InstallStatus install={install} />
        <div className="flex items-center justify-between gap-2">
          <a
            href={cls.docs_url ?? "#"}
            target="_blank"
            rel="noreferrer"
            className={
              cls.docs_url
                ? "inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
                : "pointer-events-none text-[11px] text-muted-foreground/40"
            }
          >
            Docs <ArrowUpRight className="size-3" aria-hidden="true" />
          </a>
          {install && install.status !== "uninstalled" ? (
            <button
              type="button"
              onClick={() => onUninstall(install)}
              disabled={busy}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-foreground hover:bg-surface-hover disabled:opacity-50"
            >
              <Trash2 className="size-3" aria-hidden="true" />
              Uninstall
            </button>
          ) : (
            <button
              type="button"
              onClick={onInstall}
              disabled={busy}
              className="inline-flex items-center gap-1 rounded-md bg-foreground px-2.5 py-1 text-xs font-medium text-background hover:bg-foreground/85 disabled:opacity-50"
            >
              {busy ? (
                <Loader2 className="size-3 animate-spin" aria-hidden="true" />
              ) : (
                <Plug className="size-3" aria-hidden="true" />
              )}
              {cls.tier === "C" ? "Request" : "Install"}
            </button>
          )}
        </div>
      </footer>
    </article>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const label = TIER_LABEL[tier] ?? tier;
  const tone =
    tier === "internal"
      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
      : tier === "A"
        ? "bg-sky-100 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300"
        : tier === "B"
          ? "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
          : "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
  return (
    <span
      className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium tracking-wide ${tone}`}
    >
      {label}
    </span>
  );
}

function InstallStatus({ install }: { install: ConnectorInstallation | null }) {
  if (!install || install.status === "uninstalled") {
    return <p className="text-[11px] text-muted-foreground">Not installed</p>;
  }
  if (install.status === "installed") {
    return (
      <p className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-300">
        <CheckCircle2 className="size-3" aria-hidden="true" />
        Installed
        {install.last_sync_at ? (
          <span className="text-muted-foreground">
            · synced {relativeTime(install.last_sync_at)}
          </span>
        ) : null}
      </p>
    );
  }
  if (install.status === "pending") {
    return (
      <p className="inline-flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-300">
        <Clock className="size-3" aria-hidden="true" />
        Awaiting sign-in
      </p>
    );
  }
  return (
    <p className="inline-flex items-center gap-1 text-[11px] text-destructive">
      <AlertCircle className="size-3" aria-hidden="true" />
      {install.last_error ?? "Error"}
    </p>
  );
}

function initials(name: string): string {
  return name
    .split(/[\s/]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}
