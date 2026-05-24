"use client";

import { ArrowUpRight, Network, X } from "lucide-react";
import { useEffect, useState } from "react";

import { NetworkGraph, buildProjectGraph } from "@/components/network-graph";
import type { AgentRun } from "@/lib/api";

interface Props {
  projectName: string;
  runs: AgentRun[];
}

export function NetworkGraphCard({ projectName, runs }: Props) {
  const data = buildProjectGraph(projectName, runs);
  const affected = data.nodes.filter((n) => n.affected).length;
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function onEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [open]);

  return (
    <>
      <section className="rounded-md border border-border bg-surface p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Network className="size-4 text-primary" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-foreground">Network graph</h2>
          </div>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            Open full graph
            <ArrowUpRight className="size-3" aria-hidden="true" />
          </button>
        </div>
        <p className="text-xs text-foreground-light">
          {affected > 0
            ? `${affected} element${affected === 1 ? "" : "s"} affected by the last input change.`
            : "Every project element and the dependencies between them."}
        </p>
        <div className="mt-3 overflow-hidden rounded border border-border bg-muted/20">
          <NetworkGraph nodes={data.nodes} links={data.links} compact />
        </div>
      </section>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-40 flex items-stretch bg-background/90 p-4 backdrop-blur sm:p-6"
        >
          <div className="flex w-full flex-col overflow-hidden rounded-lg border border-border bg-surface shadow-lg">
            <div className="flex h-12 items-center justify-between border-b border-border px-4">
              <div className="flex items-center gap-2">
                <Network className="size-4 text-primary" aria-hidden="true" />
                <span className="text-sm font-semibold text-foreground">
                  Network graph · {projectName}
                </span>
              </div>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setOpen(false)}
                className="grid size-8 place-items-center rounded-md text-muted-foreground hover:bg-surface-hover hover:text-foreground"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <NetworkGraph nodes={data.nodes} links={data.links} />
            </div>
            <div className="border-t border-border p-3 text-xs text-muted-foreground">
              Drag a node to explore. Red rings show what just changed. Edges:
              <span className="ml-2 font-mono">produces</span>,
              <span className="ml-2 font-mono">cites</span>,
              <span className="ml-2 font-mono">depends-on</span>,
              <span className="ml-2 font-mono">verified-by</span>.
            </div>
          </div>
        </div>
      )}
    </>
  );
}
