"""Tests for the tenancy SQL helper."""

from __future__ import annotations

from uuid import UUID

from verolas_auth.tenancy import TenancyContext, sql_set_tenancy


def test_sql_set_tenancy_uses_set_local() -> None:
    ctx = TenancyContext(
        user_id=UUID("00000000-0000-4000-8000-000000000001"),
        org_id=UUID("00000000-0000-4000-8000-000000000002"),
    )
    sql = sql_set_tenancy(ctx)
    assert "SET LOCAL app.current_user_id" in sql
    assert "SET LOCAL app.current_org_id" in sql
    assert str(ctx.user_id) in sql
    assert str(ctx.org_id) in sql
