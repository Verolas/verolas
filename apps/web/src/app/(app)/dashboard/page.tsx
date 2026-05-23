import type { Metadata } from "next";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Dashboard",
};

const cards = [
  {
    title: "Open projects",
    description: "Projects with at least one workflow run in the last 30 days.",
    value: "0",
  },
  {
    title: "Stampable deliverables",
    description: "Deliverables ready for engineer review and stamp.",
    value: "0",
  },
  {
    title: "Workflow runs (this week)",
    description: "Across all disciplines.",
    value: "0",
  },
] as const;

export default function DashboardPage() {
  return (
    <main aria-labelledby="dashboard-heading" className="space-y-6">
      <header className="space-y-1">
        <h1 id="dashboard-heading" className="text-2xl font-semibold tracking-tight">
          Dashboard
        </h1>
        <p className="text-sm text-muted-foreground">
          Snapshot of the work in your firm. Detailed metrics arrive with the analytics workstream.
        </p>
      </header>
      <section
        aria-labelledby="overview-heading"
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
      >
        <h2 id="overview-heading" className="sr-only">
          Overview metrics
        </h2>
        {cards.map((card) => (
          <Card key={card.title}>
            <CardHeader>
              <CardTitle>{card.title}</CardTitle>
              <CardDescription>{card.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold text-verolas-deep">{card.value}</p>
            </CardContent>
          </Card>
        ))}
      </section>
    </main>
  );
}
