"use client";

import { ArrowRight, Sparkles } from "lucide-react";
import { useState } from "react";

const SUGGESTIONS = [
  "Review the latest structural calc package for sanity-check errors.",
  "Summarise unresolved reviewer comments on this project.",
  "What changed in the drawings since the last submission?",
  "Draft a clarification request for the missing geotech report.",
  "Find every project where the load combinations were not signed off.",
] as const;

export function AssistantPanelBody() {
  const [query, setQuery] = useState("");
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start gap-3 rounded-md border border-border bg-muted/30 p-3">
        <Sparkles className="mt-0.5 size-4 text-primary" aria-hidden="true" />
        <div className="text-xs text-foreground-light">
          The Verolas Assistant pulls from your project files, audit log, and reviewer
          findings. Answers cite the source so you can audit every claim.
        </div>
      </div>
      <div className="mt-4">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Try asking
        </div>
        <ul className="mt-2 space-y-1">
          {SUGGESTIONS.map((s) => (
            <li key={s}>
              <button
                type="button"
                onClick={() => setQuery(s)}
                className="flex w-full items-start gap-2 rounded-md px-2 py-2 text-left text-xs text-foreground hover:bg-surface-hover"
              >
                <span className="mt-0.5 size-1 shrink-0 rounded-full bg-muted-foreground" />
                <span className="flex-1">{s}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-auto pt-4">
        <form
          className="relative"
          onSubmit={(event) => {
            event.preventDefault();
            // wired up in a later wave
          }}
        >
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ask anything about this project..."
            className="h-10 w-full rounded-md border border-border bg-surface px-3 pr-10 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30"
          />
          <button
            type="submit"
            aria-label="Send"
            className="absolute right-1.5 top-1.5 grid size-7 place-items-center rounded-md bg-primary text-primary-foreground hover:bg-primary-hover"
          >
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </button>
        </form>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Powered by Verolas reviewers. Treat AI output as draft until a human reviewer signs
          off.
        </p>
      </div>
    </div>
  );
}
