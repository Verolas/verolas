"use client";

import { useState } from "react";

const TABS = ["All", "Security", "Performance", "Messages"] as const;

export function NotificationsPanelBody() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("All");
  return (
    <div className="flex h-full flex-col">
      <div className="segmented w-full">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            aria-pressed={tab === t}
            onClick={() => setTab(t)}
            className="flex-1"
          >
            {t}
          </button>
        ))}
      </div>
      <div className="mt-6 flex flex-1 flex-col items-center justify-center text-center">
        <div className="text-sm text-muted-foreground">No new notifications</div>
        <p className="mt-1 max-w-[24ch] text-xs text-muted-foreground">
          You will see reviewer findings, audit alerts, and platform updates here.
        </p>
      </div>
    </div>
  );
}
