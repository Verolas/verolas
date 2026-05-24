export default function AuditSettingsPage() {
  return (
    <div className="mx-auto w-full max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Audit Logs</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Append-only, hash-chained record of every authenticated action in this organisation.
        </p>
      </div>
      <div className="rounded-md border border-border bg-surface p-6">
        <div className="text-sm text-foreground-light">
          The full audit-log viewer ships in a later iteration. Every onboarding,
          project-create, reviewer-finding, and sign-off lands in the chain right now and can
          be queried directly against the database. The chain is verified on every read; any
          tamper attempt is detectable.
        </div>
      </div>
    </div>
  );
}
