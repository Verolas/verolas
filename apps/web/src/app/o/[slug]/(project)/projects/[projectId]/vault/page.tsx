"use client";

import {
  AlertCircle,
  FileText,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { FileUploader, fileTypeLabel } from "@/components/file-uploader";
import { ApiError, projectFilesApi, type ProjectFile } from "@/lib/api";

const TYPE_ACCEPT: Record<string, string> = {
  drawing: ".dwg,.dxf,.ifc,.pdf",
  model: ".rvt,.ifc,.nwd,.skp,.3dm",
  calc: ".xlsx,.xlsm,.csv,.xls",
  document: ".pdf,.docx,.doc,.txt,.md",
};

export default function VaultPage() {
  const params = useParams<{ slug: string; projectId: string }>();
  const slug = params.slug;
  const projectId = params.projectId;

  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await projectFilesApi.list(slug, projectId);
      setFiles(list);
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

  const grouped = useMemo(() => {
    const out: Record<string, ProjectFile[]> = {};
    for (const f of files) {
      const bucket = bucketFor(f.kind);
      (out[bucket] ?? (out[bucket] = [])).push(f);
    }
    return out;
  }, [files]);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-8 py-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-normal tracking-tight text-foreground">Vault</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Every file on this project, versioned and audit-logged.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-foreground hover:bg-surface-hover"
        >
          <RefreshCw className="size-3.5" aria-hidden="true" />
          Refresh
        </button>
      </header>

      {error ? (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 size-4" aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      <FileUploader slug={slug} projectId={projectId} onUploaded={refresh} />

      <section>
        <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Upload by type
        </h2>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(["drawing", "model", "calc", "document"] as const).map((kind) => (
            <div
              key={kind}
              className="rounded-md border border-border bg-surface p-3"
            >
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {kind === "calc" ? "Calculations" : `${capitalize(kind)}s`}
              </p>
              <div className="mt-2">
                <FileUploader
                  inline
                  slug={slug}
                  projectId={projectId}
                  accept={TYPE_ACCEPT[kind] ?? ""}
                  onUploaded={refresh}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        {loading ? (
          <p className="text-sm text-muted-foreground">
            <Loader2 className="mr-1.5 inline size-3.5 animate-spin" aria-hidden="true" />
            Loading vault
          </p>
        ) : files.length === 0 ? (
          <p className="rounded-md border border-dashed border-border bg-surface p-6 text-sm text-muted-foreground">
            The vault is empty. Drop a file above to add one.
          </p>
        ) : (
          (["Drawings", "Models", "Calculations", "Documents", "Other"] as const).map(
            (label) => {
              const rows = grouped[label] ?? [];
              if (rows.length === 0) return null;
              return (
                <div key={label} className="space-y-2">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {label}
                  </h3>
                  <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
                    {rows.map((f) => (
                      <FileRow key={f.id} file={f} />
                    ))}
                  </ul>
                </div>
              );
            },
          )
        )}
      </section>
    </div>
  );
}

function FileRow({ file }: { file: ProjectFile }) {
  return (
    <li className="flex items-center gap-3 bg-surface px-4 py-2 text-sm">
      <FileIcon kind={file.kind} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-foreground">{file.filename}</p>
        <p className="text-xs text-muted-foreground">
          {fileTypeLabel(file.kind)}
          {file.size_bytes ? ` · ${humanSize(file.size_bytes)}` : ""}
          {" · "}
          {new Date(file.created_at).toLocaleString()}
        </p>
      </div>
      <FileStatus file={file} />
    </li>
  );
}

function FileIcon({ kind }: { kind: ProjectFile["kind"] }) {
  if (kind === "image")
    return <ImageIcon className="size-4 text-muted-foreground" aria-hidden="true" />;
  return <FileText className="size-4 text-muted-foreground" aria-hidden="true" />;
}

function FileStatus({ file }: { file: ProjectFile }) {
  if (file.status === "ready" && file.scan_verdict === "clean") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-300">
        <ShieldCheck className="size-3" aria-hidden="true" />
        Ready
      </span>
    );
  }
  if (file.status === "uploading") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
        <Loader2 className="size-3 animate-spin" aria-hidden="true" />
        Uploading
      </span>
    );
  }
  if (file.status === "scanning") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-300">
        <Loader2 className="size-3 animate-spin" aria-hidden="true" />
        Scanning
      </span>
    );
  }
  return (
    <span className="text-[11px] text-muted-foreground capitalize">{file.status}</span>
  );
}

function bucketFor(kind: ProjectFile["kind"]): string {
  switch (kind) {
    case "cad_drawing":
      return "Drawings";
    case "cad_bim":
      return "Models";
    case "spreadsheet_plain":
    case "office_macro":
      return "Calculations";
    case "office_plain":
    case "pdf":
      return "Documents";
    default:
      return "Other";
  }
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
