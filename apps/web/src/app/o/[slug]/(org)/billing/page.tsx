"use client";

import { FileText, Info } from "lucide-react";

import { Button } from "@/components/ui/button";

interface Invoice {
  id: string;
  date: string;
  amount: string;
  number: string;
  status: "paid" | "open" | "void";
}

const INVOICES: Invoice[] = [
  { id: "1", date: "15 May 2026", amount: "$0.00", number: "WAYXKK-00004", status: "paid" },
  { id: "2", date: "15 Apr 2026", amount: "$0.00", number: "WAYXKK-00003", status: "paid" },
];

export default function BillingPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-10">
      <h1 className="text-2xl font-normal tracking-tight text-foreground">Billing</h1>

      <Section
        title="Subscription Plan"
        description="Each organisation has its own subscription plan, billing cycle, payment methods, and usage quotas."
      >
        <div className="space-y-4">
          <div className="text-2xl font-medium text-success">Free Plan</div>
          <div className="flex items-center gap-3">
            <Button variant="outline">Change subscription plan</Button>
          </div>
          <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 size-4 text-muted-foreground" aria-hidden="true" />
              <div>
                <div className="font-medium text-foreground">
                  This organisation is limited by the included usage
                </div>
                <p className="mt-1 text-foreground-light">
                  Projects may become unresponsive when this organisation exceeds its{" "}
                  <button type="button" className="text-primary hover:underline">
                    included usage quota
                  </button>
                  . To scale seamlessly,{" "}
                  <button type="button" className="text-primary hover:underline">
                    upgrade to a paid plan
                  </button>
                  .
                </p>
              </div>
            </div>
          </div>
        </div>
      </Section>

      <Section
        title="Cost Control"
        description="Allow scaling beyond your plan's included quota."
        rightExtra={
          <div className="space-y-1 text-[11px] uppercase tracking-wider text-muted-foreground">
            More information
            <div className="text-xs text-primary">
              <button type="button" className="hover:underline">
                Spend cap
              </button>
            </div>
          </div>
        }
      >
        <p className="text-sm text-foreground-light">
          If you need to go beyond the included quota, simply switch off your spend cap to pay
          for additional usage.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_2fr] sm:items-start">
          <div className="flex h-20 items-end justify-around gap-1 rounded-md border border-border bg-muted/30 p-3">
            {Array.from({ length: 7 }).map((_, i) => (
              <div
                key={i}
                className="w-2 rounded-sm bg-foreground/30"
                style={{ height: `${20 + (i % 3) * 18}%` }}
              />
            ))}
          </div>
          <div>
            <div className="text-sm font-medium text-foreground">Spend cap is enabled</div>
            <p className="mt-1 text-sm text-foreground-light">
              You won&rsquo;t be charged any extra for usage. However, your projects could
              become unresponsive or enter read-only mode if you exceed the included quota.
            </p>
            <Button variant="outline" className="mt-3">
              Change spend cap
            </Button>
          </div>
        </div>
      </Section>

      <Section
        title="Past Invoices"
        description="You get an invoice every time you change your plan or when your monthly billing cycle resets."
      >
        <div className="overflow-hidden rounded-md border border-border bg-surface">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2.5">Date</th>
                <th className="px-4 py-2.5">Amount</th>
                <th className="px-4 py-2.5">Invoice number</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {INVOICES.map((invoice, index) => (
                <tr
                  key={invoice.id}
                  className={
                    index === INVOICES.length - 1
                      ? "transition-colors hover:bg-surface-hover"
                      : "border-b border-border transition-colors hover:bg-surface-hover"
                  }
                >
                  <td className="px-4 py-3 text-foreground">{invoice.date}</td>
                  <td className="px-4 py-3 font-mono text-xs text-foreground">{invoice.amount}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {invoice.number}
                  </td>
                  <td className="px-4 py-3">
                    <span className="badge" data-tone="success">
                      {invoice.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      aria-label={`Download ${invoice.number}`}
                      className="inline-grid size-7 place-items-center rounded text-muted-foreground hover:bg-surface-hover hover:text-foreground"
                    >
                      <FileText className="size-3.5" aria-hidden="true" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

function Section({
  title,
  description,
  rightExtra,
  children,
}: {
  title: string;
  description?: string;
  rightExtra?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="grid gap-8 border-b border-border pb-10 sm:grid-cols-[1fr_2fr]">
      <div>
        <h2 className="text-base font-medium text-foreground">{title}</h2>
        {description && <p className="mt-1 text-sm text-foreground-light">{description}</p>}
        {rightExtra && <div className="mt-4">{rightExtra}</div>}
      </div>
      <div>{children}</div>
    </section>
  );
}
