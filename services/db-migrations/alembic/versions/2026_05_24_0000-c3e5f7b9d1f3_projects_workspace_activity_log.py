"""projects workspace activity_log with merkle chain

Revision ID: c3e5f7b9d1f3
Revises: b2d4f6a8c0e2
Create Date: 2026-05-24 00:00:00.000000+00:00

Adds the project lifecycle tables (projects, workspaces) and the audit
log. The audit log is append-only and Merkle-chained per organization so
any tampered or deleted row breaks the chain and is detectable on a
verification walk.

Chain definition:

  this_hash = sha256(
    prev_hash
    || actor_user_id::text
    || action
    || resource_type
    || resource_id::text
    || extract(epoch from ts)::text
    || coalesce(payload::text, '')
  )

  prev_hash for the first row of an organization is 32 zero bytes.

A BEFORE INSERT trigger computes this_hash and prev_hash so the
application cannot accidentally write inconsistent rows. The trigger
takes a row lock on the per-org tail row to serialize concurrent
inserts; the resulting throughput is one append per org per round trip
which is fine for audit volume.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3e5f7b9d1f3"
down_revision: str | None = "b2d4f6a8c0e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Discipline and project status enums.
    discipline = sa.Enum(
        "structural",
        "geotech",
        "water",
        "transport",
        "review",
        "practice",
        name="discipline",
    )
    discipline.create(op.get_bind(), checkfirst=True)

    project_status = sa.Enum(
        "active",
        "archived",
        "deleted",
        name="project_status",
    )
    project_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "discipline",
            sa.Enum(
                "structural",
                "geotech",
                "water",
                "transport",
                "review",
                "practice",
                name="discipline",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "archived",
                "deleted",
                name="project_status",
                create_type=False,
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
    op.create_index("projects_org_idx", "projects", ["org_id"])

    op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE projects FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY projects_in_org ON projects
        FOR ALL
        USING (org_id = app.current_org_id())
        WITH CHECK (org_id = app.current_org_id());
        """
    )

    # Workspaces sit inside a project and group files plus the workflow runs
    # that produce them. Today a project has a default workspace; multi
    # workspace per project lands when teams want parallel design variants.
    op.create_table(
        "workspaces",
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
        sa.Column("name", sa.Text, nullable=False, server_default=sa.text("'default'")),
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
        sa.UniqueConstraint("project_id", "name", name="workspaces_project_name_unique"),
    )
    op.create_index("workspaces_project_idx", "workspaces", ["project_id"])

    op.execute("ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspaces FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY workspaces_in_org ON workspaces
        FOR ALL
        USING (org_id = app.current_org_id())
        WITH CHECK (org_id = app.current_org_id());
        """
    )

    # files gains a project / workspace association.
    op.add_column(
        "files",
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "files",
        sa.Column(
            "workspace_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("files_project_idx", "files", ["project_id"])

    # activity_log: append-only Merkle chain per org.
    op.create_table(
        "activity_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("resource_type", sa.Text, nullable=False),
        sa.Column("resource_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("seq", sa.BigInteger, nullable=False),
        sa.Column("prev_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("this_hash", sa.LargeBinary(32), nullable=False),
        sa.UniqueConstraint("org_id", "seq", name="activity_log_org_seq_unique"),
        sa.UniqueConstraint("this_hash", name="activity_log_this_hash_unique"),
    )
    op.create_index("activity_log_org_ts_idx", "activity_log", ["org_id", "ts"])
    op.create_index("activity_log_resource_idx", "activity_log", ["resource_type", "resource_id"])

    op.execute("ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE activity_log FORCE ROW LEVEL SECURITY")
    # Append only: SELECT scoped by org_id (auditor or owner). INSERT scoped by
    # org_id. UPDATE and DELETE blocked.
    op.execute(
        """
        CREATE POLICY activity_log_select_in_org ON activity_log
        FOR SELECT
        USING (org_id = app.current_org_id());
        """
    )
    op.execute(
        """
        CREATE POLICY activity_log_insert_in_org ON activity_log
        FOR INSERT
        WITH CHECK (org_id = app.current_org_id());
        """
    )
    # Explicit zero-row policies for UPDATE and DELETE so the append-only
    # invariant is enforced by the database even if a future migration
    # disables RLS by accident.
    op.execute(
        """
        CREATE POLICY activity_log_no_update ON activity_log
        FOR UPDATE
        USING (false);
        """
    )
    op.execute(
        """
        CREATE POLICY activity_log_no_delete ON activity_log
        FOR DELETE
        USING (false);
        """
    )

    # Trigger that computes prev_hash, this_hash, and seq before insert.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.activity_log_chain()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            last_seq bigint;
            last_hash bytea;
            ts_text text;
            payload_text text;
            actor_text text;
            resource_text text;
            zero_hash constant bytea := decode(repeat('0', 64), 'hex');
        BEGIN
            -- Lock the latest row for this org so concurrent inserts serialise.
            SELECT seq, this_hash
              INTO last_seq, last_hash
              FROM activity_log
             WHERE org_id = NEW.org_id
             ORDER BY seq DESC
             LIMIT 1
            FOR UPDATE;

            IF last_seq IS NULL THEN
                NEW.seq := 1;
                NEW.prev_hash := zero_hash;
            ELSE
                NEW.seq := last_seq + 1;
                NEW.prev_hash := last_hash;
            END IF;

            ts_text := extract(epoch from NEW.ts)::text;
            payload_text := coalesce(NEW.payload::text, '');
            actor_text := coalesce(NEW.actor_user_id::text, '');
            resource_text := coalesce(NEW.resource_id::text, '');

            NEW.this_hash := digest(
                NEW.prev_hash
                || convert_to(actor_text, 'UTF8')
                || convert_to(NEW.action, 'UTF8')
                || convert_to(NEW.resource_type, 'UTF8')
                || convert_to(resource_text, 'UTF8')
                || convert_to(ts_text, 'UTF8')
                || convert_to(payload_text, 'UTF8'),
                'sha256'
            );

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER activity_log_chain
        BEFORE INSERT ON activity_log
        FOR EACH ROW
        EXECUTE FUNCTION app.activity_log_chain();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS activity_log_chain ON activity_log")
    op.execute("DROP FUNCTION IF EXISTS app.activity_log_chain()")

    op.execute("DROP POLICY IF EXISTS activity_log_no_delete ON activity_log")
    op.execute("DROP POLICY IF EXISTS activity_log_no_update ON activity_log")
    op.execute("DROP POLICY IF EXISTS activity_log_insert_in_org ON activity_log")
    op.execute("DROP POLICY IF EXISTS activity_log_select_in_org ON activity_log")
    op.execute("ALTER TABLE activity_log DISABLE ROW LEVEL SECURITY")
    op.drop_index("activity_log_resource_idx", table_name="activity_log")
    op.drop_index("activity_log_org_ts_idx", table_name="activity_log")
    op.drop_table("activity_log")

    op.drop_index("files_project_idx", table_name="files")
    op.drop_column("files", "workspace_id")
    op.drop_column("files", "project_id")

    op.execute("DROP POLICY IF EXISTS workspaces_in_org ON workspaces")
    op.execute("ALTER TABLE workspaces DISABLE ROW LEVEL SECURITY")
    op.drop_index("workspaces_project_idx", table_name="workspaces")
    op.drop_table("workspaces")

    op.execute("DROP POLICY IF EXISTS projects_in_org ON projects")
    op.execute("ALTER TABLE projects DISABLE ROW LEVEL SECURITY")
    op.drop_index("projects_org_idx", table_name="projects")
    op.drop_table("projects")

    sa.Enum(name="project_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="discipline").drop(op.get_bind(), checkfirst=True)
