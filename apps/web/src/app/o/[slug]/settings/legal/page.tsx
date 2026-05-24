export default function LegalSettingsPage() {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Legal Documents</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Terms, data-processing agreement, signed AI use policies.
        </p>
      </div>
      <ul className="divide-y divide-border overflow-hidden rounded-md border border-border bg-surface text-sm">
        {[
          { name: "Terms of Service", date: "1 May 2026" },
          { name: "Data Processing Agreement", date: "1 May 2026" },
          { name: "AI Use Policy", date: "1 May 2026" },
        ].map((doc) => (
          <li
            key={doc.name}
            className="flex items-center justify-between px-4 py-3 hover:bg-surface-hover"
          >
            <div>
              <div className="font-medium text-foreground">{doc.name}</div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                Last accepted {doc.date}
              </div>
            </div>
            <button type="button" className="text-sm text-primary hover:underline">
              View
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
