"use client";

import { FileText, FolderOpen, LayoutDashboard, Settings, Users } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

interface Props {
  activeOrgSlug?: string;
}

export function Sidebar({ activeOrgSlug }: Props = {}) {
  const { me } = useAuth();
  const orgSlug =
    activeOrgSlug ?? me?.memberships?.[0]?.organization_slug ?? null;
  const activeOrg = me?.memberships?.find((m) => m.organization_slug === orgSlug);

  const base = orgSlug ? `/o/${orgSlug}` : "";
  const navItems = [
    { href: `${base}/dashboard`, label: "Dashboard", icon: LayoutDashboard, disabled: !orgSlug },
    { href: `${base}/projects`, label: "Projects", icon: FolderOpen, disabled: !orgSlug },
    { href: `${base}/deliverables`, label: "Deliverables", icon: FileText, disabled: !orgSlug },
    { href: `${base}/team`, label: "Team", icon: Users, disabled: !orgSlug },
    { href: `${base}/settings`, label: "Settings", icon: Settings, disabled: !orgSlug },
  ];

  return (
    <aside
      aria-label="Primary navigation"
      className="hidden w-60 shrink-0 border-r bg-secondary/40 p-4 md:block"
    >
      <div className="mb-6 px-2">
        <span className="block text-lg font-semibold tracking-tight text-verolas-deep">
          Verolas
        </span>
        <span className="block text-xs text-muted-foreground">Engineering, supervised</span>
      </div>
      {activeOrg && (
        <div className="mb-4 rounded-md border border-input bg-background px-3 py-2">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Workspace</div>
          <div className="text-sm font-semibold text-foreground">{activeOrg.organization_name}</div>
          <div className="text-xs text-muted-foreground">{activeOrg.role}</div>
        </div>
      )}
      <nav>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const className = cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
              item.disabled
                ? "cursor-not-allowed text-muted-foreground"
                : "text-foreground hover:bg-accent hover:text-accent-foreground",
            );
            if (item.disabled) {
              return (
                <li key={item.label}>
                  <span className={className} aria-disabled="true">
                    <Icon className="size-4" aria-hidden="true" />
                    {item.label}
                  </span>
                </li>
              );
            }
            return (
              <li key={item.label}>
                <Link href={item.href} className={className}>
                  <Icon className="size-4" aria-hidden="true" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
