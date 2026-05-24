"""Auth-less database connection for public callback handlers.

Used by the vendor OAuth callback endpoint, which the browser is
mid-redirected to with no session attached. The state token mints in
`connector_oauth_state` IS the security boundary; only a request that
arrives with a known one-shot state value can complete an install.

Do not use this dependency for any endpoint where the caller's
identity matters.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from psycopg import AsyncConnection

from verolas_api.dependencies.db import get_pool


async def public_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    """Yield a transactional connection without any auth check."""
    pool = get_pool(request)
    async with pool.connection() as conn:
        async with conn.transaction():
            yield conn


PublicConn = Annotated[AsyncConnection, Depends(public_conn)]
