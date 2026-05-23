import { FileText, FolderOpen, LayoutDashboard, Settings, Users } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderOpen },
  { href: "/projects", label: "Deliverables", icon: FileText },
  { href: "/projects", label: "Team", icon: Users },
  { href: "/projects", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
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
      <nav>
        <ul className="space-y-1">
          {navItems.map((item, index) => {
            const Icon = item.icon;
            return (
              <li key={`${item.href}-${index}`}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
                    "text-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                >
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
