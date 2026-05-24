/**
 * Browser-side OIDC config.
 *
 * Values are read from NEXT_PUBLIC_* env so they are baked into the
 * client bundle at build time. The dev cluster builds with the
 * dev Keycloak realm; local development overrides via .env.local.
 */

export interface OidcConfig {
  issuer: string;
  clientId: string;
  audience: string;
  scope: string;
}

export function oidcConfig(): OidcConfig {
  const issuer =
    process.env.NEXT_PUBLIC_OIDC_ISSUER ?? "https://auth.dev.verolas.com/realms/verolas";
  const clientId = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID ?? "verolas-web";
  const audience = process.env.NEXT_PUBLIC_OIDC_AUDIENCE ?? "verolas-api";
  return {
    issuer,
    clientId,
    audience,
    scope: "openid profile email",
  };
}

export function redirectUri(): string {
  if (typeof window === "undefined") return "";
  return `${window.location.origin}/auth/callback`;
}
