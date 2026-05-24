"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface IconRailItem {
  key: string;
  label: string;
  href: string;
  icon: ReactNode;
  shortcut?: string;
  disabled?: boolean;
}

export interface IconRailSection {
  items: IconRailItem[];
}

interface IconRailProps {
  sections: IconRailSection[];
  /** Items pinned to the bottom of the rail (e.g. Project Settings). */
  footer?: IconRailItem[];
  /** Width when expanded by hover. Defaults to 12rem. */
  expandedWidth?: string;
  /** Optional override for matching the active key explicitly (useful for nested routes). */
  activeKey?: string;
}

const COLLAPSED_W = "w-12"; // 48px
const EXPANDED_W = "w-48"; // 192px

export function IconRail({ sections, footer, activeKey }: IconRailProps) {
  const pathname = usePathname() ?? "";
  const [open, setOpen] = useState(false);

  return (
    <div
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={(event) => {
        if (event.currentTarget.contains(event.relatedTarget as Node)) return;
        setOpen(false);
      }}
      className={cn(
        "sticky top-0 z-20 hidden h-screen shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-150 md:flex",
        open ? EXPANDED_W : COLLAPSED_W,
      )}
      aria-label="Primary navigation"
      data-state={open ? "expanded" : "collapsed"}
    >
      <nav className="flex-1 overflow-hidden py-2">
        {sections.map((section, index) => (
          <div key={index} className={index > 0 ? "mt-2 border-t border-border pt-2" : ""}>
            {section.items.map((item) => (
              <RailLink
                key={item.key}
                item={item}
                open={open}
                active={isActive(item, pathname, activeKey)}
              />
            ))}
          </div>
        ))}
      </nav>
      {footer && footer.length > 0 && (
        <div className="border-t border-border py-2">
          {footer.map((item) => (
            <RailLink
              key={item.key}
              item={item}
              open={open}
              active={isActive(item, pathname, activeKey)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function isActive(item: IconRailItem, pathname: string, activeKey?: string): boolean {
  if (activeKey === item.key) return true;
  if (!item.href) return false;
  if (item.href === "/") return pathname === "/";
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

function RailLink({
  item,
  open,
  active,
}: {
  item: IconRailItem;
  open: boolean;
  active: boolean;
}) {
  const className = cn(
    "group relative flex h-9 items-center gap-3 px-3 text-sm transition-colors",
    active
      ? "text-foreground"
      : "text-muted-foreground hover:text-foreground hover:bg-surface-hover",
    item.disabled && "pointer-events-none opacity-40",
  );

  const content = (
    <>
      <span
        className={cn(
          "flex size-6 shrink-0 items-center justify-center rounded-md",
          active && "bg-muted text-foreground",
        )}
        aria-hidden="true"
      >
        {item.icon}
      </span>
      <span
        className={cn(
          "min-w-0 flex-1 truncate transition-opacity duration-100",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      >
        {item.label}
      </span>
      {open && item.shortcut && (
        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
          {item.shortcut.split(" ").map((segment, index) => (
            <span key={index} className={segment === "then" ? "" : "kbd"}>
              {segment}
            </span>
          ))}
        </span>
      )}
    </>
  );

  if (item.disabled) {
    return (
      <span className={className} aria-disabled="true">
        {content}
      </span>
    );
  }

  return (
    <Link href={item.href} className={className} prefetch={false}>
      {content}
    </Link>
  );
}
