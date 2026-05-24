"use client";

import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Width in px or tailwind-friendly value. */
  width?: string;
  header?: ReactNode;
}

export function RightPanel({ open, title, onClose, children, width = "w-96", header }: Props) {
  useEffect(() => {
    if (!open) return;
    function onEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [open, onClose]);

  return (
    <aside
      aria-hidden={!open}
      className={cn(
        "fixed right-0 top-0 z-40 flex h-screen flex-col border-l border-border bg-surface shadow-md transition-transform duration-200",
        width,
        open ? "translate-x-0" : "translate-x-full",
      )}
    >
      <div className="flex h-12 items-center justify-between border-b border-border px-4">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <div className="flex items-center gap-3">
          {header}
          <button
            type="button"
            aria-label="Close panel"
            onClick={onClose}
            className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-surface-hover hover:text-foreground"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">{children}</div>
    </aside>
  );
}
