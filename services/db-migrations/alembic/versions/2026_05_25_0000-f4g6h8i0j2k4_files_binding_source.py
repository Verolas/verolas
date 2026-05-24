"""Tag `files` rows with the connector binding they came from.

A file that lands in the Vault via a connector sync (SharePoint,
OneDrive, Box, ...) needs three things on top of the existing
`files` schema:

- `binding_id`: which project binding spawned the sync that ingested
  it. Lets us re-sync without duplicating rows and lets the UI
  surface where a file came from.
- `external_ref`: the vendor's stable id for the source object
  (SharePoint drive item id, Box file id, Google Drive file id, ...).
- A partial unique index on (binding_id, external_ref) for
  binding-scoped upserts.

Files uploaded directly by users keep both columns NULL; the
existing project_id / library_folder_id paths are untouched.

Revision ID: f4g6h8i0j2k4
Revises: e2f4g6h8i9j1
Create Date: 2026-05-25 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f4g6h8i0j2k4"
down_revision: str | None = "e2f4g6h8i9j1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column(
            "binding_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connector_bindings.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("files", sa.Column("external_ref", sa.Text, nullable=True))
    op.create_index("files_binding_idx", "files", ["binding_id"])
    op.execute(
        """
        CREATE UNIQUE INDEX files_binding_external_ref_unique
        ON files (binding_id, external_ref)
        WHERE binding_id IS NOT NULL AND external_ref IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS files_binding_external_ref_unique")
    op.drop_index("files_binding_idx", table_name="files")
    op.drop_column("files", "external_ref")
    op.drop_column("files", "binding_id")
