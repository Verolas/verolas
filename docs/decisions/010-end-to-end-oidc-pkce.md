## ADR 010: End to end OIDC PKCE for browser sign in

- Status: accepted
- Date: 2026-05-24
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: ADR 005, ADR 006, ADR 008
- Informed: founding team

## Context

The auth workstream landed Keycloak in the cluster, the API verified tokens, and the front end had the project list and create form. What was missing: the browser could not actually acquire a token. Users had to paste a bearer string into localStorage by hand. To close the loop we needed the front end to drive a real PKCE authorization code flow against the configured realm, store the resulting tokens, and supply them to the API client. This ADR pins the chosen library, the storage shape, and the deployment choices we made for the dev cluster.

## Options considered

### PKCE library: oauth4webapi (chosen)

- Pros: tiny, no dependencies, ships native ESM, validates ID token signature, supports the discovery endpoint, has explicit PKCE helpers, and works in the browser via Web Crypto. Maintained by the panva PKI-active maintainers.
- Cons: lower level than NextAuth or Auth.js. We write the redirect, the callback handler, and the storage layer ourselves. This is fine for our shape: the API is the source of truth on session, and we do not want NextAuth pulling in server route handlers we would have to fight for our k3s deployment shape.

Alternatives:

- Auth.js (NextAuth): convention over configuration. Wants server route handlers under app/api. Adds a session cookie layer we do not need because the API verifies the bearer directly.
- Keycloak JS adapter: official, drags jQuery-style state into modern React, and the v25 line is in maintenance mode.

### Token storage: sessionStorage only (chosen)

- Tokens never touch localStorage. They live only for the lifetime of the browser tab. A refresh keeps the session; closing the tab ends it. PKCE verifier and state are also sessionStorage.
- Why not httpOnly cookies: the API is on a different subdomain and CORS+cookies is more friction than a bearer header. The bearer-in-memory choice keeps the API authentication path exactly the same as service-to-service auth.
- Risk accepted: an XSS on the same origin could read sessionStorage. CSP and the standard React XSS protections cover the obvious vectors; we will add a strict CSP header in a follow up.

### Auth context shape (chosen)

- Single AuthProvider at the root layout. The provider reads tokens from sessionStorage on mount, exposes `tokens`, `signIn`, `signOut`, and `setTokens`, and wires the API client through `setApiTokenGetter`. The API module never reaches into storage directly; only the context owns the path from storage to network header.
- ProtectedRoute wraps the authenticated app shell. While the context is loading it renders a non-flashing status. After load it redirects to /login with a `?next=` parameter so post-login can land back where the user was.

### Callback page (chosen)

- A dedicated `/auth/callback` route, wrapped in Suspense so Next can prerender it, handles the code exchange and stores tokens. On success it pops a `post_login` redirect path written before the redirect to the IdP. On failure it shows the IdP error and links back to /login.

### In cluster TLS verification for JWKS (chosen, with caveat)

- Traefik in the dev cluster serves a self-signed cert because cert-manager is not pointed at a public Let's Encrypt issuer for in-cluster service-to-service paths. The API runs inside the cluster and fetches JWKS from `https://auth.dev.verolas.com`, which resolves to Traefik's ingress and presents the self-signed cert.
- We added a `VEROLAS_API_OIDC_VERIFY_TLS` setting that defaults to true. The dev deployment opts out (`false`) so the JWKS fetch works. Production will keep it true once we either run a real cert on the auth ingress or use the in-cluster service hostname with a properly-issued mesh cert.

## Decision

| Bible bullet | Implementation |
| --- | --- |
| Front end OIDC PKCE | `apps/web/src/lib/oidc/*` (config, session-storage, client) drives the flow; `apps/web/src/lib/auth-context.tsx` owns the React surface; `apps/web/src/app/auth/callback/page.tsx` is the callback handler; `apps/web/src/components/protected-route.tsx` gates the app shell. |
| Bearer token on every API call | `apps/web/src/lib/api.ts` reads through `setApiTokenGetter` which the auth context populates on every render. |
| API verifies the bearer against the realm | Pre-existing `verolas_auth.TokenVerifier`; this ADR adds the `VEROLAS_API_OIDC_VERIFY_TLS` setting so the in-cluster JWKS fetch survives Traefik's self-signed cert. |
| Founder user provisioned in Postgres | Seeded directly in the dev cluster: `users.id` set to the Keycloak subject UUID so the audit chain attributes events to a real row, owner membership granted in the default org. |

## Consequences

Positive:

- The browser can sign in. /projects works end to end without manual token injection.
- The auth context is the only place that knows about token storage. The API client takes whatever the context hands it, so swapping to httpOnly cookies later is a one-place change.
- The JWKS TLS bypass is gated on a flag that defaults to verifying. Future deployments cannot accidentally skip verification.

Negative:

- The dev cluster trusts the in-cluster Traefik cert blindly. This is fine for dev because the network is the cluster, but the flag must remain false only in dev.
- The bearer token is in sessionStorage, accessible to JavaScript on the same origin. An XSS gets the token. The mitigation is CSP and disciplined sink-side React (no `dangerouslySetInnerHTML` on untrusted strings); a CSP header is a follow up.
- We do not refresh the access token yet. When it expires the next API call gets a 401 and the ProtectedRoute redirects to /login. A refresh-token rotation pass is a follow up.

## Follow ups

1. Add a strict CSP and `Permissions-Policy` header set on the web deployment.
2. Wire the refresh token: silent refresh on 401, sliding session.
3. Replace the in-cluster TLS bypass with either a real cert on the auth ingress or a mesh certificate via Linkerd (the auth workstream's standing deferral).
4. Replace the dev seed of the founder user with an idempotent migration that runs on first boot, keyed by the realm's expected admin subject.
5. Add a route that exchanges the bearer for an API-issued short-lived token, so the API can rotate session secrets independently of the IdP.

## References

- oauth4webapi: https://github.com/panva/oauth4webapi
- PKCE: RFC 7636
- Related: [[ADR 005]], [[ADR 006]], [[ADR 008]]
