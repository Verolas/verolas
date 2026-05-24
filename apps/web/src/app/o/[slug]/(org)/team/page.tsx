"use client";

import { Book, Search, UserPlus, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";

interface Member {
  email: string;
  role: string;
  mfa: boolean;
  isYou?: boolean;
}

export default function TeamPage() {
  const { me } = useAuth();
  const [filter, setFilter] = useState("");

  const members: Member[] = useMemo(() => {
    if (!me) return [];
    return [
      {
        email: me.email ?? me.keycloak_subject,
        role: me.memberships[0]?.role ?? "owner",
        mfa: false,
        isYou: true,
      },
    ];
  }, [me]);

  const filtered = members.filter((m) =>
    m.email.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <h1 className="text-2xl font-normal tracking-tight text-foreground">Team</h1>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter members"
            className="pl-8"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline">
            <Book className="size-3.5" aria-hidden="true" />
            Docs
          </Button>
          <Button>
            <UserPlus className="size-3.5" aria-hidden="true" />
            Invite members
          </Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-border bg-surface">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2.5">Member</th>
              <th className="px-4 py-2.5">MFA</th>
              <th className="px-4 py-2.5">Role</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((member, index) => (
              <tr
                key={member.email}
                className={
                  index === filtered.length - 1
                    ? "transition-colors hover:bg-surface-hover"
                    : "border-b border-border transition-colors hover:bg-surface-hover"
                }
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="grid size-8 place-items-center rounded-full border border-border bg-muted text-[11px] font-semibold text-foreground">
                      {initials(member.email)}
                    </span>
                    <span className="text-sm text-foreground">{member.email}</span>
                    {member.isYou && <span className="badge">You</span>}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                    {member.mfa ? "Enabled" : "Disabled"}
                    <X className="size-3.5" aria-hidden="true" />
                  </span>
                </td>
                <td className="px-4 py-3 text-sm capitalize text-foreground">{member.role}</td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    Leave team
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
          {filtered.length} member{filtered.length === 1 ? "" : "s"}
        </div>
      </div>
    </div>
  );
}

function initials(email: string): string {
  const local = email.split("@", 1)[0] ?? "";
  if (!local) return "?";
  const pieces = local.split(/[._-]+/).filter(Boolean);
  if (pieces.length === 0) return local.slice(0, 2).toUpperCase();
  if (pieces.length === 1) return pieces[0]!.slice(0, 2).toUpperCase();
  return (pieces[0]![0] + pieces[1]![0]!).toUpperCase();
}
