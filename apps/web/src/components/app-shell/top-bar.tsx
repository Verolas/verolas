"use client";

import { Bell, ChevronsUpDown, CircleHelp, Search, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ThemeMenuItem } from "@/components/theme-menu-item";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

interface Props {
  orgSlug?: string;
  orgName?: string;
  plan?: string;
  children?: React.ReactNode;
  onOpenPanel?: (panel: "help" | "assistant" | "notifications") => void;
}

export function TopBar({ orgSlug, orgName, plan = "FREE", children, onOpenPanel }: Props) {
  return (
    <header className="flex h-12 flex-1 items-center gap-2 border-b border-border bg-surface px-3">
      {orgName && orgSlug ? (
        <OrgChip name={orgName} slug={orgSlug} plan={plan} />
      ) : (
        <span className="text-sm text-muted-foreground">Select an organisation</span>
      )}
      {children}
      <div className="ml-auto flex items-center gap-1">
        <Link
          href="#feedback"
          className="hidden rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-surface-hover hover:text-foreground sm:inline-flex"
        >
          Feedback
        </Link>
        <SearchTrigger />
        <IconButton aria-label="Help & Support" onClick={() => onOpenPanel?.("help")}>
          <CircleHelp className="size-4" aria-hidden="true" />
        </IconButton>
        <IconButton aria-label="AI assistant" onClick={() => onOpenPanel?.("assistant")}>
          <Sparkles className="size-4" aria-hidden="true" />
        </IconButton>
        <IconButton aria-label="Notifications" onClick={() => onOpenPanel?.("notifications")}>
          <Bell className="size-4" aria-hidden="true" />
        </IconButton>
        <AvatarMenu />
      </div>
    </header>
  );
}

function OrgChip({ name, slug, plan }: { name: string; slug: string; plan: string }) {
  return (
    <Link
      href={`/o/${slug}/projects`}
      className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-sm hover:bg-surface-hover"
    >
      <span
        className="grid size-4 place-items-center rounded text-[10px] font-semibold text-white"
        style={{ backgroundColor: stringToColor(slug) }}
      >
        {name[0]?.toUpperCase() ?? "?"}
      </span>
      <span className="font-medium text-foreground">{name}</span>
      <span className="badge">{plan}</span>
      <ChevronsUpDown className="size-3 text-muted-foreground" aria-hidden="true" />
    </Link>
  );
}

function SearchTrigger() {
  return (
    <button
      type="button"
      className="hidden h-8 items-center gap-2 rounded-md border border-border bg-muted/40 px-2.5 text-sm text-muted-foreground hover:bg-surface-hover sm:inline-flex"
      aria-label="Search"
    >
      <Search className="size-3.5" aria-hidden="true" />
      <span>Search...</span>
      <span className="ml-6 flex items-center gap-1">
        <span className="kbd">⌘</span>
        <span className="kbd">K</span>
      </span>
    </button>
  );
}

function IconButton({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        "grid size-8 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground",
      )}
      {...props}
    >
      {children}
    </button>
  );
}

function AvatarMenu() {
  const { tokens, me, signOut } = useAuth();
  const email = tokens?.email ?? me?.email ?? null;
  const initials = computeInitials(email);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(event: MouseEvent): void {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    function onEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("mousedown", onClickOutside);
    window.addEventListener("keydown", onEscape);
    return () => {
      window.removeEventListener("mousedown", onClickOutside);
      window.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="ml-1 grid size-8 place-items-center rounded-full border border-border bg-muted text-[11px] font-semibold text-foreground hover:bg-surface-hover"
      >
        {initials}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1.5 w-64 overflow-hidden rounded-lg border border-border bg-surface shadow-md"
        >
          <div className="border-b border-border px-3 py-2.5">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Signed in as
            </div>
            <div className="mt-0.5 truncate text-sm font-medium text-foreground">
              {email ?? "unknown"}
            </div>
          </div>
          <ThemeMenuItem />
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              signOut();
            }}
            className="block w-full border-t border-border px-3 py-2.5 text-left text-sm text-foreground hover:bg-surface-hover"
            role="menuitem"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function computeInitials(email: string | null): string {
  if (!email) return "?";
  const local = email.split("@", 1)[0] ?? "";
  if (!local) return email[0]?.toUpperCase() ?? "?";
  const pieces = local.split(/[._-]+/).filter(Boolean);
  if (pieces.length === 0) return local.slice(0, 2).toUpperCase();
  if (pieces.length === 1) return pieces[0]!.slice(0, 2).toUpperCase();
  return (pieces[0]![0] + pieces[1]![0]!).toUpperCase();
}

function stringToColor(value: string): string {
  let h = 0;
  for (let i = 0; i < value.length; i += 1) {
    h = value.charCodeAt(i) + ((h << 5) - h);
  }
  const hue = Math.abs(h) % 360;
  return `hsl(${hue}, 35%, 45%)`;
}
