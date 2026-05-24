"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

interface Item {
  label: string;
  href: string;
}

interface Group {
  title: string;
  items: Item[];
}

interface Props {
  groups: Group[];
}

export function SettingsRail({ groups }: Props) {
  const pathname = usePathname() ?? "";
  return (
    <aside
      aria-label="Settings navigation"
      className="hidden h-screen w-56 shrink-0 border-r border-border bg-surface md:flex md:flex-col"
    >
      <div className="border-b border-border px-4 py-4">
        <div className="text-sm font-medium text-foreground">Settings</div>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {groups.map((group) => (
          <div key={group.title} className="mb-4 last:mb-0">
            <div className="px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {group.title}
            </div>
            <ul className="mt-1">
              {group.items.map((item) => {
                const active = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex h-8 items-center rounded-md px-2 text-sm transition-colors",
                        active
                          ? "bg-muted font-medium text-foreground"
                          : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
                      )}
                      prefetch={false}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
