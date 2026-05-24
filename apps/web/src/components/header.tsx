"use client";

import { Bell, LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";

export function Header() {
  const { tokens, signOut } = useAuth();
  const email = tokens?.email ?? null;

  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-4">
      <div className="text-sm text-muted-foreground">
        <span aria-hidden="true" className="hidden sm:inline">
          /
        </span>{" "}
        <span>Workspace</span>
      </div>
      <div className="flex items-center gap-3">
        {email && <span className="text-sm text-muted-foreground">{email}</span>}
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell className="size-4" aria-hidden="true" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Sign out" onClick={signOut}>
          <LogOut className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </header>
  );
}
