"use client";

import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Cpu,
  Loader2,
  Trash2,
  XCircle,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  bridgesApi,
  type Bridge,
  type BridgeEnrollResult,
} from "@/lib/api";

const TIER_C_TOOLS: { id: string; name: string }[] = [
  { id: "sofistik", name: "SOFiSTiK" },
  { id: "dlubal-rfem", name: "Dlubal RFEM / RSTAB" },
  { id: "csi-suite", name: "SAP2000 / ETABS" },
  { id: "staad", name: "STAAD.Pro" },
  { id: "idea-statica", name: "IDEA StatiCa" },
  { id: "plaxis", name: "Plaxis" },
  { id: "tekla", name: "Tekla Structures" },
  { id: "bentley-projectwise", name: "Bentley ProjectWise" },
  { id: "rhino", name: "Rhino + Grasshopper" },
  { id: "d-trust-qes", name: "D-Trust QES" },
];

export default function BridgesPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const [bridges, setBridges] = useState<Bridge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showEnroll, setShowEnroll] = useState(false);
  const [enrolled, setEnrolled] = useState<BridgeEnrollResult | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await bridgesApi.list(slug);
      setBridges(list);
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

  const onRevoke = useCallback(
    async (bridge: Bridge) => {
      if (!confirm(`Revoke ${bridge.name}? Any pending jobs will be cancelled.`)) return;
      try {
        await bridgesApi.revoke(slug, bridge.id);
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      }
    },
    [slug, refresh],
  );

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-normal tracking-tight text-foreground">
            Bridge agents
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Bridge agents connect Verolas to engineering software running on your
            internal workstations: SOFiSTiK, RFEM, Tekla, Plaxis, SAP2000, and
            similar. One bridge can serve multiple tools.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowEnroll(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/85"
        >
          <Cpu className="size-3.5" aria-hidden="true" />
          Enroll bridge
        </button>
      </header>

      {error ? (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 size-4" aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      {loading ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1.5 inline size-3.5 animate-spin" aria-hidden="true" />
          Loading bridges
        </p>
      ) : bridges.length === 0 ? (
        <p className="rounded-md border border-dashed border-border bg-surface p-8 text-center text-sm text-muted-foreground">
          No bridges yet. Enroll one to wire up on-prem tools.
        </p>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
          {bridges.map((b) => (
            <BridgeRow key={b.id} bridge={b} onRevoke={() => onRevoke(b)} />
          ))}
        </ul>
      )}

      {showEnroll ? (
        <EnrollModal
          slug={slug}
          onClose={() => {
            setShowEnroll(false);
            setEnrolled(null);
            void refresh();
          }}
          onEnrolled={setEnrolled}
          enrolled={enrolled}
        />
      ) : null}
    </div>
  );
}

function BridgeRow({ bridge, onRevoke }: { bridge: Bridge; onRevoke: () => void }) {
  return (
    <li className="flex items-center gap-4 bg-surface px-4 py-3 text-sm">
      <BridgeStatusIcon status={bridge.status} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-foreground">{bridge.name}</p>
        <p className="truncate text-xs text-muted-foreground">
          {bridge.supported_tools.length > 0
            ? bridge.supported_tools.join(", ")
            : "No tools declared"}
          {bridge.hostname ? ` · ${bridge.hostname}` : ""}
          {bridge.last_seen_at
            ? ` · last seen ${relativeTime(bridge.last_seen_at)}`
            : " · never seen"}
        </p>
      </div>
      <button
        type="button"
        onClick={onRevoke}
        className="inline-flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-foreground hover:bg-surface-hover"
      >
        <Trash2 className="size-3" aria-hidden="true" />
        Revoke
      </button>
    </li>
  );
}

function BridgeStatusIcon({ status }: { status: Bridge["status"] }) {
  if (status === "active") {
    return <CheckCircle2 className="size-4 text-emerald-500" aria-hidden="true" />;
  }
  if (status === "pending") {
    return <Clock className="size-4 text-amber-500" aria-hidden="true" />;
  }
  if (status === "revoked") {
    return <XCircle className="size-4 text-destructive" aria-hidden="true" />;
  }
  return <Cpu className="size-4 text-muted-foreground" aria-hidden="true" />;
}

function EnrollModal({
  slug,
  onClose,
  onEnrolled,
  enrolled,
}: {
  slug: string;
  onClose: () => void;
  onEnrolled: (result: BridgeEnrollResult) => void;
  enrolled: BridgeEnrollResult | null;
}) {
  const [name, setName] = useState("");
  const [tools, setTools] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const onSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!name.trim()) return;
      setBusy(true);
      try {
        const result = await bridgesApi.enroll(slug, name.trim(), Array.from(tools));
        onEnrolled(result);
        setModalError(null);
      } catch (err) {
        setModalError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setBusy(false);
      }
    },
    [slug, name, tools, onEnrolled],
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-md border border-border bg-surface shadow-lg">
        <header className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-base font-medium text-foreground">
            {enrolled ? "Bridge enrolled" : "Enroll a new bridge"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <XCircle className="size-5" aria-hidden="true" />
          </button>
        </header>

        {enrolled ? (
          <EnrolledView enrolled={enrolled} onClose={onClose} />
        ) : (
          <form onSubmit={onSubmit} className="space-y-4 p-5">
            <label className="block space-y-1 text-xs text-muted-foreground">
              <span>Bridge name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Munich office calc box"
                className="block w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-foreground"
                required
                maxLength={200}
              />
            </label>
            <fieldset className="space-y-1.5 text-xs">
              <legend className="text-muted-foreground">
                Tools this bridge will serve (optional, can change later)
              </legend>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {TIER_C_TOOLS.map((t) => {
                  const on = tools.has(t.id);
                  return (
                    <label
                      key={t.id}
                      className={`flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 ${
                        on
                          ? "border-foreground bg-surface-hover"
                          : "border-border bg-surface"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={on}
                        onChange={() => {
                          const next = new Set(tools);
                          if (on) next.delete(t.id);
                          else next.add(t.id);
                          setTools(next);
                        }}
                        className="size-3"
                      />
                      <span className="text-foreground">{t.name}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
            {modalError ? (
              <p className="text-xs text-destructive">{modalError}</p>
            ) : null}
            <button
              type="submit"
              disabled={busy || !name.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/85 disabled:opacity-50"
            >
              {busy ? (
                <Loader2 className="size-3 animate-spin" aria-hidden="true" />
              ) : null}
              Enroll
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

function EnrolledView({
  enrolled,
  onClose,
}: {
  enrolled: BridgeEnrollResult;
  onClose: () => void;
}) {
  const dockerCmd =
    `docker run -d --name verolas-bridge --restart=unless-stopped \\\n` +
    `  -e VEROLAS_BRIDGE_TOKEN='${enrolled.token}' \\\n` +
    `  -e VEROLAS_BRIDGE_API_BASE_URL='${enrolled.api_base_url}' \\\n` +
    `  ghcr.io/verolas/bridge:latest`;
  return (
    <div className="space-y-4 p-5 text-sm">
      <p className="text-foreground-light">
        Bridge <span className="font-medium text-foreground">{enrolled.name}</span> is
        ready. Below is the one-time enrollment token. Paste it into the bridge
        host before closing this dialog — it is not shown again.
      </p>
      <section className="space-y-1">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Token
        </p>
        <code className="block break-all rounded-md border border-border bg-background p-2 text-xs text-foreground">
          {enrolled.token}
        </code>
      </section>
      <section className="space-y-1">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Quickstart (Docker)
        </p>
        <pre className="overflow-x-auto rounded-md border border-border bg-background p-3 text-[11px] text-foreground">
          {dockerCmd}
        </pre>
      </section>
      <p className="text-xs text-muted-foreground">
        Once the bridge starts polling, its status will flip to{" "}
        <span className="text-foreground">active</span> on this page.
      </p>
      <button
        type="button"
        onClick={onClose}
        className="inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/85"
      >
        Done
      </button>
    </div>
  );
}

function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}
