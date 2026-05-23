"""initial tenancy schema

Revision ID: a1c0d3e5f7b9
Revises:
Create Date: 2026-05-23 12:00:00.000000+00:00

Creates the multi tenant identity model: organizations, users, memberships,
role enum, plus the tenant scoping primitives (session variable getter and the
row level security policies that read it).

Tables created:
- organizations (the tenant boundary)
- users (global identity, no tenant scoping)
- memberships (which users belong to which orgs, with what role)

RBAC roles, in increasing privilege:
- viewer:   read only on projects and deliverables
- auditor:  read only on audit logs
- engineer: edits projects, runs workflows
- reviewer: reviews deliverables and signs off
- admin:    org management except billing and ownership transfer
- owner:    full org access

Tenant scoping:
- `app.current_org_id` is a PostgreSQL session variable set by the API layer
  on every request. RLS policies reference this variable.
- Helper functions `app.current_org_id()` and `app.is_member()` are created so
  policies stay readable. Application code uses `SET LOCAL app.current_org_id`
  inside a transaction so the value never leaks across requests.

The application layer (services/auth/) verifies the access token, extracts the
selected `org_id`, and sets the session variable before any query runs.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c0d3e5f7b9"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS app")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.current_org_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        AS $$
            SELECT NULLIF(current_setting('app.current_org_id', true), '')::uuid
        $$;
        """
    )

    org_status = sa.Enum("active", "suspended", "deleted", name="organization_status")
    org_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False, unique=True),
        sa.Column("plan", sa.Text, nullable=False, server_default=sa.text("'free'")),
        sa.Column(
            "status",
            sa.Enum(
                "active", "suspended", "deleted", name="organization_status", create_type=False
            ),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    user_status = sa.Enum("active", "invited", "suspended", "deleted", name="user_status")
    user_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("keycloak_subject", sa.Text, nullable=True, unique=True),
        sa.Column(
            "status",
            sa.Enum(
                "active", "invited", "suspended", "deleted", name="user_status", create_type=False
            ),
            nullable=False,
            server_default=sa.text("'invited'"),
        ),
        sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("totp_secret_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    role_enum = sa.Enum(
        "owner",
        "admin",
        "reviewer",
        "engineer",
        "viewer",
        "auditor",
        name="membership_role",
    )
    role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "memberships",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum(
                "owner",
                "admin",
                "reviewer",
                "engineer",
                "viewer",
                "auditor",
                name="membership_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("invited_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "org_id", name="memberships_user_org_unique"),
    )

    op.create_index("memberships_org_idx", "memberships", ["org_id"])
    op.create_index("memberships_user_idx", "memberships", ["user_id"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.is_member(target_org_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM memberships
                WHERE org_id = target_org_id
                  AND user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            )
        $$;
        """
    )

    # RLS on the tenant scoped tables. Organizations is special: row visibility
    # is controlled by membership, not by current_org_id, so a user can list
    # all orgs they belong to via a subquery. Memberships are also visible per
    # user. Application tables added later all carry org_id and use the
    # standard "org_id = app.current_org_id()" policy.

    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY organizations_visible_to_members ON organizations
        FOR ALL
        USING (
            id = app.current_org_id()
            OR app.is_member(id)
        )
        WITH CHECK (id = app.current_org_id() OR app.is_member(id));
        """
    )

    op.execute("ALTER TABLE memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY memberships_visible_to_org ON memberships
        FOR ALL
        USING (
            org_id = app.current_org_id()
            OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
        WITH CHECK (org_id = app.current_org_id());
        """
    )

    # users table is global identity, not tenant scoped. RLS is on but the
    # policy lets a user see their own row plus any user in their orgs.
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY users_visible_to_self_or_org_member ON users
        FOR ALL
        USING (
            id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            OR id IN (
                SELECT user_id FROM memberships WHERE org_id = app.current_org_id()
            )
        )
        WITH CHECK (id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
        """
    )

    # The verolas_app role uses the policies above. Superuser bypasses RLS by
    # default; this is intentional so migrations and operator queries are not
    # blocked. The application connects as verolas_app, not as superuser.


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS users_visible_to_self_or_org_member ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS memberships_visible_to_org ON memberships")
    op.execute("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS organizations_visible_to_members ON organizations")
    op.execute("ALTER TABLE organizations DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS app.is_member(uuid)")

    op.drop_index("memberships_user_idx", table_name="memberships")
    op.drop_index("memberships_org_idx", table_name="memberships")
    op.drop_table("memberships")
    sa.Enum(name="membership_role").drop(op.get_bind(), checkfirst=True)

    op.drop_table("users")
    sa.Enum(name="user_status").drop(op.get_bind(), checkfirst=True)

    op.drop_table("organizations")
    sa.Enum(name="organization_status").drop(op.get_bind(), checkfirst=True)

    op.execute("DROP FUNCTION IF EXISTS app.current_org_id()")
    op.execute("DROP SCHEMA IF EXISTS app")
