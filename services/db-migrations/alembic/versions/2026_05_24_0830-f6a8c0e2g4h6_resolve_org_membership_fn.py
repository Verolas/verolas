"""SECURITY DEFINER lookup for org-scoped routes.

`db_org_conn` resolves the org from the URL slug and validates the
caller's membership before stamping tenancy. The previous attempt
used `SET LOCAL row_security = off`, which doesn't bypass RLS for
the verolas_app role; it just makes RLS-touching reads throw. This
function does the lookup as the postgres owner so the route can
keep running under tenancy for everything that comes after.

Revision ID: f6a8c0e2g4h6
Revises: e5f7b9c1d3a2
Create Date: 2026-05-24 08:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f6a8c0e2g4h6"
down_revision: str | None = "e5f7b9c1d3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.resolve_org_membership(
            p_subject text,
            p_slug text
        )
        RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, app
        AS $$
        DECLARE
            result jsonb;
        BEGIN
            SELECT jsonb_build_object(
                'user_id', u.id,
                'organization_id', o.id,
                'organization_slug', o.slug,
                'role', m.role
            )
            INTO result
            FROM organizations o
            JOIN memberships m ON m.org_id = o.id
            JOIN users u ON u.id = m.user_id
            WHERE o.slug = p_slug
              AND u.keycloak_subject = p_subject
              AND o.status <> 'deleted'
            LIMIT 1;
            RETURN result;
        END;
        $$;
        """
    )
    op.execute("REVOKE EXECUTE ON FUNCTION app.resolve_org_membership(text, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.resolve_org_membership(text, text) TO verolas_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app.resolve_org_membership(text, text)")
