"""Database connection pool and per-request transaction with tenancy.

The pool is an async psycopg AsyncConnectionPool managed by the app
lifespan. The `db` dependency opens a transaction, sets the
`app.current_user_id` and `app.current_org_id` session variables that
the row level security policies read, hands the connection to the
handler, and commits on success (or rolls back on exception).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from verolas_auth import TenancyContext, sql_set_tenancy

from verolas_api.dependencies.auth import AuthContext, require_auth


def get_pool(request: Request) -> AsyncConnectionPool:
    """Return the app-wide async psycopg pool."""
    pool: AsyncConnectionPool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured on the server.",
        )
    return pool


async def db_conn(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> AsyncIterator[AsyncConnection]:
    """Yield a transactional connection with tenancy set."""
    if auth.claims.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not have an active organisation.",
        )

    pool = get_pool(request)
    async with pool.connection() as conn:
        async with conn.transaction():
            # Resolve the application user_id from the Keycloak subject. For
            # phase 8 we proxy the subject through as the user id when the
            # caller has not yet been provisioned in `users`; the auth library
            # will switch to a real lookup once Keycloak federation lands.
            user_id = _to_uuid_or_zero(auth.claims.keycloak_subject)

            ctx = TenancyContext(
                user_id=user_id,
                org_id=auth.claims.org_id,
            )
            await conn.execute(sql_set_tenancy(ctx))
            yield conn


DbConn = Annotated[AsyncConnection, Depends(db_conn)]

_ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")


def _to_uuid_or_zero(value: str) -> UUID:
    """Parse a Keycloak subject as UUID; fall back to the null UUID otherwise.

    Keycloak subjects are UUIDs in production. In tests the stub verifier
    sometimes hands an opaque string; this preserves a deterministic value
    rather than blowing up the request.
    """
    try:
        return UUID(value)
    except (ValueError, TypeError):
        return _ZERO_UUID
