"use client";

import { Moon, Sun, Monitor } from "lucide-react";

import { useTheme } from "@/lib/theme";

export function ThemeMenuItem() {
  const { choice, setChoice } = useTheme();
  const options: { key: typeof choice; label: string; icon: typeof Sun }[] = [
    { key: "light", label: "Light", icon: Sun },
    { key: "dark", label: "Dark", icon: Moon },
    { key: "system", label: "System", icon: Monitor },
  ];
  return (
    <div className="px-2 py-1.5">
      <div className="mb-1 px-2 text-xs font-medium text-muted-foreground">Appearance</div>
      <div className="segmented w-full">
        {options.map((opt) => {
          const Icon = opt.icon;
          return (
            <button
              key={opt.key}
              type="button"
              aria-pressed={choice === opt.key}
              onClick={() => setChoice(opt.key)}
              className="flex flex-1 items-center justify-center gap-1.5"
            >
              <Icon className="size-3" aria-hidden="true" />
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
