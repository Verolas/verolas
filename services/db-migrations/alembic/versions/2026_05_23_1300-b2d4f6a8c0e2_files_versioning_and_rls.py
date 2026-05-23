"""files versioning and rls

Revision ID: b2d4f6a8c0e2
Revises: a1c0d3e5f7b9
Create Date: 2026-05-23 13:00:00.000000+00:00

Adds the files table with versioning, scan tracking, and RLS scoped to
`app.current_org_id`. Each upload creates a new row. Subsequent uploads of
the same logical file link backward via parent_file_id; the most recent
row in a version chain is the head and the older rows are retained for
audit and rollback.

Columns of interest:
- bucket / object_key: where the data lives in Hetzner Object Storage.
- size_bytes: actual stored size, populated after the multipart complete.
- sha256: client supplied at upload completion, verified server side once
  the object scan landed.
- kind: classification from verolas_storage.file_kinds (cad_drawing,
  office_macro, etc.). The macro path keys off this.
- status: lifecycle state for the upload, scan, and review.
- scan_result and scan_signature: clamd verdict, null until scanned.
- macro_sandbox_required: true for XLSM, DOCM, PPTM, and similar so the
  ingest pipeline knows to route through the sandbox path.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2d4f6a8c0e2"
down_revision: str | None = "a1c0d3e5f7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    file_status = sa.Enum(
        "uploading",
        "scanning",
        "ready",
        "quarantined",
        "deleted",
        name="file_status",
    )
    file_status.create(op.get_bind(), checkfirst=True)

    file_kind = sa.Enum(
        "office_macro",
        "office_plain",
        "cad_drawing",
        "cad_bim",
        "pdf",
        "image",
        "archive",
        "spreadsheet_plain",
        "generic",
        name="file_kind",
    )
    file_kind.create(op.get_bind(), checkfirst=True)

    scan_verdict = sa.Enum(
        "clean",
        "infected",
        "error",
        name="scan_verdict",
    )
    scan_verdict.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "files",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "parent_file_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("content_type", sa.Text, nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "office_macro",
                "office_plain",
                "cad_drawing",
                "cad_bim",
                "pdf",
                "image",
                "archive",
                "spreadsheet_plain",
                "generic",
                name="file_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "macro_sandbox_required", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("bucket", sa.Text, nullable=False),
        sa.Column("object_key", sa.Text, nullable=False),
        sa.Column("multipart_upload_id", sa.Text, nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("sha256", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "uploading",
                "scanning",
                "ready",
                "quarantined",
                "deleted",
                name="file_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'uploading'"),
        ),
        sa.Column(
            "scan_verdict",
            sa.Enum(
                "clean",
                "infected",
                "error",
                name="scan_verdict",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("scan_signature", sa.Text, nullable=True),
        sa.Column("scanned_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.UniqueConstraint("bucket", "object_key", name="files_bucket_key_unique"),
        sa.CheckConstraint("version >= 1", name="files_version_positive"),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="files_size_nonneg"),
    )

    op.create_index("files_org_idx", "files", ["org_id"])
    op.create_index("files_parent_idx", "files", ["parent_file_id"])
    op.create_index("files_kind_idx", "files", ["kind"])
    op.create_index("files_status_idx", "files", ["status"])

    op.execute("ALTER TABLE files ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE files FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY files_visible_in_org ON files
        FOR ALL
        USING (org_id = app.current_org_id())
        WITH CHECK (org_id = app.current_org_id());
        """
    )

    # View that returns the head of every version chain per file. Useful for
    # listings that should show only the latest version while keeping the
    # full history available via a join on parent_file_id.
    op.execute(
        """
        CREATE OR REPLACE VIEW files_latest AS
        SELECT f.*
        FROM files f
        WHERE NOT EXISTS (
            SELECT 1 FROM files c
            WHERE c.parent_file_id = f.id
              AND c.org_id = f.org_id
              AND c.status <> 'deleted'
        )
        AND f.status <> 'deleted';
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS files_latest")
    op.execute("DROP POLICY IF EXISTS files_visible_in_org ON files")
    op.execute("ALTER TABLE files DISABLE ROW LEVEL SECURITY")

    op.drop_index("files_status_idx", table_name="files")
    op.drop_index("files_kind_idx", table_name="files")
    op.drop_index("files_parent_idx", table_name="files")
    op.drop_index("files_org_idx", table_name="files")
    op.drop_table("files")

    sa.Enum(name="scan_verdict").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="file_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="file_status").drop(op.get_bind(), checkfirst=True)
