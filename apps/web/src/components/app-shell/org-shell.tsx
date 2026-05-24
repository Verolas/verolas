"use client";

import {
  BarChart3,
  FolderKanban,
  LayoutGrid,
  Receipt,
  Settings,
  Users,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import { ProtectedRoute } from "@/components/protected-route";
import { IconRail, type IconRailItem } from "@/components/icon-rail";
import { TopBar } from "@/components/app-shell/top-bar";
import { RightPanel } from "@/components/app-shell/right-panel";
import { HelpPanelBody } from "@/components/app-shell/help-panel";
import { AssistantPanelBody } from "@/components/app-shell/assistant-panel";
import { NotificationsPanelBody } from "@/components/app-shell/notifications-panel";
import { useAuth } from "@/lib/auth-context";

interface Props {
  slug: string;
  children: ReactNode;
}

export function OrgShell({ slug, children }: Props) {
  const { me } = useAuth();
  const activeOrg = me?.memberships?.find((m) => m.organization_slug === slug);
  const [panel, setPanel] = useState<"help" | "assistant" | "notifications" | null>(null);

  const items: IconRailItem[] = [
    {
      key: "projects",
      label: "Projects",
      href: `/o/${slug}/projects`,
      icon: <FolderKanban className="size-4" aria-hidden="true" />,
      shortcut: "G then P",
    },
    {
      key: "team",
      label: "Team",
      href: `/o/${slug}/team`,
      icon: <Users className="size-4" aria-hidden="true" />,
    },
    {
      key: "integrations",
      label: "Integrations",
      href: `/o/${slug}/integrations`,
      icon: <LayoutGrid className="size-4" aria-hidden="true" />,
    },
    {
      key: "usage",
      label: "Usage",
      href: `/o/${slug}/usage`,
      icon: <BarChart3 className="size-4" aria-hidden="true" />,
    },
    {
      key: "billing",
      label: "Billing",
      href: `/o/${slug}/billing`,
      icon: <Receipt className="size-4" aria-hidden="true" />,
    },
  ];

  const footer: IconRailItem[] = [
    {
      key: "settings",
      label: "Organization Settings",
      href: `/o/${slug}/settings`,
      icon: <Settings className="size-4" aria-hidden="true" />,
    },
  ];

  return (
    <ProtectedRoute>
      <div className="flex min-h-screen bg-background">
        <IconRail sections={[{ items }]} footer={footer} />
        <div className="flex min-h-screen flex-1 flex-col">
          <TopBar
            orgSlug={slug}
            orgName={activeOrg?.organization_name ?? slug}
            onOpenPanel={(next) => setPanel((current) => (current === next ? null : next))}
          />
          <main className="flex-1 px-8 py-8">{children}</main>
        </div>
        <RightPanel
          open={panel === "help"}
          title="Help & Support"
          onClose={() => setPanel(null)}
          header={
            <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="status-dot" data-status="active" />
              All systems operational
            </span>
          }
        >
          <HelpPanelBody />
        </RightPanel>
        <RightPanel
          open={panel === "assistant"}
          title="Verolas Assistant"
          onClose={() => setPanel(null)}
        >
          <AssistantPanelBody />
        </RightPanel>
        <RightPanel
          open={panel === "notifications"}
          title="Notifications"
          onClose={() => setPanel(null)}
        >
          <NotificationsPanelBody />
        </RightPanel>
      </div>
    </ProtectedRoute>
  );
}
