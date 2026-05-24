"""Locale on organizations and per-user locale override.

The region picked during onboarding sets the org's default locale,
which drives the UI language, number / date format, units, code set,
fee schedule, drawing templates, and permit pack format. A user can
override their personal UI language in settings without changing the
firm's code set.

Revision ID: b8c0d2e4f6g8
Revises: a7b9c1d3e5f7
Create Date: 2026-05-24 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c0d2e4f6g8"
down_revision: str | None = "a7b9c1d3e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "locale",
            sa.Text,
            nullable=False,
            server_default="en-US",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "region",
            sa.Text,
            nullable=False,
            server_default="us",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "locale_override",
            sa.Text,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "locale_override")
    op.drop_column("organizations", "region")
    op.drop_column("organizations", "locale")
