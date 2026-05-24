"use client";

import {
  Calculator,
  ClipboardCheck,
  Cog,
  FileText,
  Folders,
  Home,
  LayoutGrid,
  Layers,
  LineChart,
  Pencil,
  Shield,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import { ProtectedRoute } from "@/components/protected-route";
import { IconRail, type IconRailItem } from "@/components/icon-rail";
import { TopBar } from "@/components/app-shell/top-bar";
import { ShellFrame } from "@/components/app-shell/shell-frame";
import { ProjectBreadcrumb } from "@/components/app-shell/project-breadcrumb";
import { RightPanel } from "@/components/app-shell/right-panel";
import { HelpPanelBody } from "@/components/app-shell/help-panel";
import { AssistantPanelBody } from "@/components/app-shell/assistant-panel";
import { NotificationsPanelBody } from "@/components/app-shell/notifications-panel";
import { ConnectPanelBody } from "@/components/app-shell/connect-panel";
import { useAuth } from "@/lib/auth-context";

interface Props {
  slug: string;
  projectId: string;
  projectName: string;
  children: ReactNode;
}

export function ProjectShell({ slug, projectId, projectName, children }: Props) {
  const { me } = useAuth();
  const activeOrg = me?.memberships?.find((m) => m.organization_slug === slug);
  const [panel, setPanel] = useState<
    "help" | "assistant" | "notifications" | "connect" | null
  >(null);

  const base = `/o/${slug}/projects/${projectId}`;

  const primary: IconRailItem[] = [
    { key: "overview", label: "Project Overview", href: `${base}/overview`, icon: <Home className="size-4" /> },
    { key: "drawings", label: "Drawings", href: `${base}/drawings`, icon: <Pencil className="size-4" /> },
    { key: "calculations", label: "Calculations", href: `${base}/calculations`, icon: <Calculator className="size-4" /> },
  ];

  const data: IconRailItem[] = [
    { key: "documents", label: "Documents", href: `${base}/documents`, icon: <FileText className="size-4" /> },
    { key: "models", label: "Models & BIM", href: `${base}/models`, icon: <Layers className="size-4" /> },
    { key: "workspaces", label: "Workspaces", href: `${base}/workspaces`, icon: <Folders className="size-4" /> },
    { key: "reviewers", label: "Reviewers", href: `${base}/reviewers`, icon: <ClipboardCheck className="size-4" /> },
  ];

  const platform: IconRailItem[] = [
    { key: "advisors", label: "Advisors", href: `${base}/advisors`, icon: <ShieldAlert className="size-4" /> },
    { key: "observability", label: "Observability", href: `${base}/observability`, icon: <LineChart className="size-4" /> },
    { key: "audit", label: "Audit Log", href: `${base}/audit`, icon: <Shield className="size-4" /> },
    { key: "integrations", label: "Integrations", href: `${base}/integrations`, icon: <LayoutGrid className="size-4" /> },
  ];

  const footer: IconRailItem[] = [
    { key: "settings", label: "Project Settings", href: `${base}/settings`, icon: <Cog className="size-4" /> },
  ];

  return (
    <ProtectedRoute>
      <ShellFrame
        homeHref={`/o/${slug}/projects`}
        topBar={
          <TopBar
            orgSlug={slug}
            orgName={activeOrg?.organization_name ?? slug}
            onOpenPanel={(next) => setPanel((current) => (current === next ? null : next))}
          >
            <ProjectBreadcrumb
              orgSlug={slug}
              projectId={projectId}
              projectName={projectName}
              onOpenConnect={() => setPanel("connect")}
            />
          </TopBar>
        }
        rail={<IconRail sections={[{ items: primary }, { items: data }, { items: platform }]} footer={footer} />}
      >
        {children}
      </ShellFrame>
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
        header={
          <span className="flex items-center gap-1.5 text-[11px] text-primary">
            <Sparkles className="size-3" aria-hidden="true" />
            New chat
          </span>
        }
        width="w-[420px]"
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
      <RightPanel
        open={panel === "connect"}
        title="Connect to this project"
        onClose={() => setPanel(null)}
        width="w-[480px]"
      >
        <ConnectPanelBody projectId={projectId} />
      </RightPanel>
    </ProtectedRoute>
  );
}
