"""Connector installations + bindings.

Two-layer model:

- `connector_installations` is one row per org per connector class.
  The org's IT admin installs a class (SharePoint, Autodesk APS,
  Procore, Verolas Library, ...) once for the firm. Credentials,
  OAuth scopes, and the vendor account live here.

- `connector_bindings` is one row per project per instance. The
  project manager picks a specific resource (which SharePoint
  library, which ACC hub, which Slack channel) from the pool the
  org install grants.

- `connector_waitlist` captures org-level interest in Tier C
  connectors that need partner agreements before they can ship live.

Revision ID: c0e2f4g6h8i0
Revises: b8c0d2e4f6g8
Create Date: 2026-05-24 11:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c0e2f4g6h8i0"
down_revision: str | None = "b8c0d2e4f6g8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE connector_install_status AS ENUM (
            'pending',
            'installed',
            'error',
            'uninstalled'
        )
        """
    )
    op.execute(
        """
        CREATE TYPE connector_binding_status AS ENUM (
            'active',
            'paused',
            'error'
        )
        """
    )

    op.create_table(
        "connector_installations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("class_id", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "installed",
                "error",
                "uninstalled",
                name="connector_install_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "installed_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scopes", sa.dialects.postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "oauth_account",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "credentials",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
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
        sa.UniqueConstraint("org_id", "class_id", name="connector_installations_org_class_unique"),
    )
    op.create_index("connector_installations_org_idx", "connector_installations", ["org_id"])

    op.create_table(
        "connector_bindings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "installation_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connector_installations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("instance_ref", sa.Text, nullable=False),
        sa.Column("instance_label", sa.Text, nullable=False),
        sa.Column("config", sa.dialects.postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "paused",
                "error",
                name="connector_binding_status",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
    op.create_index("connector_bindings_project_idx", "connector_bindings", ["project_id"])
    op.create_index(
        "connector_bindings_installation_idx", "connector_bindings", ["installation_id"]
    )

    op.create_table(
        "connector_waitlist",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("class_id", sa.Text, nullable=False),
        sa.Column(
            "requested_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("org_id", "class_id", name="connector_waitlist_org_class_unique"),
    )

    # Row-level security: same shape as projects (org-scoped).
    for table in ("connector_installations", "connector_bindings", "connector_waitlist"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_visible_to_org ON {table} "
            f"FOR SELECT USING (org_id = app.current_org_id())"
        )
        op.execute(
            f"CREATE POLICY {table}_insert_in_org ON {table} "
            f"FOR INSERT WITH CHECK (org_id = app.current_org_id())"
        )
        op.execute(
            f"CREATE POLICY {table}_update_in_org ON {table} "
            f"FOR UPDATE USING (org_id = app.current_org_id()) "
            f"WITH CHECK (org_id = app.current_org_id())"
        )
        op.execute(
            f"CREATE POLICY {table}_delete_in_org ON {table} "
            f"FOR DELETE USING (org_id = app.current_org_id())"
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.connector_installations_set_updated_at()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER connector_installations_updated_at
        BEFORE UPDATE ON connector_installations
        FOR EACH ROW
        EXECUTE FUNCTION app.connector_installations_set_updated_at()
        """
    )
    op.execute(
        """
        CREATE TRIGGER connector_bindings_updated_at
        BEFORE UPDATE ON connector_bindings
        FOR EACH ROW
        EXECUTE FUNCTION app.connector_installations_set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS connector_bindings_updated_at ON connector_bindings")
    op.execute(
        "DROP TRIGGER IF EXISTS connector_installations_updated_at ON connector_installations"
    )
    op.execute("DROP FUNCTION IF EXISTS app.connector_installations_set_updated_at()")
    for table in ("connector_waitlist", "connector_bindings", "connector_installations"):
        for action in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            policy = (
                f"{table}_{action.lower()}_in_org"
                if action != "SELECT"
                else f"{table}_visible_to_org"
            )
            op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.drop_table(table)
    op.execute("DROP TYPE IF EXISTS connector_binding_status")
    op.execute("DROP TYPE IF EXISTS connector_install_status")
