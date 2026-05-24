"use client";

import { AlertCircle, FolderPlus, Loader2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ApiError, libraryApi, type LibraryFolder } from "@/lib/api";

export default function LibraryPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const [folders, setFolders] = useState<LibraryFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [showForm, setShowForm] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const list = await libraryApi.listFolders(slug);
      setFolders(list);
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

  const onCreate = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!name.trim()) return;
      setCreating(true);
      try {
        await libraryApi.createFolder(slug, name.trim(), description.trim() || undefined);
        setName("");
        setDescription("");
        setShowForm(false);
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setCreating(false);
      }
    },
    [slug, name, description, refresh],
  );

  const onDelete = useCallback(
    async (folder: LibraryFolder) => {
      if (!confirm(`Delete folder "${folder.name}"? Files in it will be unlinked.`)) return;
      try {
        await libraryApi.deleteFolder(slug, folder.id);
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
          <h1 className="text-2xl font-normal tracking-tight text-foreground">Library</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Shared firm content: standard details, calc templates, reference clauses,
            master specs. Mount any folder into a project from its Connectors page.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          className="inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/85"
        >
          <FolderPlus className="size-3.5" aria-hidden="true" />
          {showForm ? "Cancel" : "New folder"}
        </button>
      </header>

      {error ? (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="mt-0.5 size-4" aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}

      {showForm ? (
        <form
          onSubmit={onCreate}
          className="space-y-3 rounded-md border border-border bg-surface p-4"
        >
          <label className="space-y-1 text-xs text-muted-foreground">
            <span>Folder name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. EN 1992 reference clauses"
              className="block w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-foreground"
              required
              maxLength={200}
            />
          </label>
          <label className="space-y-1 text-xs text-muted-foreground">
            <span>Description (optional)</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="block w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground outline-none focus:border-foreground"
              maxLength={2000}
            />
          </label>
          <button
            type="submit"
            disabled={creating || !name.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/85 disabled:opacity-50"
          >
            {creating ? (
              <Loader2 className="size-3 animate-spin" aria-hidden="true" />
            ) : null}
            Create
          </button>
        </form>
      ) : null}

      {loading ? (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1.5 inline size-3.5 animate-spin" aria-hidden="true" />
          Loading folders
        </p>
      ) : folders.length === 0 ? (
        <p className="rounded-md border border-dashed border-border bg-surface p-8 text-center text-sm text-muted-foreground">
          No folders yet. Create one to start uploading shared content.
        </p>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {folders.map((f) => (
            <li key={f.id} className="rounded-md border border-border bg-surface p-4">
              <div className="flex items-start justify-between gap-2">
                <Link
                  href={`/o/${slug}/library/${f.id}`}
                  className="min-w-0 flex-1 text-sm font-medium text-foreground hover:underline"
                >
                  {f.name}
                </Link>
                <button
                  type="button"
                  onClick={() => onDelete(f)}
                  className="text-muted-foreground hover:text-destructive"
                  aria-label="Delete folder"
                >
                  <Trash2 className="size-3.5" aria-hidden="true" />
                </button>
              </div>
              {f.description ? (
                <p className="mt-1 text-xs text-foreground-light line-clamp-2">
                  {f.description}
                </p>
              ) : null}
              <p className="mt-3 text-[11px] text-muted-foreground">
                {f.file_count} file{f.file_count === 1 ? "" : "s"}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
