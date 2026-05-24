"use client";

/**
 * Drag-and-drop uploader bound to the project-scoped /files endpoint.
 *
 * 1. POST /v1/orgs/{slug}/projects/{projectId}/files/ to mint a presigned PUT
 *    and write the initial DB row in 'uploading' state.
 * 2. PUT the file bytes straight to the object store.
 * 3. Surface upload progress + errors per file.
 *
 * The "complete" + clamd scan step lives behind a later endpoint and is not
 * yet wired; uploads land as `uploading` rows that ingest can pick up.
 */

import { CloudUpload, FileText, Loader2, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import {
  ApiError,
  projectFilesApi,
  type PresignedUpload,
  type ProjectFile,
} from "@/lib/api";

type UploadState = "queued" | "presigning" | "uploading" | "done" | "error";

interface Item {
  id: string;
  file: File;
  state: UploadState;
  error?: string;
}

interface Props {
  slug: string;
  projectId: string;
  /** Pre-filter dropped files (e.g. only DWG). Returns truthy to accept. */
  accept?: string;
  /** Called once files have been picked successfully to refresh upstream lists. */
  onUploaded?: () => void;
  /** Tight inline rendering for per-type Upload buttons. */
  inline?: boolean;
}

export function FileUploader({ slug, projectId, accept, onUploaded, inline }: Props) {
  const [items, setItems] = useState<Item[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleFiles = useCallback(
    (files: FileList | File[]) => {
      const list = Array.from(files);
      if (list.length === 0) return;
      const next: Item[] = list.map((f, i) => ({
        id: `${Date.now()}-${i}-${f.name}`,
        file: f,
        state: "queued",
      }));
      setItems((prev) => [...next, ...prev]);

      void Promise.all(next.map((item) => uploadOne(item, slug, projectId, setItems))).then(
        () => onUploaded?.(),
      );
    },
    [slug, projectId, onUploaded],
  );

  const onDrop: React.DragEventHandler<HTMLDivElement> = useCallback(
    (event) => {
      event.preventDefault();
      setDragging(false);
      handleFiles(event.dataTransfer.files);
    },
    [handleFiles],
  );

  const cls = inline
    ? "inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-1.5 text-xs text-foreground hover:bg-surface-hover cursor-pointer"
    : `relative flex flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed bg-surface px-8 py-12 text-center transition-colors ${
        dragging ? "border-foreground bg-surface-hover" : "border-border"
      }`;

  return (
    <div className="space-y-3">
      <div
        className={cls}
        onDragOver={(e) => {
          e.preventDefault();
          if (!inline) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
      >
        {inline ? (
          <>
            <CloudUpload className="size-3.5" aria-hidden="true" />
            Upload
          </>
        ) : (
          <>
            <CloudUpload className="size-7 text-muted-foreground" aria-hidden="true" />
            <div className="space-y-0.5">
              <p className="text-sm font-medium text-foreground">
                Drop files anywhere on this page
              </p>
              <p className="text-xs text-muted-foreground">
                or click to pick from your computer
              </p>
            </div>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          onChange={(e) => {
            if (e.target.files) handleFiles(e.target.files);
            e.target.value = "";
          }}
          className="absolute h-0 w-0 opacity-0"
          aria-hidden="true"
          tabIndex={-1}
        />
      </div>

      {items.length > 0 ? (
        <ul className="space-y-1.5">
          {items.map((item) => (
            <UploadRow
              key={item.id}
              item={item}
              onDismiss={() =>
                setItems((prev) => prev.filter((p) => p.id !== item.id))
              }
            />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function UploadRow({ item, onDismiss }: { item: Item; onDismiss: () => void }) {
  return (
    <li className="flex items-center gap-3 rounded-md border border-border bg-surface px-3 py-2 text-xs">
      <FileText className="size-3.5 text-muted-foreground" aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate text-foreground">{item.file.name}</span>
      <span className="text-muted-foreground">
        {item.state === "queued" || item.state === "presigning" ? "Preparing" : null}
        {item.state === "uploading" ? (
          <Loader2 className="inline size-3 animate-spin" aria-hidden="true" />
        ) : null}
        {item.state === "done" ? "Uploaded" : null}
        {item.state === "error" ? (
          <span className="text-destructive">{item.error ?? "Failed"}</span>
        ) : null}
      </span>
      <button
        type="button"
        onClick={onDismiss}
        className="text-muted-foreground hover:text-foreground"
        aria-label="Dismiss"
      >
        <X className="size-3.5" aria-hidden="true" />
      </button>
    </li>
  );
}

async function uploadOne(
  item: Item,
  slug: string,
  projectId: string,
  setItems: React.Dispatch<React.SetStateAction<Item[]>>,
): Promise<void> {
  const setState = (next: UploadState, error?: string) =>
    setItems((prev) =>
      prev.map((p) => {
        if (p.id !== item.id) return p;
        const updated: Item = { ...p, state: next };
        if (error !== undefined) updated.error = error;
        return updated;
      }),
    );

  try {
    setState("presigning");
    const res = await projectFilesApi.initiateUpload(slug, projectId, {
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

export function fileTypeLabel(kind: ProjectFile["kind"]): string {
  switch (kind) {
    case "cad_drawing":
      return "Drawing";
    case "cad_bim":
      return "BIM";
    case "spreadsheet_plain":
      return "Spreadsheet";
    case "office_macro":
      return "Office (macro)";
    case "office_plain":
      return "Document";
    case "pdf":
      return "PDF";
    case "image":
      return "Image";
    case "archive":
      return "Archive";
    default:
      return "File";
  }
}
