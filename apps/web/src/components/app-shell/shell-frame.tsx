"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/app-shell/logo";

interface Props {
  /** The top-bar slot, rendered to the right of the 48px logo cell. */
  topBar: ReactNode;
  /** The icon rail rendered as the second-row left column. */
  rail: ReactNode;
  /** The page content. */
  children: ReactNode;
  /** Where the corner logo links to. Defaults to /projects which resolves
   * to the caller's first org once their /v1/me has loaded. */
  homeHref?: string;
}

/**
 * Two-row, two-column shell:
 *
 * +-----+----------------------------------------+
 * | LOG | top bar                                |
 * +-----+----------------------------------------+
 * | RAIL|                                        |
 * |     | content                                |
 * |     |                                        |
 * +-----+----------------------------------------+
 *
 * The logo cell and rail share a left column at 48px; the top bar and
 * content share the right column. Borders meet flush at the corner.
 */
export function ShellFrame({ topBar, rail, children, homeHref = "/projects" }: Props) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <div className="sticky top-0 z-30 flex h-12 shrink-0 bg-surface">
        <Link
          href={homeHref}
          className="flex w-12 shrink-0 items-center justify-center border-b border-r border-border"
          aria-label="Home"
        >
          <Logo className="size-5 text-primary" />
        </Link>
        {topBar}
      </div>
      <div className="flex flex-1">
        {rail}
        <main className="flex-1 overflow-x-hidden">{children}</main>
      </div>
    </div>
  );
}
