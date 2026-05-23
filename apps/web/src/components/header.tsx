import { Bell, CircleUser } from "lucide-react";

import { Button } from "@/components/ui/button";

export function Header() {
  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-4">
      <div className="text-sm text-muted-foreground">
        <span aria-hidden="true" className="hidden sm:inline">
          /
        </span>{" "}
        <span>Workspace</span>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell className="size-4" aria-hidden="true" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Account menu">
          <CircleUser className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </header>
  );
}
