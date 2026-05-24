"""Connection helper for routes that run before any tenancy exists.

`/v1/me` and `/v1/onboarding` happen before the caller has been wired
into an organisation, so the regular org-scoped `db_conn` cannot serve
them. We hand the route a plain transactional connection from the
pool. The route is expected to talk to `app.account_view` and
`app.onboard_account`, which are `SECURITY DEFINER` functions in the
database that own the RLS bypass for these flows; the verolas_app role
does not have BYPASSRLS, and `SET LOCAL row_security = off` would just
make RLS-touching queries throw rather than bypass anything.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from psycopg import AsyncConnection

from verolas_api.dependencies.auth import AuthContext, require_auth
from verolas_api.dependencies.db import get_pool


async def bootstrap_conn(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> AsyncIterator[AsyncConnection]:
    """Yield a transactional connection; SECURITY DEFINER functions handle RLS."""
    _ = auth  # requires a verified caller; identity enforcement is in the route
    pool = get_pool(request)
    async with pool.connection() as conn:
        async with conn.transaction():
            yield conn


BootstrapConn = Annotated[AsyncConnection, Depends(bootstrap_conn)]
