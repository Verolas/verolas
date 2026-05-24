import type { ReactNode } from "react";

import { SettingsRail } from "@/components/app-shell/settings-rail";

export default async function SettingsLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const base = `/o/${slug}/settings`;
  const groups = [
    {
      title: "Configuration",
      items: [
        { label: "General", href: `${base}/general` },
        { label: "Security", href: `${base}/security` },
        { label: "SSO", href: `${base}/sso` },
      ],
    },
    {
      title: "Connections",
      items: [{ label: "OAuth Apps", href: `${base}/oauth` }],
    },
    {
      title: "Compliance",
      items: [
        { label: "Audit Logs", href: `${base}/audit` },
        { label: "Legal Documents", href: `${base}/legal` },
      ],
    },
  ];
  return (
    <div className="-m-8 flex min-h-[calc(100vh-3rem)]">
      <SettingsRail groups={groups} />
      <div className="flex-1 px-8 py-8">{children}</div>
    </div>
  );
}
