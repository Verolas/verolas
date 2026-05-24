"""Org-scoped tenancy dependency for routes under /v1/orgs/{org_slug}/...

`db_org_conn` takes the slug from the URL, looks up the org, verifies
the caller is a member, then sets `app.current_user_id` +
`app.current_org_id` for RLS just like the legacy `db_conn`. The
membership check runs with RLS off (since by definition we don't yet
know the org_id) and then RLS is re-enabled for the rest of the
transaction.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, Request, status
from psycopg import AsyncConnection
from verolas_auth import TenancyContext, sql_set_tenancy

from verolas_api.dependencies.auth import AuthContext, require_auth
from verolas_api.dependencies.db import get_pool


@dataclass(frozen=True, slots=True)
class OrgContext:
    """The resolved org for a path-scoped request."""

    user_id: UUID
    organization_id: UUID
    organization_slug: str
    role: str


async def db_org_conn(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_auth)],
    org_slug: Annotated[str, Path(min_length=1, max_length=40)],
) -> AsyncIterator[tuple[AsyncConnection, OrgContext]]:
    """Resolve org from URL slug, validate membership, set RLS tenancy."""
    pool = get_pool(request)
    async with pool.connection() as conn:
        async with conn.transaction():
            # Stage 1: temporarily disable RLS so we can look up the org +
            # membership before we know the tenancy.
            await conn.execute("SET LOCAL row_security = off")
            cur = await conn.execute(
                """
                SELECT o.id, o.slug, m.role, u.id
                FROM organizations o
                JOIN memberships m ON m.org_id = o.id
                JOIN users u ON u.id = m.user_id
                WHERE o.slug = %s
                  AND u.keycloak_subject = %s
                  AND o.status <> 'deleted'
                """,
                (org_slug, auth.claims.keycloak_subject),
            )
            row = await cur.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No membership for this organisation.",
                )
            org_id, slug, role, user_id = row

            # Stage 2: re-enable RLS and stamp tenancy. Every statement the
            # route runs after this is filtered by RLS.
            await conn.execute("SET LOCAL row_security = on")
            ctx = TenancyContext(user_id=user_id, org_id=org_id)
            await conn.execute(sql_set_tenancy(ctx))

            yield (
                conn,
                OrgContext(
                    user_id=user_id,
                    organization_id=org_id,
                    organization_slug=slug,
                    role=role,
                ),
            )


DbOrgConn = Annotated[tuple[AsyncConnection, OrgContext], Depends(db_org_conn)]
