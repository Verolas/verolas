"""Workflow documents: editable, project-scoped instances of workflow graphs.

After stage 1-3, workflows lived only as Verolas-global templates plus
runs. Stage 4 adds a project-scoped editable layer: a "document" sits
in a folder, has a name, references the template it was forked from
(or NULL for a blank document), and carries its own definition JSONB
the user can edit.

Runs gain a `document_id` foreign key plus `definition_snapshot`. When
a run is created from a document, the document's current definition is
snapshotted into the run row. This keeps runs immutable even if the
user later edits the document, without us having to version the
document explicitly.

Both `template_id` and `template_version_id` on `workflow_runs` become
nullable. A run is rooted in either a global template (legacy path,
used by hello-workflow runs created via the API directly) or a project
document (new path). The check constraint enforces exactly one root.

Revision ID: i8j0l2m4n6o8
Revises: h7i9k1m3n5o7
Create Date: 2026-05-25 11:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "i8j0l2m4n6o8"
down_revision: str | None = "h7i9k1m3n5o7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_documents",
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
        # Free-text path. "/" for the root; "/Statik/Wohngebäude" for a
        # nested folder. We do not materialize folders as their own
        # rows; the gallery groups documents by string prefix.
        sa.Column(
            "folder",
            sa.Text,
            nullable=False,
            server_default="/",
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "source_template_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_template_version_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_template_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # The editable graph. Same shape as workflow_template_versions.definition
        # (a TemplateDefinition: nodes, edges, entry_keys).
        sa.Column("definition", sa.dialects.postgresql.JSONB, nullable=False),
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
        # name unique per (project, folder). Two docs can share a name
        # if they live in different folders, same as filesystems.
        sa.UniqueConstraint("project_id", "folder", "name", name="workflow_documents_unique_name"),
    )
    op.create_index(
        "workflow_documents_project_idx",
        "workflow_documents",
        ["project_id"],
    )
    op.create_index(
        "workflow_documents_folder_idx",
        "workflow_documents",
        ["project_id", "folder"],
    )

    # RLS for documents.
    op.execute("ALTER TABLE workflow_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workflow_documents FORCE ROW LEVEL SECURITY")
    for action in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        if action == "SELECT":
            op.execute(
                "CREATE POLICY workflow_documents_visible_to_org "
                "ON workflow_documents "
                "FOR SELECT USING (org_id = app.current_org_id())"
            )
        elif action == "INSERT":
            op.execute(
                "CREATE POLICY workflow_documents_insert_in_org "
                "ON workflow_documents "
                "FOR INSERT WITH CHECK (org_id = app.current_org_id())"
            )
        elif action == "UPDATE":
            op.execute(
                "CREATE POLICY workflow_documents_update_in_org "
                "ON workflow_documents "
                "FOR UPDATE USING (org_id = app.current_org_id()) "
                "WITH CHECK (org_id = app.current_org_id())"
            )
        else:
            op.execute(
                "CREATE POLICY workflow_documents_delete_in_org "
                "ON workflow_documents "
                "FOR DELETE USING (org_id = app.current_org_id())"
            )

    op.execute(
        "CREATE TRIGGER workflow_documents_updated_at "
        "BEFORE UPDATE ON workflow_documents "
        "FOR EACH ROW "
        "EXECUTE FUNCTION app.connector_installations_set_updated_at()"
    )

    # Add document_id + definition_snapshot to workflow_runs. Loosen the
    # existing template FK columns to nullable.
    op.add_column(
        "workflow_runs",
        sa.Column(
            "document_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "workflow_runs",
        sa.Column(
            "definition_snapshot",
            sa.dialects.postgresql.JSONB,
            nullable=True,
        ),
    )
    op.alter_column("workflow_runs", "template_id", nullable=True)
    op.alter_column("workflow_runs", "template_version_id", nullable=True)
    op.create_index("workflow_runs_document_idx", "workflow_runs", ["document_id"])

    # A run must be rooted in either a template (legacy / API direct)
    # or a document (new path). Exactly one must be set.
    op.execute(
        "ALTER TABLE workflow_runs ADD CONSTRAINT workflow_runs_root_check "
        "CHECK ("
        "(template_id IS NOT NULL AND document_id IS NULL) OR "
        "(template_id IS NULL AND document_id IS NOT NULL))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE workflow_runs DROP CONSTRAINT IF EXISTS workflow_runs_root_check")
    op.drop_index("workflow_runs_document_idx", table_name="workflow_runs")
    op.alter_column("workflow_runs", "template_version_id", nullable=False)
    op.alter_column("workflow_runs", "template_id", nullable=False)
    op.drop_column("workflow_runs", "definition_snapshot")
    op.drop_column("workflow_runs", "document_id")

    op.execute("DROP TRIGGER IF EXISTS workflow_documents_updated_at ON workflow_documents")
    for policy in (
        "workflow_documents_visible_to_org",
        "workflow_documents_insert_in_org",
        "workflow_documents_update_in_org",
        "workflow_documents_delete_in_org",
    ):
        op.execute(f"DROP POLICY IF EXISTS {policy} ON workflow_documents")
    op.execute("ALTER TABLE workflow_documents DISABLE ROW LEVEL SECURITY")
    op.drop_index("workflow_documents_folder_idx", table_name="workflow_documents")
    op.drop_index("workflow_documents_project_idx", table_name="workflow_documents")
    op.drop_table("workflow_documents")
