export default function SsoSettingsPage() {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-normal tracking-tight text-foreground">SSO</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Single sign-on with your firm&rsquo;s identity provider.
        </p>
      </div>
      <div className="rounded-md border border-dashed border-border p-10 text-center">
        <div className="text-sm font-medium text-foreground">
          Connect Microsoft Entra ID, Google Workspace, or any SAML 2.0 IdP
        </div>
        <p className="mx-auto mt-2 max-w-md text-sm text-foreground-light">
          Once a paid plan is active, configure your SSO connection here. Members signing in
          via SSO are auto-provisioned with their assigned role.
        </p>
        <button
          type="button"
          className="mt-4 inline-flex h-9 items-center rounded-md border border-border bg-surface px-3 text-sm text-foreground hover:bg-surface-hover"
        >
          Contact sales to enable SSO
        </button>
      </div>
    </div>
  );
}
