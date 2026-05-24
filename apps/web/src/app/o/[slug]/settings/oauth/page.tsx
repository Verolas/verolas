export default function OauthSettingsPage() {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">OAuth Apps</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Third-party apps that can act on this organisation&rsquo;s behalf.
        </p>
      </div>
      <div className="rounded-md border border-dashed border-border p-10 text-center">
        <div className="text-sm font-medium text-foreground">No OAuth apps connected</div>
        <p className="mx-auto mt-2 max-w-md text-sm text-foreground-light">
          Approved apps will appear here with their granted scopes and the date they were
          authorised. Revoking removes their tokens immediately.
        </p>
      </div>
    </div>
  );
}
