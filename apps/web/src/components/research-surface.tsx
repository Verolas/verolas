"use client";

import { BookOpen, Filter, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import {
  CLAUSES,
  CODES,
  type CodeId,
  type ClauseStub,
  type CodeMeta,
  searchClauses,
} from "@/lib/research-data";

interface Props {
  /** When provided, the surface starts scoped to these codes
   *  (the project's pinned code set). An escape hatch toggles to all codes. */
  scopedCodeIds?: CodeId[];
  scopeLabel?: string;
}

export function ResearchSurface({ scopedCodeIds, scopeLabel }: Props) {
  const [query, setQuery] = useState("");
  const [allCodes, setAllCodes] = useState(scopedCodeIds === undefined);
  const [activeCode, setActiveCode] = useState<CodeId | null>(null);

  const effectiveScope = useMemo<CodeId[] | undefined>(() => {
    if (allCodes) return undefined;
    return scopedCodeIds;
  }, [allCodes, scopedCodeIds]);

  const hits = useMemo(
    () => searchClauses(query, effectiveScope),
    [query, effectiveScope],
  );

  const filteredCodes = useMemo<CodeMeta[]>(() => {
    if (!effectiveScope) return CODES;
    return CODES.filter((c) => effectiveScope.includes(c.id));
  }, [effectiveScope]);

  return (
    <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
      <aside className="space-y-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Scope
          </div>
          {scopedCodeIds && (
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                aria-pressed={!allCodes}
                onClick={() => setAllCodes(false)}
                className={`rounded-full border px-2 py-0.5 text-[11px] ${
                  !allCodes
                    ? "border-primary bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground"
                    : "border-border text-muted-foreground hover:bg-surface-hover"
                }`}
              >
                {scopeLabel ?? "Project codes"}
              </button>
              <button
                type="button"
                aria-pressed={allCodes}
                onClick={() => setAllCodes(true)}
                className={`rounded-full border px-2 py-0.5 text-[11px] ${
                  allCodes
                    ? "border-primary bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground"
                    : "border-border text-muted-foreground hover:bg-surface-hover"
                }`}
              >
                All codes
              </button>
            </div>
          )}
        </div>

        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Codes
          </div>
          <ul className="mt-1.5 space-y-0.5">
            {filteredCodes.map((code) => {
              const active = code.id === activeCode;
              const clauseCount = CLAUSES.filter((c) => c.codeId === code.id).length;
              return (
                <li key={code.id}>
                  <button
                    type="button"
                    onClick={() => setActiveCode(active ? null : code.id)}
                    aria-pressed={active}
                    className={`flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-xs ${
                      active
                        ? "bg-muted text-foreground"
                        : "text-muted-foreground hover:bg-surface-hover hover:text-foreground"
                    }`}
                  >
                    <span className="flex-1 truncate">
                      <span className="font-mono text-foreground">{code.short}</span>
                      <span className="ml-1.5 text-muted-foreground">— {code.title}</span>
                    </span>
                    <span className="rounded bg-muted px-1 font-mono text-[10px] text-muted-foreground">
                      {clauseCount}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>

      <div className="space-y-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search clauses, topics, or formulas"
            className="pl-8"
          />
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Filter className="size-3" aria-hidden="true" />
          {hits.length} clause{hits.length === 1 ? "" : "s"} matching
          {effectiveScope && !allCodes ? " in pinned codes" : " across all codes"}
        </div>

        <ul className="space-y-2">
          {hits
            .filter((c) => (activeCode ? c.codeId === activeCode : true))
            .map((clause) => (
              <ClauseCard key={`${clause.codeId}-${clause.number}`} clause={clause} />
            ))}
        </ul>

        {hits.length === 0 && (
          <div className="rounded-md border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
            No clauses matched. Widen the scope or try a different keyword.
          </div>
        )}
      </div>
    </div>
  );
}

function ClauseCard({ clause }: { clause: ClauseStub }) {
  const code = CODES.find((c) => c.id === clause.codeId);
  return (
    <li className="rounded-md border border-border bg-surface p-3 hover:bg-surface-hover">
      <div className="flex items-start gap-2">
        <BookOpen className="mt-0.5 size-3.5 text-primary" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-muted-foreground">{code?.short}</span>
            <span className="font-mono text-[11px] text-foreground">§{clause.number}</span>
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
              {clause.topic}
            </span>
          </div>
          <div className="mt-1 text-sm font-medium text-foreground">{clause.title}</div>
          <p className="mt-1 text-xs text-foreground-light">{clause.summary}</p>
        </div>
      </div>
    </li>
  );
}
