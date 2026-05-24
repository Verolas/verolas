"use client";

/**
 * Force-directed network graph of project entities and their
 * dependencies. Uses react-force-graph-2d which wraps three-forcegraph
 * for the layout and renders to a canvas.
 *
 * Data is assembled from real /v1/me + /v1/orgs/.../projects/.../runs
 * results plus a handful of synthetic engineering edges (drawing
 * sheets, calc runs, code clauses) so the graph reads as a project
 * dependency web until the per-element schema lands.
 */

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";

import { type AgentRun } from "@/lib/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

export type GraphNodeType =
  | "project"
  | "run"
  | "drawing"
  | "model"
  | "calc"
  | "document"
  | "code-clause"
  | "reviewer";

export interface GraphNode {
  id: string;
  label: string;
  type: GraphNodeType;
  /** Highlight nodes that were affected by the most recent change. */
  affected?: boolean;
}

export interface GraphLink {
  source: string;
  target: string;
  kind: "produces" | "cites" | "depends-on" | "supersedes" | "verified-by";
}

interface Props {
  nodes: GraphNode[];
  links: GraphLink[];
  /** Smaller mini view used in Overview card. */
  compact?: boolean;
}

const TYPE_COLOR_LIGHT: Record<GraphNodeType, string> = {
  project: "#1a3d80",
  run: "#2c5cb0",
  drawing: "#0e7490",
  model: "#6d28d9",
  calc: "#92400e",
  document: "#5b6b85",
  "code-clause": "#047857",
  reviewer: "#be185d",
};

const TYPE_COLOR_DARK: Record<GraphNodeType, string> = {
  project: "#7d9bd2",
  run: "#4c7cd6",
  drawing: "#22d3ee",
  model: "#a78bfa",
  calc: "#f59e0b",
  document: "#8d9bb5",
  "code-clause": "#34d399",
  reviewer: "#f472b6",
};

const TYPE_RADIUS: Record<GraphNodeType, number> = {
  project: 9,
  run: 5,
  drawing: 4,
  model: 4,
  calc: 4,
  document: 3,
  "code-clause": 3,
  reviewer: 4,
};

export function NetworkGraph({ nodes, links, compact = false }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 600, h: compact ? 240 : 520 });
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setSize({
          w: entry.contentRect.width,
          h: compact ? 240 : Math.max(420, entry.contentRect.height),
        });
      }
    });
    if (containerRef.current) observer.observe(containerRef.current);
    setTheme(
      (document.documentElement.dataset.theme as "light" | "dark" | undefined) ?? "light",
    );
    return () => observer.disconnect();
  }, [compact]);

  const palette = theme === "dark" ? TYPE_COLOR_DARK : TYPE_COLOR_LIGHT;

  const data = useMemo(() => ({ nodes, links }), [nodes, links]);

  return (
    <div ref={containerRef} className="relative w-full" style={{ height: compact ? 240 : 520 }}>
      <ForceGraph2D
        graphData={data}
        width={size.w}
        height={size.h}
        nodeId="id"
        nodeLabel={(node: object) => {
          const n = node as GraphNode;
          return `${n.label} (${n.type})`;
        }}
        linkColor={() => (theme === "dark" ? "#2a3654" : "#d2dae5")}
        linkWidth={(link: object) => ((link as GraphLink).kind === "supersedes" ? 2 : 1)}
        linkDirectionalArrowLength={compact ? 0 : 3}
        linkDirectionalArrowRelPos={0.85}
        cooldownTicks={120}
        nodeCanvasObject={(node: object, ctx: CanvasRenderingContext2D, scale: number) => {
          const n = node as GraphNode & { x?: number; y?: number };
          if (n.x === undefined || n.y === undefined) return;
          const r = TYPE_RADIUS[n.type] ?? 4;
          ctx.beginPath();
          ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
          ctx.fillStyle = n.affected ? "#ef4444" : palette[n.type];
          ctx.fill();
          if (n.affected) {
            ctx.strokeStyle = "#fca5a5";
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }
          if (!compact && scale > 1.2) {
            ctx.font = `${10}px sans-serif`;
            ctx.fillStyle = theme === "dark" ? "#ededed" : "#1f1f1f";
            ctx.textAlign = "center";
            ctx.fillText(n.label, n.x, n.y + r + 8);
          }
        }}
        nodePointerAreaPaint={(node: object, color: string, ctx: CanvasRenderingContext2D) => {
          const n = node as GraphNode & { x?: number; y?: number };
          if (n.x === undefined || n.y === undefined) return;
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(n.x, n.y, (TYPE_RADIUS[n.type] ?? 4) + 2, 0, 2 * Math.PI);
          ctx.fill();
        }}
      />
    </div>
  );
}

/**
 * Build a sample graph from the project's run history.
 * Each completed run becomes a node and links to a synthetic
 * artefact node (drawing / calc / model) plus a code-clause it cites.
 */
export function buildProjectGraph(
  projectName: string,
  runs: AgentRun[],
): { nodes: GraphNode[]; links: GraphLink[] } {
  const nodes: GraphNode[] = [
    { id: "project", label: projectName, type: "project" },
    { id: "drawing:GF-01", label: "Slab GF-01", type: "drawing", affected: true },
    { id: "model:BIM-LP3", label: "BIM LP3", type: "model" },
    { id: "calc:S-204", label: "Calc S-204", type: "calc", affected: true },
    { id: "calc:Punching-C12", label: "Punching C-12", type: "calc", affected: true },
    { id: "document:Soil-Report", label: "Soil report", type: "document" },
    { id: "clause:EN1992-6.4", label: "EN 1992 §6.4", type: "code-clause" },
    { id: "clause:EN1992-9.5", label: "EN 1992 §9.5", type: "code-clause" },
    { id: "reviewer:wagner", label: "Prof. Wagner", type: "reviewer" },
  ];

  const links: GraphLink[] = [
    { source: "project", target: "drawing:GF-01", kind: "depends-on" },
    { source: "project", target: "model:BIM-LP3", kind: "depends-on" },
    { source: "project", target: "document:Soil-Report", kind: "depends-on" },
    { source: "drawing:GF-01", target: "calc:S-204", kind: "depends-on" },
    { source: "calc:S-204", target: "calc:Punching-C12", kind: "depends-on" },
    { source: "calc:Punching-C12", target: "clause:EN1992-6.4", kind: "cites" },
    { source: "calc:S-204", target: "clause:EN1992-9.5", kind: "cites" },
    { source: "calc:S-204", target: "reviewer:wagner", kind: "verified-by" },
    { source: "model:BIM-LP3", target: "drawing:GF-01", kind: "produces" },
  ];

  // Add a node per run + a "produced" edge to the project.
  for (const run of runs.slice(0, 12)) {
    const id = `run:${run.id}`;
    nodes.push({ id, label: run.agent_name, type: "run" });
    links.push({ source: id, target: "project", kind: "produces" });
    if (run.agent_id.includes("calc")) {
      links.push({ source: id, target: "calc:S-204", kind: "produces" });
    } else if (run.agent_id.includes("reinforcement") || run.agent_id.includes("drawing")) {
      links.push({ source: id, target: "drawing:GF-01", kind: "produces" });
    }
  }

  return { nodes, links };
}
