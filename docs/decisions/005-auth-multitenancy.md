# ADR 005: Auth and multi tenancy, Keycloak, six role RBAC, Postgres RLS, mandatory TOTP

- Status: accepted
- Date: 2026-05-23
- Deciders: Shramish Kafle (founder, CEO)
- Consulted: ADR 002, ADR 003, ADR 004
- Informed: founding team

## Context

Verolas is a multi tenant SaaS by design. From day one the platform must isolate organisations from each other, identify users globally and per organisation, enforce role based access, and require multi factor authentication. The stack baseline names Keycloak as the IdP and PostgreSQL row level security as the tenant boundary. This ADR turns those bullets into a concrete implementation.

## Options considered

### Identity provider: Keycloak (chosen)

- Pros: open source, EU sovereign by default, mature, OIDC compliant, supports SAML federation, social IdPs, TOTP and WebAuthn out of the box. Realm configuration is JSON, so identity setup lives in code.
- Cons: heavier than a hosted IdP, needs its own database and operator attention.
- Alternatives: Auth0 (US owned, not sovereign), Authentik (newer, smaller ecosystem), ZITADEL (newer). Conservative pick for an audit grade product wins.

### Tenant boundary: Postgres row level security (chosen)

- Pros: defence in depth. Application bugs cannot leak rows across tenants because the database itself refuses to return them. Policies are SQL, reviewable, and tested by the same migrations that define the tables.
- Cons: every query must run inside a transaction that sets the tenant session variables. Application code must be disciplined.
- Alternatives:
  - Schema per tenant: explodes connection pooling and migration coordination at any reasonable customer count.
  - Database per tenant: hard NO at this scale, ops overhead is enormous.
  - Application level filtering only: weakest. A single missing `WHERE org_id = ?` leaks customer data.

### Role catalogue: six roles, one source of truth (chosen)

- Roles: `owner`, `admin`, `reviewer`, `engineer`, `viewer`, `auditor`.
- One source of truth lives in `services/auth/verolas_auth/roles.py`. The Postgres enum `membership_role` from the tenancy migration and the Keycloak realm roles in `infra/helm/keycloak/realm-template.json` mirror this enum name for name. Any change lands in lockstep across all three.
- The privilege ladder for `role_at_least()` covers the editing chain only. The viewer and auditor splits are explicit role checks, not ladder comparisons. This is the right tradeoff: simple comparator for the common case, explicit check for the audit and read only edges.

### Token verification: PyJWT with JWKS caching (chosen)

- The OIDC verifier in `services/auth/verolas_auth/tokens.py` fetches the realm's JWKS, caches it for ten minutes, and verifies signature, issuer, audience, exp, iat, sub on every request. Signing keys are looked up by kid; an unknown kid forces a JWKS refresh on the next request so Keycloak key rotation does not require a deploy.
- Alternatives: python-jose (unmaintained), authlib (heavier). PyJWT plus cryptography is the conservative, well maintained pick.

### MFA: mandatory TOTP from day one (chosen)

- Keycloak realm template makes `CONFIGURE_TOTP` a default required action, so every user enrolls on first login. OTP policy: 6 digit, 30 second period, SHA1, look ahead of 1 step. SHA1 chosen for universal authenticator app compatibility; SHA256 is supported by newer apps but not universally.
- The `services/auth` library exposes secret generation and code verification helpers used by the application during in app flows (e.g., elevated step up for sensitive operations).
- Recovery codes are enabled in the realm template, ten codes per user, printable on enrollment.

### Tenant scoping in queries: SET LOCAL session variables inside transactions (chosen)

- Every API request opens a transaction, sets `app.current_user_id` and `app.current_org_id`, runs queries, commits. `SET LOCAL` ensures the variables reset at transaction end so a pooled connection cannot leak context across requests.
- The Postgres helper function `app.current_org_id()` reads the variable; the RLS policies reference the function so the SQL stays readable.
- The auth library exposes `sql_set_tenancy(ctx)` to render the SQL. Application code always uses the helper, never raw string formatting.

## Decision

| Bible bullet | Implementation |
| --- | --- |
| Keycloak deployed | Bitnami Keycloak Helm chart, `infra/helm/keycloak/values-{dev,prod}.yaml`, `realm-template.json` with six roles, OTP policy, password policy, brute force protection, event logging |
| User / Organization / Membership data model | First real Alembic revision (`services/db-migrations/alembic/versions/...initial_tenancy_schema.py`) with `users`, `organizations`, `memberships`, role enum, status enums, helper functions, full RLS policies |
| RBAC roles defined | `services/auth/verolas_auth/roles.py` with the six role enum and a privilege comparator |
| Row level security on tenant tables | Policies on `organizations`, `memberships`, `users`. Future application tables that carry `org_id` adopt the standard policy via the migration helper |
| Email / password and first SSO OIDC flow | Keycloak realm with the `verolas-web` public client (Authorization Code PKCE) and the `verolas-api` bearer only client. The token verifier in `services/auth/verolas_auth/tokens.py` consumes the access tokens |
| MFA TOTP ready from day one | Realm requires TOTP at first login. `services/auth/verolas_auth/mfa.py` provides enrollment URI generation and code verification |

## Consequences

Positive:

- Tenant isolation is enforced by the database, not by application discipline. Defence in depth.
- One role enum lives in three coordinated places. Drift is detected by tests as soon as one diverges.
- Token verification is cached, signed key rotation is transparent.
- MFA is on by default, not opt in. No "we will turn it on later" debt.
- Realm configuration is a JSON file in the repo, reviewable, version controlled, reapplied on every cluster rebuild.

Negative:

- Every query needs the right context set. The auth library hides this behind `sql_set_tenancy`, but a developer who reaches around the helper bypasses RLS. PR review catches this; in the future a `psycopg` connection wrapper enforces it at the driver level.
- Keycloak is a service we now operate. Upgrades, backups, and incident response are on us. Mitigation: Keycloak's data lives in our managed Postgres (in prod), so the Postgres backup chain covers it.
- TOTP enrollment adds friction at first login. Acceptable: any team that ships engineering deliverables to be stamped by a licensed engineer expects MFA.

New work created:

- Apply the CloudNativePG operator and Postgres cluster (covered by ADR 004) before the Alembic migration runs.
- Run the migration after the cluster comes up; verify pgvector and the new `app` schema and helper functions land cleanly.
- Install Keycloak on dev, import `realm-template.json`, configure SMTP, create the first user, assign them owner role on the verolas realm.
- Add the API gateway in a subsequent workstream that uses `services/auth` to verify tokens and set tenancy on every request.
- Add the frontend in a subsequent workstream that performs Authorization Code PKCE against `verolas-web`.

## Compliance and audit notes

- Keycloak event logging is enabled with 90 day retention covering login, logout, password change, MFA change, consent grant, and client login. This satisfies the EU AI Act high risk record keeping obligation for identity events.
- RLS policies are enforced via `FORCE ROW LEVEL SECURITY` so superusers cannot accidentally bypass them; application connections use the `verolas_app` role, not superuser.
- The `users.totp_secret_encrypted` column is binary AES GCM enveloped, key sourced from Vault. The Keycloak database also holds the secret independently, so a user can rotate either source.
- Brute force protection in the realm template locks an account for 15 minutes after 5 failed attempts, 12 hour delta window. This matches the BSI baseline for password protected services.

## Follow ups

1. Install Keycloak on dev, apply the realm template.
2. Run the first Alembic migration against the dev cluster, verify the role enum, RLS policies, and helper functions exist.
3. Add the `verolas_app` Postgres role and grant it the right table privileges (the migration's RLS policies already gate row access; column level privileges come next).
4. Wire the `services/auth` package into the first API gateway when that lands.
5. Add a property based test that picks two random orgs, two random users, asserts the API cannot leak rows across them through RLS. Runs as integration test against a real Postgres in CI once a workflow exists.

## References

- Keycloak: https://www.keycloak.org
- PostgreSQL row level security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- PyJWT: https://pyjwt.readthedocs.io
- pyotp: https://pyauth.github.io/pyotp/
- OWASP MFA cheatsheet: https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html
- Related: [[ADR 002]], [[ADR 003]], [[ADR 004]]
