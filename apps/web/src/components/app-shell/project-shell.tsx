"use client";

import {
  BadgeCheck,
  Bot,
  Calculator,
  Cog,
  Files,
  Home,
  Layers,
  Leaf,
  MessageSquare,
  Network,
  Pencil,
  Play,
  PlugZap,
  Receipt,
  ScanText,
  Send,
  Share2,
  Shield,
  ShieldAlert,
  Sparkles,
  Workflow,
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

const ICON = "size-4" as const;

export function ProjectShell({ slug, projectId, projectName, children }: Props) {
  const { me } = useAuth();
  const activeOrg = me?.memberships?.find((m) => m.organization_slug === slug);
  const [panel, setPanel] = useState<
    "help" | "assistant" | "notifications" | "connect" | null
  >(null);

  const base = `/o/${slug}/projects/${projectId}`;

  const work: IconRailItem[] = [
    { key: "overview", label: "Overview", href: `${base}/overview`, icon: <Home className={ICON} /> },
    { key: "runs", label: "Runs", href: `${base}/runs`, icon: <Play className={ICON} /> },
    { key: "drawings", label: "Drawings", href: `${base}/drawings`, icon: <Pencil className={ICON} /> },
    { key: "models", label: "Models", href: `${base}/models`, icon: <Layers className={ICON} /> },
    { key: "calculations", label: "Calculations", href: `${base}/calculations`, icon: <Calculator className={ICON} /> },
    { key: "documents", label: "Documents", href: `${base}/documents`, icon: <Files className={ICON} /> },
  ];

  const intelligence: IconRailItem[] = [
    { key: "agents", label: "Agents", href: `${base}/agents`, icon: <Bot className={ICON} /> },
    { key: "graph", label: "Graph", href: `${base}/graph`, icon: <Network className={ICON} /> },
    { key: "codes", label: "Codes & Research", href: `${base}/codes`, icon: <ScanText className={ICON} /> },
  ];

  const collaboration: IconRailItem[] = [
    { key: "communications", label: "Communications", href: `${base}/communications`, icon: <MessageSquare className={ICON} /> },
    { key: "reviewers", label: "Reviewers", href: `${base}/reviewers`, icon: <BadgeCheck className={ICON} /> },
    { key: "sharing", label: "Sharing", href: `${base}/sharing`, icon: <Share2 className={ICON} /> },
  ];

  const delivery: IconRailItem[] = [
    { key: "deliverables", label: "Deliverables", href: `${base}/deliverables`, icon: <Workflow className={ICON} /> },
    { key: "submissions", label: "Submissions", href: `${base}/submissions`, icon: <Send className={ICON} /> },
    { key: "estimating", label: "Estimating", href: `${base}/estimating`, icon: <Receipt className={ICON} /> },
    { key: "sustainability", label: "Sustainability", href: `${base}/sustainability`, icon: <Leaf className={ICON} /> },
  ];

  const trust: IconRailItem[] = [
    { key: "quality", label: "Quality", href: `${base}/quality`, icon: <ShieldAlert className={ICON} /> },
    { key: "audit", label: "Audit Log", href: `${base}/audit`, icon: <Shield className={ICON} /> },
  ];

  const footer: IconRailItem[] = [
    { key: "connectors", label: "Connectors", href: `${base}/connectors`, icon: <PlugZap className={ICON} /> },
    { key: "settings", label: "Project Settings", href: `${base}/settings`, icon: <Cog className={ICON} /> },
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
        rail={
          <IconRail
            sections={[
              { items: work },
              { items: intelligence },
              { items: collaboration },
              { items: delivery },
              { items: trust },
            ]}
            footer={footer}
          />
        }
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
