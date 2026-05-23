"""Tenant scoping helpers.

Every database request executes inside a transaction that sets two session
variables: `app.current_user_id` and `app.current_org_id`. The row level
security policies in the tenancy migration read these variables to scope
visibility. The application layer never queries with raw connection objects
that do not first set these variables.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenancyContext:
    """The pair of identifiers RLS needs on every request."""

    user_id: UUID
    org_id: UUID


def sql_set_tenancy(ctx: TenancyContext) -> str:
    """Render the SQL to set the session variables.

    The application calls this inside a transaction:

        async with conn.transaction():
            await conn.execute(sql_set_tenancy(ctx))
            ...

    SET LOCAL is the right scope: variables reset at end of transaction so
    they cannot leak across requests if the connection is reused.
    """
    return (
        f"SET LOCAL app.current_user_id = '{ctx.user_id}'; "
        f"SET LOCAL app.current_org_id = '{ctx.org_id}';"
    )
