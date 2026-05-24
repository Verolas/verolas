"""Verolas Library: org-level folders that any project can mount.

The Library is the firm's shared content store: standard details,
template calc sheets, reference clauses, master specs, vendor
catalogs. An org admin uploads content here once; project managers
mount any folder into a project via the existing connectors binding
mechanism (the `verolas-library` connector class).

- `library_folders` is one row per folder, org-scoped under RLS.
- `files.library_folder_id` joins the existing `files` table to a
  folder. A file row belongs either to a project (`project_id`)
  or to a library folder, not both.

Revision ID: d1f3g5h7i9j1
Revises: c0e2f4g6h8i0
Create Date: 2026-05-24 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1f3g5h7i9j1"
down_revision: str | None = "c0e2f4g6h8i0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_folders",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
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
        sa.UniqueConstraint("org_id", "name", name="library_folders_org_name_unique"),
    )
    op.create_index("library_folders_org_idx", "library_folders", ["org_id"])

    op.execute("ALTER TABLE library_folders ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE library_folders FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY library_folders_visible_to_org ON library_folders "
        "FOR SELECT USING (org_id = app.current_org_id())"
    )
    op.execute(
        "CREATE POLICY library_folders_insert_in_org ON library_folders "
        "FOR INSERT WITH CHECK (org_id = app.current_org_id())"
    )
    op.execute(
        "CREATE POLICY library_folders_update_in_org ON library_folders "
        "FOR UPDATE USING (org_id = app.current_org_id()) "
        "WITH CHECK (org_id = app.current_org_id())"
    )
    op.execute(
        "CREATE POLICY library_folders_delete_in_org ON library_folders "
        "FOR DELETE USING (org_id = app.current_org_id())"
    )

    op.execute(
        """
        CREATE TRIGGER library_folders_updated_at
        BEFORE UPDATE ON library_folders
        FOR EACH ROW
        EXECUTE FUNCTION app.connector_installations_set_updated_at()
        """
    )

    op.add_column(
        "files",
        sa.Column(
            "library_folder_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("library_folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("files_library_folder_idx", "files", ["library_folder_id"])


def downgrade() -> None:
    op.drop_index("files_library_folder_idx", table_name="files")
    op.drop_column("files", "library_folder_id")
    op.execute("DROP TRIGGER IF EXISTS library_folders_updated_at ON library_folders")
    for action in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        policy = (
            f"library_folders_{action.lower()}_in_org"
            if action != "SELECT"
            else "library_folders_visible_to_org"
        )
        op.execute(f"DROP POLICY IF EXISTS {policy} ON library_folders")
    op.execute("ALTER TABLE library_folders DISABLE ROW LEVEL SECURITY")
    op.drop_index("library_folders_org_idx", table_name="library_folders")
    op.drop_table("library_folders")
