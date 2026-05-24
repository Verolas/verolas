"""OAuth state tokens for connector install flows.

A short-lived row per in-flight OAuth dance. The browser kicks off
`GET /v1/orgs/{slug}/connectors/oauth/start?class_id=X`, the API
mints a state token + PKCE verifier, stores them here keyed by the
state value, and redirects the browser to the vendor's authorize
URL. When the vendor calls back, the API looks up the state row,
exchanges code for tokens, and deletes the row.

Tokens older than 10 minutes are considered expired and rejected.
A periodic vacuum (or, in the interim, ON CONFLICT cleanup) keeps
the table tiny.

Revision ID: e2f4g6h8i9j1
Revises: d1f3g5h7i9j1
Create Date: 2026-05-24 13:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2f4g6h8i9j1"
down_revision: str | None = "d1f3g5h7i9j1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_oauth_state",
        sa.Column("state", sa.Text, primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("class_id", sa.Text, nullable=False),
        sa.Column("pkce_verifier", sa.Text, nullable=False),
        sa.Column("redirect_after", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
    )
    op.create_index("connector_oauth_state_org_idx", "connector_oauth_state", ["org_id"])
    op.create_index("connector_oauth_state_expires_idx", "connector_oauth_state", ["expires_at"])

    # OAuth callbacks have no session yet (the browser is mid-redirect)
    # so the state row is looked up without the app.current_org_id() guard.
    # The row's `state` value is unguessable and one-shot; that is the
    # security boundary. We do not enable RLS on this table.

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON connector_oauth_state TO verolas_app")


def downgrade() -> None:
    op.drop_index("connector_oauth_state_expires_idx", table_name="connector_oauth_state")
    op.drop_index("connector_oauth_state_org_idx", table_name="connector_oauth_state")
    op.drop_table("connector_oauth_state")
