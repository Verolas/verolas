"""Connection helpers that bypass row-level security for bootstrap writes.

The onboarding flow creates the first organisation, the user row, and the
first owner membership before any tenancy context exists, so the regular
`db_conn` dependency (which insists on a verified org_id from the token)
cannot serve those writes. `bootstrap_conn` opens a connection with
`row_security = off` for the duration of the transaction so the inserts
succeed under the policies' implicit deny.

The bypass is scoped to a single transaction and never leaks back into
later requests; the pool's connection lifecycle is unchanged. We do not
elevate the database role; we still run as `verolas_app`, which is why
the migration that grants table privileges and the SECURITY DEFINER
audit-trigger function still apply.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from psycopg import AsyncConnection

from verolas_api.dependencies.auth import AuthContext, require_auth
from verolas_api.dependencies.db import get_pool


async def bootstrap_conn(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> AsyncIterator[AsyncConnection]:
    """Yield a transactional connection that bypasses RLS for the request."""
    _ = auth  # requires a verified caller; identity enforcement is in the route
    pool = get_pool(request)
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL row_security = off")
            yield conn


BootstrapConn = Annotated[AsyncConnection, Depends(bootstrap_conn)]


def require_uuid(value: str, *, field: str) -> str:
    """Cheap guard for fields that must look like a Keycloak subject UUID."""
    from uuid import UUID

    try:
        return str(UUID(value))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field} is not a valid identifier.",
        ) from exc
