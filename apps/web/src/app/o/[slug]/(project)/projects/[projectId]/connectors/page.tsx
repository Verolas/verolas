"use client";

import { AlertCircle, Loader2, Plug, RefreshCw, Trash2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  connectorsApi,
  type ConnectorBinding,
  type ConnectorClass,
  type ConnectorInstallation,
} from "@/lib/api";

interface BindRow extends ConnectorBinding {
  className: string;
  instanceLabel: string;
}

export default function ProjectConnectorsPage() {
  const params = useParams<{ slug: string; projectId: string }>();
  const slug = params.slug;
  const projectId = params.projectId;

  const [catalog, setCatalog] = useState<ConnectorClass[]>([]);
  const [installs, setInstalls] = useState<ConnectorInstallation[]>([]);
  const [bindings, setBindings] = useState<ConnectorBinding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [openInstall, setOpenInstall] = useState<string | null>(null);

  const classById = useMemo(() => {
    const m = new Map<string, ConnectorClass>();
    for (const c of catalog) m.set(c.id, c);
    return m;
  }, [catalog]);

  const refresh = useCallback(async () => {
    try {
      const [cat, ins, bnd] = await Promise.all([
        connectorsApi.catalog(),
        connectorsApi.listInstallations(slug),
        connectorsApi.listBindings(slug, projectId),
      ]);
      setCatalog(cat);
      setInstalls(ins);
      setBindings(bnd);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setLoading(false);
    }
  }, [slug, projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const bindRows: BindRow[] = useMemo(() => {
    return bindings.map((b) => ({
      ...b,
      className: classById.get(b.class_id)?.name ?? b.class_id,
      instanceLabel: b.instance_label,
    }));
  }, [bindings, classById]);

  const availableInstalls = useMemo(
    () => installs.filter((i) => i.status === "installed" || i.status === "pending"),
    [installs],
  );

  const onBind = useCallback(
    async (install: ConnectorInstallation, instanceRef: string, instanceLabel: string) => {
      setBusy(install.id);
      try {
        await connectorsApi.bind(slug, projectId, install.id, instanceRef, instanceLabel);
        setOpenInstall(null);
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusy(null);
      }
    },
    [slug, projectId, refresh],
  );

  const onUnbind = useCallback(
    async (binding: ConnectorBinding) => {
      setBusy(binding.id);
      try {
        await connectorsApi.unbind(slug, projectId, binding.id);
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusy(null);
      }
    },
    [slug, projectId, refresh],
  );

  const onSync = useCallback(
    async (binding: ConnectorBinding) => {
      setBusy(binding.id);
      try {
        const result = await connectorsApi.syncBinding(slug, projectId, binding.id);
        setError(
          `Sync complete: ${result.files_added} added, ${result.files_updated} updated, ${result.files_removed} removed.`,
        );
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusy(null);
      }
    },
    [slug, projectId, refresh],
  );

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-5xl px-8 py-8 text-sm text-muted-foreground">
        <Loader2 className="mr-2 inline size-4 animate-spin" aria-hidden="true" />
        Loading connectors
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 px-8 py-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Connectors</h1>
        <p className="text-sm text-muted-foreground">
          Pick which resources this project pulls from each installed connector.
        </p>
      </header>

      {error ? (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 size-4" aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Active bindings
        </h2>
        {bindRows.length === 0 ? (
          <p className="rounded-md border border-dashed border-border bg-surface p-6 text-sm text-muted-foreground">
            No connector bindings on this project yet.
          </p>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
            {bindRows.map((b) => (
              <li
                key={b.id}
                className="flex items-center gap-4 bg-surface px-4 py-3 text-sm"
              >
                <Plug className="size-4 text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-foreground">
                    {b.className} <span className="text-muted-foreground">/ {b.instanceLabel}</span>
                  </p>
                  <p className="truncate text-xs text-muted-foreground">{b.instance_ref}</p>
                </div>
                <button
                  type="button"
                  onClick={() => onSync(b)}
                  disabled={busy === b.id}
                  className="inline-flex items-center gap-1 rounded-md bg-foreground px-2.5 py-1 text-xs font-medium text-background hover:bg-foreground/85 disabled:opacity-50"
                >
                  {busy === b.id ? (
                    <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                  ) : (
                    <RefreshCw className="size-3" aria-hidden="true" />
                  )}
                  Sync now
                </button>
                <button
                  type="button"
                  onClick={() => onUnbind(b)}
                  disabled={busy === b.id}
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-foreground hover:bg-surface-hover disabled:opacity-50"
                >
                  <Trash2 className="size-3" aria-hidden="true" />
                  Unbind
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Available org installations
        </h2>
        {availableInstalls.length === 0 ? (
          <p className="rounded-md border border-dashed border-border bg-surface p-6 text-sm text-muted-foreground">
            No connectors installed at the org level yet. An admin must install a connector
            from the org Integrations page first.
          </p>
        ) : (
          <ul className="space-y-2">
            {availableInstalls.map((install) => {
              const cls = classById.get(install.class_id);
              if (!cls) return null;
              return (
                <li
                  key={install.id}
                  className="rounded-md border border-border bg-surface p-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-foreground">{cls.name}</p>
                      <p className="text-xs text-muted-foreground">{cls.vendor}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setOpenInstall((cur) => (cur === install.id ? null : install.id))
                      }
                      className="rounded-md bg-foreground px-2.5 py-1 text-xs font-medium text-background hover:bg-foreground/85"
                    >
                      {openInstall === install.id ? "Cancel" : "Bind resource"}
                    </button>
                  </div>
                  {openInstall === install.id ? (
                    <BindForm
                      slug={slug}
                      classId={install.class_id}
                      placeholder={cls.instance_label}
                      busy={busy === install.id}
                      onSubmit={(ref, label) => onBind(install, ref, label)}
                    />
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function BindForm({
  slug,
  classId,
  placeholder,
  busy,
  onSubmit,
}: {
  slug: string;
  classId: string;
  placeholder: string;
  busy: boolean;
  onSubmit: (instanceRef: string, instanceLabel: string) => void;
}) {
  const [ref, setRef] = useState("");
  const [label, setLabel] = useState("");
  const [options, setOptions] = useState<
    { ref: string; label: string; hint: string | null }[]
  >([]);
  const [loadingOptions, setLoadingOptions] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoadingOptions(true);
    connectorsApi
      .listInstances(slug, classId)
      .then((rows) => {
        if (!cancelled) setOptions(rows);
      })
      .catch(() => {
        // Silent fallback to free-form input.
      })
      .finally(() => {
        if (!cancelled) setLoadingOptions(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, classId]);

  return (
    <form
      className="mt-3 space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (!ref.trim() || !label.trim()) return;
        onSubmit(ref.trim(), label.trim());
      }}
    >
      {loadingOptions ? (
        <p className="text-xs text-muted-foreground">
          <Loader2 className="mr-1 inline size-3 animate-spin" aria-hidden="true" />
          Loading available {placeholder.toLowerCase()}s
        </p>
      ) : options.length > 0 ? (
        <label className="space-y-1 text-xs text-muted-foreground">
          <span>Pick a {placeholder.toLowerCase()}</span>
          <select
            value={ref}
            onChange={(e) => {
              const next = e.target.value;
              setRef(next);
              const found = options.find((o) => o.ref === next);
              if (found) setLabel(found.label);
            }}
            className="block w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-foreground"
            required
          >
            <option value="">{`Select ${placeholder.toLowerCase()}`}</option>
            {options.map((o) => (
              <option key={o.ref} value={o.ref}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <label className="space-y-1 text-xs text-muted-foreground">
            <span>{placeholder} identifier</span>
            <input
              value={ref}
              onChange={(e) => setRef(e.target.value)}
              placeholder="e.g. workspace-id, library-guid, channel-id"
              className="block w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-foreground"
              required
            />
          </label>
          <label className="space-y-1 text-xs text-muted-foreground">
            <span>Display label</span>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="What the team will see"
              className="block w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-foreground"
              required
            />
          </label>
        </div>
      )}
      <button
        type="submit"
        disabled={busy || !ref.trim() || !label.trim()}
        className="inline-flex items-center gap-1 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/85 disabled:opacity-50"
      >
        {busy ? (
          <Loader2 className="size-3 animate-spin" aria-hidden="true" />
        ) : (
          <Plug className="size-3" aria-hidden="true" />
        )}
        Bind
      </button>
    </form>
  );
}
