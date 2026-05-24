"""Org-scoped tenancy dependency for routes under /v1/orgs/{org_slug}/...

`db_org_conn` resolves the org from the URL slug via the SECURITY
DEFINER function `app.resolve_org_membership`, validates the caller
is a member, then sets `app.current_user_id` + `app.current_org_id`
for RLS just like the legacy `db_conn`. We use the helper function
because the verolas_app role cannot bypass RLS itself, and
`SET LOCAL row_security = off` only makes RLS-touching reads throw
rather than bypass anything.
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
    """Resolve org via SECURITY DEFINER lookup, validate membership, stamp tenancy."""
    pool = get_pool(request)
    async with pool.connection() as conn:
        async with conn.transaction():
            cur = await conn.execute(
                "SELECT app.resolve_org_membership(%s, %s)",
                (auth.claims.keycloak_subject, org_slug),
            )
            row = await cur.fetchone()
            payload = row[0] if row else None
            if payload is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No membership for this organisation.",
                )

            user_id = UUID(payload["user_id"])
            org_id = UUID(payload["organization_id"])
            slug = payload["organization_slug"]
            role = payload["role"]

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
