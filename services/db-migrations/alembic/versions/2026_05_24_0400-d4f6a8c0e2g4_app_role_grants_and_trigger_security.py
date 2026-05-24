"""App role grants and audit trigger SECURITY DEFINER.

The application connects as `verolas_app`, a non-superuser role that
RLS treats as the request actor. For RLS to compose correctly the role
needs three things that earlier migrations forgot to grant:

1. `USAGE` on the `app` schema and `EXECUTE` on its tenancy functions
   (`app.current_org_id()` etc.), otherwise every policy that calls
   `app.current_org_id()` blows up with "permission denied for schema
   app" and silently returns false, so all rows look invisible.
2. CRUD privileges on the user-facing tables in `public`. Schema-level
   `GRANT ... ON ALL TABLES` plus default-privilege grants so future
   tables added by Alembic inherit the same access.
3. `app.activity_log_chain()` runs `SELECT ... FOR UPDATE` against
   `activity_log` to compute the next chain seq. Postgres treats the
   `FOR UPDATE` part as an UPDATE for RLS evaluation, and the existing
   `activity_log_no_update` policy (USING false) makes the lookup
   return zero rows. The fix is to make the trigger SECURITY DEFINER
   so it runs as the function owner (postgres) and skips RLS for the
   lookup, while still respecting the application-supplied org_id on
   the actual INSERT.

Both pieces are required for `/v1/projects` create-with-audit to work
end to end.

Revision ID: d4f6a8c0e2g4
Revises: c3e5f7b9d1f3
Create Date: 2026-05-24 04:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d4f6a8c0e2g4"
down_revision: str | None = "c3e5f7b9d1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "verolas_app"


def upgrade() -> None:
    op.execute(f"GRANT USAGE ON SCHEMA app TO {APP_ROLE}")
    op.execute(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO {APP_ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT EXECUTE ON FUNCTIONS TO {APP_ROLE}")

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
    )

    op.execute(f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {APP_ROLE}"
    )

    op.execute("ALTER FUNCTION app.activity_log_chain() SECURITY DEFINER")
    op.execute("REVOKE EXECUTE ON FUNCTION app.activity_log_chain() FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app.activity_log_chain() TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("ALTER FUNCTION app.activity_log_chain() SECURITY INVOKER")
    op.execute(
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE}"
    )
    op.execute(f"REVOKE USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE USAGE, SELECT, UPDATE ON SEQUENCES FROM {APP_ROLE}"
    )
    op.execute(f"REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA app FROM {APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA app REVOKE EXECUTE ON FUNCTIONS FROM {APP_ROLE}"
    )
    op.execute(f"REVOKE USAGE ON SCHEMA app FROM {APP_ROLE}")
