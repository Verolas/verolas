export default function SecuritySettingsPage() {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">Security</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Authentication policy, session lifetime, MFA enforcement.
        </p>
      </div>
      <Placeholder
        title="Security controls land in the next iteration"
        body="Settings for enforced MFA, SSO-only sign-in, session lifetime, and per-role API scopes will appear here. The audit log already records every authentication event."
      />
    </div>
  );
}

function Placeholder({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-md border border-dashed border-border p-10 text-center">
      <div className="text-sm font-medium text-foreground">{title}</div>
      <p className="mx-auto mt-2 max-w-md text-sm text-foreground-light">{body}</p>
    </div>
  );
}
