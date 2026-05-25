"""Workflow engine: templates, versions, runs, run nodes, run events.

Five tables that together implement the workflow system described in
verolas-workflow-bible.md.

- `workflow_templates` holds the catalog of templates. A template with
  org_id NULL is a Verolas-global template (synced from code). A template
  with org_id set is owned by that firm, often forked from a global one.
- `workflow_template_versions` is the immutable version history of each
  template. A run pins to one version. Editing a template never mutates
  prior versions; it appends a new one.
- `workflow_runs` is one execution of one template against one project.
- `workflow_run_nodes` is the per-node runtime state inside a run. Status
  goes pending -> ready -> running -> completed (or skipped / failed).
  Gate nodes carry an `gate_decision` value when an approver acts.
- `workflow_run_events` is the append-only audit log. The final state of
  a run can be derived by replaying events.

All tables FORCE ROW LEVEL SECURITY. The template table has a special
SELECT policy that lets every org read global rows (org_id IS NULL); all
other tables follow the standard org-scoped pattern.

Revision ID: h7i9k1m3n5o7
Revises: g6h8i0k2l4m6
Create Date: 2026-05-25 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h7i9k1m3n5o7"
down_revision: str | None = "g6h8i0k2l4m6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enums.
    op.execute(
        """
        CREATE TYPE workflow_template_source AS ENUM ('code', 'ui')
        """
    )
    op.execute(
        """
        CREATE TYPE workflow_run_status AS ENUM (
            'pending', 'running', 'paused', 'completed', 'failed', 'cancelled'
        )
        """
    )
    op.execute(
        """
        CREATE TYPE workflow_node_status AS ENUM (
            'pending', 'ready', 'running', 'paused', 'completed',
            'failed', 'skipped'
        )
        """
    )

    # workflow_templates: catalog. Global templates (org_id NULL) are
    # Verolas-authored. Per-org templates are firm-owned forks.
    op.create_table(
        "workflow_templates",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("jurisdiction", sa.Text, nullable=True),
        sa.Column("project_type", sa.Text, nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "code",
                "ui",
                name="workflow_template_source",
                create_type=False,
            ),
            nullable=False,
            server_default="code",
        ),
        sa.Column(
            "forked_from_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
    # slug is unique per ownership scope: global templates share one
    # namespace, each org has its own.
    op.execute(
        "CREATE UNIQUE INDEX workflow_templates_global_slug_idx "
        "ON workflow_templates (slug) WHERE org_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX workflow_templates_org_slug_idx "
        "ON workflow_templates (org_id, slug) WHERE org_id IS NOT NULL"
    )
    op.create_index(
        "workflow_templates_jurisdiction_idx",
        "workflow_templates",
        ["jurisdiction"],
    )

    # workflow_template_versions: immutable history.
    op.create_table(
        "workflow_template_versions",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "template_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("definition", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("definition_hash", sa.Text, nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "authored_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "authored_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "template_id",
            "version",
            name="workflow_template_versions_unique_version",
        ),
    )
    op.create_index(
        "workflow_template_versions_template_idx",
        "workflow_template_versions",
        ["template_id"],
    )

    # workflow_runs: one execution.
    op.create_table(
        "workflow_runs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
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
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "template_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_template_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "paused",
                "completed",
                "failed",
                "cancelled",
                name="workflow_run_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "started_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "context",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
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
    op.create_index("workflow_runs_org_idx", "workflow_runs", ["org_id"])
    op.create_index("workflow_runs_project_idx", "workflow_runs", ["project_id"])
    op.create_index("workflow_runs_status_idx", "workflow_runs", ["status"])

    # workflow_run_nodes: per-node runtime state. node_key is the stable
    # identifier from the template definition (e.g. "lp4_compile_statik").
    op.create_table(
        "workflow_run_nodes",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_key", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "ready",
                "running",
                "paused",
                "completed",
                "failed",
                "skipped",
                name="workflow_node_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "assignee_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("gate_decision", sa.Text, nullable=True),
        sa.Column(
            "inputs",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "outputs",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "params",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.TIMESTAMP(timezone=True),
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
        sa.UniqueConstraint("run_id", "node_key", name="workflow_run_nodes_unique_node"),
    )
    op.create_index("workflow_run_nodes_run_idx", "workflow_run_nodes", ["run_id"])
    op.create_index(
        "workflow_run_nodes_status_idx",
        "workflow_run_nodes",
        ["run_id", "status"],
    )

    # workflow_run_events: append-only audit log.
    op.create_table(
        "workflow_run_events",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "node_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_run_nodes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "actor_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "workflow_run_events_run_idx",
        "workflow_run_events",
        ["run_id", "occurred_at"],
    )

    # RLS policies for the org-scoped tables. workflow_templates is
    # special because global rows (org_id NULL) must be readable by every
    # org member.
    for table in (
        "workflow_runs",
        "workflow_run_nodes",
        "workflow_run_events",
    ):
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

    # workflow_templates: globals readable by any org, writes only on
    # org-owned rows. Global templates are seeded with the bypass-RLS
    # bootstrap connection.
    op.execute("ALTER TABLE workflow_templates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workflow_templates FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY workflow_templates_visible_to_org ON workflow_templates "
        "FOR SELECT USING (org_id IS NULL OR org_id = app.current_org_id())"
    )
    op.execute(
        "CREATE POLICY workflow_templates_insert_in_org ON workflow_templates "
        "FOR INSERT WITH CHECK (org_id = app.current_org_id())"
    )
    op.execute(
        "CREATE POLICY workflow_templates_update_in_org ON workflow_templates "
        "FOR UPDATE USING (org_id = app.current_org_id()) "
        "WITH CHECK (org_id = app.current_org_id())"
    )
    op.execute(
        "CREATE POLICY workflow_templates_delete_in_org ON workflow_templates "
        "FOR DELETE USING (org_id = app.current_org_id())"
    )

    # workflow_template_versions: visibility follows the parent template.
    # A version is readable if its template row is readable.
    op.execute("ALTER TABLE workflow_template_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workflow_template_versions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY workflow_template_versions_visible ON "
        "workflow_template_versions FOR SELECT USING ("
        "EXISTS (SELECT 1 FROM workflow_templates t "
        "WHERE t.id = workflow_template_versions.template_id "
        "AND (t.org_id IS NULL OR t.org_id = app.current_org_id())))"
    )
    op.execute(
        "CREATE POLICY workflow_template_versions_insert ON "
        "workflow_template_versions FOR INSERT WITH CHECK ("
        "EXISTS (SELECT 1 FROM workflow_templates t "
        "WHERE t.id = workflow_template_versions.template_id "
        "AND t.org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE POLICY workflow_template_versions_update ON "
        "workflow_template_versions FOR UPDATE USING ("
        "EXISTS (SELECT 1 FROM workflow_templates t "
        "WHERE t.id = workflow_template_versions.template_id "
        "AND t.org_id = app.current_org_id())) "
        "WITH CHECK ("
        "EXISTS (SELECT 1 FROM workflow_templates t "
        "WHERE t.id = workflow_template_versions.template_id "
        "AND t.org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE POLICY workflow_template_versions_delete ON "
        "workflow_template_versions FOR DELETE USING ("
        "EXISTS (SELECT 1 FROM workflow_templates t "
        "WHERE t.id = workflow_template_versions.template_id "
        "AND t.org_id = app.current_org_id()))"
    )

    # updated_at triggers.
    for table in (
        "workflow_templates",
        "workflow_runs",
        "workflow_run_nodes",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_updated_at "
            f"BEFORE UPDATE ON {table} "
            f"FOR EACH ROW "
            f"EXECUTE FUNCTION app.connector_installations_set_updated_at()"
        )

    # SECURITY DEFINER function for syncing code-authored Verolas-global
    # templates. The API role cannot write org_id=NULL rows under FORCE
    # RLS, so the sync goes through this function which runs as the
    # owner (postgres) and bypasses RLS.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.upsert_global_workflow_template(
            p_slug text,
            p_name text,
            p_description text,
            p_jurisdiction text,
            p_project_type text,
            p_definition jsonb,
            p_definition_hash text
        )
        RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, app
        AS $$
        DECLARE
            template_row workflow_templates%ROWTYPE;
            latest_version workflow_template_versions%ROWTYPE;
            new_version_row workflow_template_versions%ROWTYPE;
            next_version int;
            action text;
        BEGIN
            -- Find or create the template catalog row.
            SELECT * INTO template_row
            FROM workflow_templates
            WHERE org_id IS NULL AND slug = p_slug;

            IF NOT FOUND THEN
                INSERT INTO workflow_templates (
                    org_id, slug, name, description,
                    jurisdiction, project_type, source
                )
                VALUES (
                    NULL, p_slug, p_name, p_description,
                    p_jurisdiction, p_project_type, 'code'
                )
                RETURNING * INTO template_row;
                action := 'created_template';
            ELSE
                -- Keep catalog metadata in sync with code on every call.
                UPDATE workflow_templates
                SET name = p_name,
                    description = p_description,
                    jurisdiction = p_jurisdiction,
                    project_type = p_project_type,
                    updated_at = now()
                WHERE id = template_row.id;
            END IF;

            -- Compare against the latest active version.
            SELECT * INTO latest_version
            FROM workflow_template_versions
            WHERE template_id = template_row.id AND is_active = true
            ORDER BY version DESC
            LIMIT 1;

            IF FOUND AND latest_version.definition_hash = p_definition_hash THEN
                RETURN jsonb_build_object(
                    'template_id', template_row.id,
                    'version_id', latest_version.id,
                    'version', latest_version.version,
                    'action', 'unchanged'
                );
            END IF;

            -- Deactivate prior active version(s) and mint a new one.
            UPDATE workflow_template_versions
            SET is_active = false
            WHERE template_id = template_row.id AND is_active = true;

            SELECT COALESCE(MAX(version), 0) + 1 INTO next_version
            FROM workflow_template_versions
            WHERE template_id = template_row.id;

            INSERT INTO workflow_template_versions (
                template_id, version, definition, definition_hash,
                is_active, authored_by_user_id, authored_at
            )
            VALUES (
                template_row.id, next_version, p_definition,
                p_definition_hash, true, NULL, now()
            )
            RETURNING * INTO new_version_row;

            IF action IS NULL THEN
                action := 'new_version';
            END IF;

            RETURN jsonb_build_object(
                'template_id', template_row.id,
                'version_id', new_version_row.id,
                'version', new_version_row.version,
                'action', action
            );
        END;
        $$
        """
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION app.upsert_global_workflow_template("
        "text, text, text, text, text, jsonb, text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.upsert_global_workflow_template("
        "text, text, text, text, text, jsonb, text) TO verolas_app"
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS app.upsert_global_workflow_template("
        "text, text, text, text, text, jsonb, text)"
    )
    for table in (
        "workflow_templates",
        "workflow_runs",
        "workflow_run_nodes",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_updated_at ON {table}")

    op.execute(
        "DROP POLICY IF EXISTS workflow_template_versions_visible ON workflow_template_versions"
    )
    op.execute(
        "DROP POLICY IF EXISTS workflow_template_versions_insert ON workflow_template_versions"
    )
    op.execute(
        "DROP POLICY IF EXISTS workflow_template_versions_update ON workflow_template_versions"
    )
    op.execute(
        "DROP POLICY IF EXISTS workflow_template_versions_delete ON workflow_template_versions"
    )
    op.execute("ALTER TABLE workflow_template_versions DISABLE ROW LEVEL SECURITY")

    for table in (
        "workflow_templates",
        "workflow_runs",
        "workflow_run_nodes",
        "workflow_run_events",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_visible_to_org ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert_in_org ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_update_in_org ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_delete_in_org ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS workflow_run_events_run_idx")
    op.drop_table("workflow_run_events")

    op.execute("DROP INDEX IF EXISTS workflow_run_nodes_status_idx")
    op.execute("DROP INDEX IF EXISTS workflow_run_nodes_run_idx")
    op.drop_table("workflow_run_nodes")

    op.execute("DROP INDEX IF EXISTS workflow_runs_status_idx")
    op.execute("DROP INDEX IF EXISTS workflow_runs_project_idx")
    op.execute("DROP INDEX IF EXISTS workflow_runs_org_idx")
    op.drop_table("workflow_runs")

    op.execute("DROP INDEX IF EXISTS workflow_template_versions_template_idx")
    op.drop_table("workflow_template_versions")

    op.execute("DROP INDEX IF EXISTS workflow_templates_jurisdiction_idx")
    op.execute("DROP INDEX IF EXISTS workflow_templates_org_slug_idx")
    op.execute("DROP INDEX IF EXISTS workflow_templates_global_slug_idx")
    op.drop_table("workflow_templates")

    op.execute("DROP TYPE IF EXISTS workflow_node_status")
    op.execute("DROP TYPE IF EXISTS workflow_run_status")
    op.execute("DROP TYPE IF EXISTS workflow_template_source")
