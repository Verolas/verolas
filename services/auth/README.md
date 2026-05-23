# verolas-auth

Shared auth primitives for every Python service in Verolas. Provides four building blocks:

1. **Role enum** with privilege comparison. One source of truth, paired with the Keycloak realm template and the Postgres `membership_role` enum.
2. **OIDC token verifier** that fetches JWKS from Keycloak, caches it, and verifies bearer tokens by signature, issuer, audience, and expiry.
3. **Tenancy context helper** that renders the SQL to set `app.current_user_id` and `app.current_org_id` session variables, which the row level security policies in the tenancy migration read.
4. **TOTP MFA helpers** that mint enrollment secrets, render `otpauth://` URIs for authenticator apps, and verify codes in constant time.

## Local setup

```bash
cd services/auth
uv sync
uv run pytest
```

## How services use this

The first consumer is the API gateway in `apps/api` (lands in a later workstream). The pattern looks like this:

```python
from verolas_auth import TenancyContext, TokenVerifier, TokenVerifierSettings, sql_set_tenancy

settings = TokenVerifierSettings(
    issuer="https://auth.verolas.com/realms/verolas",
    audience="verolas-api",
)
verifier = TokenVerifier(settings)

# On every request:
claims = verifier.verify(bearer_token)
async with conn.transaction():
    if claims.org_id is None:
        raise PermissionError("Token has no org context")
    ctx = TenancyContext(user_id=user_id_from_subject(claims.keycloak_subject), org_id=claims.org_id)
    await conn.execute(sql_set_tenancy(ctx))
    # All queries inside this transaction are scoped to ctx.org_id by RLS.
```

## Why the role split is more than a privilege ladder

The role enum lives in `verolas_auth/roles.py`. Six values, three "broad scopes":

- Editing chain: `engineer` does the work, `reviewer` approves it, `admin` runs the org, `owner` owns it.
- Read only: `viewer` sees projects and deliverables.
- Audit only: `auditor` sees the audit log that `engineer` and `reviewer` cannot see.

`role_at_least()` orders the four "editing chain" roles plus the two read only roles into a single privilege scale. It is correct for "does this caller have admin or better" type checks. For checks like "can this caller read the audit log" use direct role membership tests, not the comparator.

## Why MFA is mandatory from day one

The Keycloak realm template enforces TOTP on first login. The `users.mfa_enabled` column lets the application track whether the user has completed enrollment, useful for UX states that should not be shown until MFA is in place. The `users.totp_secret_encrypted` column holds the AES GCM enveloped secret; the envelope key lives in Vault.

The auth library produces the secret and the provisioning URI. The application is responsible for the envelope encryption and the secret database column write. The Keycloak side also has the secret independently (Keycloak stores it itself), so a user can rotate either source.

## Why JWKS is cached, not pinned

Keycloak rotates signing keys quarterly. Pinning a key would lock us into a single signing key forever, breaking the moment Keycloak rotates. The JWKS cache holds keys for ten minutes by default; on a rotation, the next token signed with the new kid forces a JWKS refresh and the new key is picked up.

The cache TTL is configurable on `TokenVerifierSettings`. Lower it under suspicion of compromise.

## Tests

```bash
uv run pytest -v
uv run ruff format --check .
uv run ruff check .
uv run mypy .
```

All four are green on commit.
