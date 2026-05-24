"use client";

import {
  AlertCircle,
  ArrowLeft,
  CloudUpload,
  FileText,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  libraryApi,
  type LibraryFile,
  type PresignedUpload,
} from "@/lib/api";

type UploadState = "queued" | "presigning" | "uploading" | "done" | "error";

interface UploadItem {
  id: string;
  file: File;
  state: UploadState;
  error?: string;
}

export default function LibraryFolderPage() {
  const params = useParams<{ slug: string; folderId: string }>();
  const slug = params.slug;
  const folderId = params.folderId;

  const [files, setFiles] = useState<LibraryFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await libraryApi.listFiles(slug, folderId);
      setFiles(list);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setLoading(false);
    }
  }, [slug, folderId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleFiles = useCallback(
    (list: FileList | File[]) => {
      const incoming = Array.from(list);
      if (incoming.length === 0) return;
      const next: UploadItem[] = incoming.map((f, i) => ({
        id: `${Date.now()}-${i}-${f.name}`,
        file: f,
        state: "queued",
      }));
      setUploads((prev) => [...next, ...prev]);
      void Promise.all(next.map((u) => uploadOne(u, slug, folderId, setUploads))).then(() =>
        refresh(),
      );
    },
    [slug, folderId, refresh],
  );

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <Link
        href={`/o/${slug}/library`}
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3" aria-hidden="true" />
        Back to Library
      </Link>

      <header>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">
          Folder contents
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Files added here can be mounted into any project via Connectors.
        </p>
      </header>

      {error ? (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 size-4" aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      <div
        className={`relative flex flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed bg-surface px-8 py-10 text-center transition-colors ${
          dragging ? "border-foreground bg-surface-hover" : "border-border"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
      >
        <CloudUpload className="size-7 text-muted-foreground" aria-hidden="true" />
        <div className="space-y-0.5">
          <p className="text-sm font-medium text-foreground">Drop files to upload</p>
          <p className="text-xs text-muted-foreground">or click to pick</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          onChange={(e) => {
            if (e.target.files) handleFiles(e.target.files);
            e.target.value = "";
          }}
          className="absolute h-0 w-0 opacity-0"
          aria-hidden="true"
          tabIndex={-1}
        />
      </div>

      {uploads.length > 0 ? (
        <ul className="space-y-1.5">
          {uploads.map((u) => (
            <li
              key={u.id}
              className="flex items-center gap-3 rounded-md border border-border bg-surface px-3 py-2 text-xs"
            >
              <FileText className="size-3.5 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-foreground">{u.file.name}</span>
              <span className="text-muted-foreground">
                {u.state === "uploading" || u.state === "presigning" ? (
                  <Loader2 className="inline size-3 animate-spin" aria-hidden="true" />
                ) : u.state === "done" ? (
                  "Uploaded"
                ) : u.state === "error" ? (
                  <span className="text-destructive">{u.error ?? "Failed"}</span>
                ) : (
                  "Queued"
                )}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <section>
        <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Files
        </h2>
        {loading ? (
          <p className="mt-3 text-sm text-muted-foreground">
            <Loader2 className="mr-1.5 inline size-3.5 animate-spin" aria-hidden="true" />
            Loading
          </p>
        ) : files.length === 0 ? (
          <p className="mt-3 rounded-md border border-dashed border-border bg-surface p-6 text-sm text-muted-foreground">
            This folder is empty.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-border overflow-hidden rounded-md border border-border">
            {files.map((f) => (
              <li key={f.id} className="flex items-center gap-3 bg-surface px-4 py-2 text-sm">
                <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-foreground">{f.filename}</p>
                  <p className="text-xs text-muted-foreground">
                    {f.kind}
                    {f.size_bytes ? ` · ${humanSize(f.size_bytes)}` : ""}
                    {" · "}
                    {new Date(f.created_at).toLocaleString()}
                  </p>
                </div>
                <span className="text-[11px] text-muted-foreground capitalize">
                  {f.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

async function uploadOne(
  item: UploadItem,
  slug: string,
  folderId: string,
  setItems: React.Dispatch<React.SetStateAction<UploadItem[]>>,
): Promise<void> {
  const setState = (next: UploadState, error?: string) =>
    setItems((prev) =>
      prev.map((p) => {
        if (p.id !== item.id) return p;
        const updated: UploadItem = { ...p, state: next };
        if (error !== undefined) updated.error = error;
        return updated;
      }),
    );

  try {
    setState("presigning");
    const res = await libraryApi.uploadFile(slug, folderId, {
      filename: item.file.name,
      content_type: item.file.type || null,
      size_bytes: item.file.size,
    });
    const upload = res.single_part_upload;
    if (!upload) {
      throw new Error("Multipart upload not implemented in the UI yet.");
    }
    setState("uploading");
    await uploadToObjectStore(upload, item.file);
    setState("done");
  } catch (err) {
    setState("error", err instanceof ApiError ? err.detail : (err as Error).message);
  }
}

async function uploadToObjectStore(upload: PresignedUpload, file: File): Promise<void> {
  const response = await fetch(upload.url, {
    method: upload.method,
    headers: upload.headers,
    body: file,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Object store rejected upload (${response.status}): ${text}`);
  }
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}
