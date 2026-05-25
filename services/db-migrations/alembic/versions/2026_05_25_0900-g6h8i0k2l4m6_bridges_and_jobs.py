"""Verolas Bridge: on-prem agent enrollment + job queue.

Tier C connectors (SOFiSTiK, Tekla, RFEM/RSTAB, SAP2000/ETABS, STAAD,
IDEA StatiCa, Plaxis, ProjectWise, Rhino, D-Trust QES) cannot be
reached from the cloud directly; the vendor software runs on the
engineer's Windows workstation. A firm installs the Verolas Bridge
agent inside their network. The agent long-polls the cloud for jobs,
executes them against the locally installed tool, and streams the
output back through pre-signed S3 PUTs.

Two tables:

- `bridges` is one row per agent install. The org admin enrols a
  bridge from the Integrations page; the cloud mints a long-lived
  token (the secret is hashed before storage) and surfaces the
  enrollment string once.
- `bridge_jobs` is the queue. A row appears whenever an `agent_run`
  needs a Tier C tool; the bridge picks it up, runs the tool, writes
  the result back. Org-scoped under RLS so one firm's bridges never
  see another's jobs.

Revision ID: g6h8i0k2l4m6
Revises: f4g6h8i0j2k4
Create Date: 2026-05-25 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g6h8i0k2l4m6"
down_revision: str | None = "f4g6h8i0j2k4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE bridge_status AS ENUM (
            'pending',
            'active',
            'offline',
            'revoked'
        )
        """
    )
    op.execute(
        """
        CREATE TYPE bridge_job_status AS ENUM (
            'queued',
            'in_progress',
            'completed',
            'failed',
            'cancelled'
        )
        """
    )

    op.create_table(
        "bridges",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("secret_hash", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "active",
                "offline",
                "revoked",
                name="bridge_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "supported_tools",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column("hostname", sa.Text, nullable=True),
        sa.Column("agent_version", sa.Text, nullable=True),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
    op.create_index("bridges_org_idx", "bridges", ["org_id"])

    op.create_table(
        "bridge_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bridge_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bridges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "agent_run_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("class_id", sa.Text, nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "in_progress",
                "completed",
                "failed",
                "cancelled",
                name="bridge_job_status",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("result", sa.dialects.postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("bridge_jobs_bridge_idx", "bridge_jobs", ["bridge_id"])
    op.create_index(
        "bridge_jobs_pending_idx",
        "bridge_jobs",
        ["bridge_id"],
        postgresql_where=sa.text("status = 'queued'"),
    )

    for table in ("bridges", "bridge_jobs"):
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
        CREATE TRIGGER bridges_updated_at
        BEFORE UPDATE ON bridges
        FOR EACH ROW
        EXECUTE FUNCTION app.connector_installations_set_updated_at()
        """
    )
    op.execute(
        """
        CREATE TRIGGER bridge_jobs_updated_at
        BEFORE UPDATE ON bridge_jobs
        FOR EACH ROW
        EXECUTE FUNCTION app.connector_installations_set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS bridge_jobs_updated_at ON bridge_jobs")
    op.execute("DROP TRIGGER IF EXISTS bridges_updated_at ON bridges")
    for table in ("bridge_jobs", "bridges"):
        for action in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            policy = (
                f"{table}_{action.lower()}_in_org"
                if action != "SELECT"
                else f"{table}_visible_to_org"
            )
            op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS bridge_jobs_pending_idx")
    op.drop_index("bridge_jobs_bridge_idx", table_name="bridge_jobs")
    op.drop_table("bridge_jobs")
    op.drop_index("bridges_org_idx", table_name="bridges")
    op.drop_table("bridges")
    op.execute("DROP TYPE IF EXISTS bridge_job_status")
    op.execute("DROP TYPE IF EXISTS bridge_status")
