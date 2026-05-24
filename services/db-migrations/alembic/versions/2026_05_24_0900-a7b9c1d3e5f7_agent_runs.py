"""Agent runs as first-class objects.

Every Verolas deliverable is the output of an agent run. This table
makes that explicit: each run has a brief, a plan, a current step,
streaming progress, and a result. Runs are org-scoped via project_id
and inherit the same row-level security as projects.

The activity_log already records who did what, but agent runs are a
distinct lifecycle (queued -> running -> completed) that the audit log
chain hashes do not capture. Runs reference their corresponding
audit-log seq so a reviewer can pivot from a sign-off to the exact
run that produced the artefact under review.

Revision ID: a7b9c1d3e5f7
Revises: f6a8c0e2g4h6
Create Date: 2026-05-24 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b9c1d3e5f7"
down_revision: str | None = "f6a8c0e2g4h6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE agent_run_status AS ENUM (
            'queued',
            'running',
            'blocked',
            'completed',
            'failed',
            'cancelled'
        )
        """
    )
    op.execute(
        """
        CREATE TYPE agent_run_trigger AS ENUM (
            'manual',
            'schedule',
            'event'
        )
        """
    )

    op.create_table(
        "agent_runs",
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
        sa.Column("agent_id", sa.Text, nullable=False),
        sa.Column("agent_name", sa.Text, nullable=False),
        sa.Column("tier", sa.SmallInteger, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "blocked",
                "completed",
                "failed",
                "cancelled",
                name="agent_run_status",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "trigger",
            sa.Enum(
                "manual",
                "schedule",
                "event",
                name="agent_run_trigger",
                create_type=False,
            ),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "triggered_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("brief", sa.Text, nullable=False),
        sa.Column(
            "plan",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_percent", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column(
            "result",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("cost_micro_usd", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("audit_chain_seq", sa.BigInteger, nullable=True),
        sa.Column(
            "queued_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
    op.create_index("agent_runs_project_idx", "agent_runs", ["project_id"])
    op.create_index("agent_runs_org_idx", "agent_runs", ["org_id"])
    op.create_index(
        "agent_runs_active_idx",
        "agent_runs",
        ["project_id", "status"],
        postgresql_where=sa.text("status IN ('queued', 'running', 'blocked')"),
    )

    # Row-level security: same shape as projects (org-scoped).
    op.execute("ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agent_runs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY agent_runs_visible_to_org ON agent_runs
            FOR SELECT
            USING (org_id = app.current_org_id())
        """
    )
    op.execute(
        """
        CREATE POLICY agent_runs_insert_in_org ON agent_runs
            FOR INSERT
            WITH CHECK (org_id = app.current_org_id())
        """
    )
    op.execute(
        """
        CREATE POLICY agent_runs_update_in_org ON agent_runs
            FOR UPDATE
            USING (org_id = app.current_org_id())
            WITH CHECK (org_id = app.current_org_id())
        """
    )

    # updated_at trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.agent_runs_set_updated_at()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER agent_runs_updated_at
        BEFORE UPDATE ON agent_runs
        FOR EACH ROW
        EXECUTE FUNCTION app.agent_runs_set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS agent_runs_updated_at ON agent_runs")
    op.execute("DROP FUNCTION IF EXISTS app.agent_runs_set_updated_at()")
    op.execute("DROP POLICY IF EXISTS agent_runs_update_in_org ON agent_runs")
    op.execute("DROP POLICY IF EXISTS agent_runs_insert_in_org ON agent_runs")
    op.execute("DROP POLICY IF EXISTS agent_runs_visible_to_org ON agent_runs")
    op.execute("ALTER TABLE agent_runs DISABLE ROW LEVEL SECURITY")
    op.drop_index("agent_runs_active_idx", table_name="agent_runs")
    op.drop_index("agent_runs_org_idx", table_name="agent_runs")
    op.drop_index("agent_runs_project_idx", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.execute("DROP TYPE IF EXISTS agent_run_trigger")
    op.execute("DROP TYPE IF EXISTS agent_run_status")
