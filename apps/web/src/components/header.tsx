"use client";

import { Bell, ChevronDown, LogOut, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ThemeMenuItem } from "@/components/theme-menu-item";
import { useAuth } from "@/lib/auth-context";

export function Header() {
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
    <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-hairline bg-surface/95 px-5 backdrop-blur supports-[backdrop-filter]:bg-surface/80">
      <div className="hidden flex-1 items-center md:flex">
        <label className="relative flex w-full max-w-md items-center">
          <Search
            className="pointer-events-none absolute left-2.5 size-3.5 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            type="search"
            placeholder="Search projects, deliverables, files"
            aria-label="Search"
            className="h-8 w-full rounded-md border border-hairline bg-muted pl-8 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/30"
          />
        </label>
      </div>
      <div className="flex flex-1 items-center justify-end gap-2 md:flex-none">
        <button
          type="button"
          aria-label="Notifications"
          className="grid size-8 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Bell className="size-4" aria-hidden="true" />
        </button>
        <div className="relative" ref={ref}>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
            className="flex items-center gap-2 rounded-md py-1 pl-1 pr-2 text-sm text-foreground hover:bg-muted"
          >
            <span className="grid size-7 place-items-center rounded-full bg-brand-600 text-[11px] font-semibold text-white">
              {initials}
            </span>
            <ChevronDown className="size-3 text-muted-foreground" aria-hidden="true" />
          </button>
          {open && (
            <div
              role="menu"
              className="absolute right-0 top-full mt-2 w-64 overflow-hidden rounded-lg border border-hairline bg-surface shadow-md"
            >
              <div className="border-b border-hairline px-3 py-2.5">
                <div className="text-xs text-muted-foreground">Signed in as</div>
                <div className="truncate text-sm font-medium text-foreground">
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
                className="flex w-full items-center gap-2 border-t border-hairline px-3 py-2.5 text-left text-sm text-foreground hover:bg-muted"
                role="menuitem"
              >
                <LogOut className="size-3.5 text-muted-foreground" aria-hidden="true" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
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
