"use client";

import {
  Building2,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LifeBuoy,
  Settings,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

interface Props {
  activeOrgSlug?: string;
}

type NavEntry = {
  key: string;
  label: string;
  icon: typeof LayoutDashboard;
  external?: boolean;
};

const PRIMARY: NavEntry[] = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "projects", label: "Projects", icon: FolderOpen },
  { key: "deliverables", label: "Deliverables", icon: FileText },
  { key: "team", label: "Team", icon: Users },
];

const FOOTER: NavEntry[] = [
  { key: "settings", label: "Settings", icon: Settings },
  { key: "help", label: "Help & support", icon: LifeBuoy, external: true },
];

export function Sidebar({ activeOrgSlug }: Props = {}) {
  const { me } = useAuth();
  const pathname = usePathname() ?? "";
  const slug = activeOrgSlug ?? me?.memberships?.[0]?.organization_slug ?? null;
  const activeOrg = me?.memberships?.find((m) => m.organization_slug === slug);

  const base = slug ? `/o/${slug}` : "";
  const disabled = !slug;

  return (
    <aside
      aria-label="Primary navigation"
      className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-hairline bg-surface md:flex"
    >
      <div className="flex h-14 items-center gap-2 border-b border-hairline px-4">
        <div className="grid size-7 place-items-center rounded-md bg-brand-700 text-white">
          <Building2 className="size-4" aria-hidden="true" />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold tracking-tight text-foreground">Verolas</span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Civil AI
          </span>
        </div>
      </div>

      <div className="border-b border-hairline p-3">
        <div className="rounded-md border border-hairline bg-muted/60 px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-sm font-medium text-foreground">
              {activeOrg?.organization_name ?? "No workspace"}
            </span>
            {activeOrg && (
              <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-brand-700">
                {activeOrg.role}
              </span>
            )}
          </div>
          {slug && (
            <div className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">
              /o/{slug}
            </div>
          )}
        </div>
      </div>

      <nav className="flex-1 px-2 py-3" aria-label="Main">
        <ul className="space-y-0.5">
          {PRIMARY.map((item) => {
            const Icon = item.icon;
            const href = `${base}/${item.key}`;
            const active = !disabled && pathname.startsWith(href);
            return (
              <li key={item.key}>
                <NavItem
                  href={href}
                  active={active}
                  disabled={disabled}
                  icon={<Icon className="size-4" aria-hidden="true" />}
                >
                  {item.label}
                </NavItem>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-hairline px-2 py-3">
        <ul className="space-y-0.5">
          {FOOTER.map((item) => {
            const Icon = item.icon;
            const href = item.external ? "https://verolas.com/help" : `${base}/${item.key}`;
            const active = !disabled && !item.external && pathname.startsWith(href);
            return (
              <li key={item.key}>
                <NavItem
                  href={href}
                  active={active}
                  disabled={disabled && !item.external}
                  icon={<Icon className="size-4" aria-hidden="true" />}
                  external={item.external ?? false}
                >
                  {item.label}
                </NavItem>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}

interface NavItemProps {
  href: string;
  active?: boolean;
  disabled?: boolean;
  icon: React.ReactNode;
  children: React.ReactNode;
  external?: boolean;
}

function NavItem({ href, active, disabled, icon, children, external }: NavItemProps) {
  const className = cn(
    "relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
    active
      ? "bg-brand-50 text-brand-700 dark:bg-accent dark:text-accent-foreground"
      : "text-muted-foreground hover:bg-muted hover:text-foreground",
    disabled && "pointer-events-none opacity-50",
  );
  const inner = (
    <>
      {active && (
        <span
          aria-hidden="true"
          className="absolute left-0 top-1.5 h-5 w-0.5 rounded-full bg-brand-600"
        />
      )}
      {icon}
      <span className="flex-1">{children}</span>
    </>
  );
  if (disabled) {
    return (
      <span className={className} aria-disabled="true">
        {inner}
      </span>
    );
  }
  if (external) {
    return (
      <a className={className} href={href} target="_blank" rel="noreferrer">
        {inner}
      </a>
    );
  }
  return (
    <Link className={className} href={href}>
      {inner}
    </Link>
  );
}
