import type { Metadata } from "next";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Projects",
};

export default function ProjectsPage() {
  return (
    <main aria-labelledby="projects-heading" className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 id="projects-heading" className="text-2xl font-semibold tracking-tight">
            Projects
          </h1>
          <p className="text-sm text-muted-foreground">
            A project is the top level container for engineering work. Create one per building,
            site, or infrastructure piece.
          </p>
        </div>
        <Button>New project</Button>
      </header>
      <section aria-label="Project list">
        <Card>
          <CardHeader>
            <CardTitle>No projects yet</CardTitle>
            <CardDescription>
              Once the project lifecycle workstream is wired up, your projects will appear here
              with their HOAI Leistungsphase or RIBA stage, owning engineer, and last workflow run.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline">Create your first project</Button>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
