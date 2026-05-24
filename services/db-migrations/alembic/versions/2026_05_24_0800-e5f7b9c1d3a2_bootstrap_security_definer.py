"""SECURITY DEFINER functions for /v1/me and /v1/onboarding.

The application role (verolas_app) does not have BYPASSRLS, and
`SET LOCAL row_security = off` would only cause RLS-touching queries
to throw instead of bypassing the policy. Two helper functions, owned
by postgres and marked SECURITY DEFINER, do the chicken-and-egg work
that the app does before any tenancy context exists:

- `app.account_view(p_subject)` returns the user row + memberships as
  jsonb so /v1/me can decide whether to send the caller to onboarding.
- `app.onboard_account(...)` atomically inserts the user, the first
  org, the owner membership, the first project, and two audit chain
  entries.

These are the only writes that need to bypass RLS; every other path
keeps running under tenancy. Execute permission is granted to
verolas_app and revoked from PUBLIC.

Revision ID: e5f7b9c1d3a2
Revises: d4f6a8c0e2g4
Create Date: 2026-05-24 08:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e5f7b9c1d3a2"
down_revision: str | None = "d4f6a8c0e2g4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.account_view(p_subject text)
        RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, app
        AS $$
        DECLARE
            user_row users%ROWTYPE;
            memberships_json jsonb;
        BEGIN
            SELECT * INTO user_row FROM users WHERE keycloak_subject = p_subject;
            IF NOT FOUND THEN
                RETURN jsonb_build_object('user', NULL, 'memberships', '[]'::jsonb);
            END IF;
            SELECT COALESCE(jsonb_agg(jsonb_build_object(
                'organization_id', o.id,
                'organization_slug', o.slug,
                'organization_name', o.name,
                'organization_status', o.status,
                'role', m.role
            ) ORDER BY o.created_at), '[]'::jsonb)
            INTO memberships_json
            FROM memberships m
            JOIN organizations o ON o.id = m.org_id
            WHERE m.user_id = user_row.id;
            RETURN jsonb_build_object(
                'user', jsonb_build_object(
                    'id', user_row.id,
                    'email', user_row.email,
                    'name', user_row.name,
                    'created_at', user_row.created_at
                ),
                'memberships', memberships_json
            );
        END;
        $$;
        """
    )
    op.execute("REVOKE EXECUTE ON FUNCTION app.account_view(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.account_view(text) TO verolas_app")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.onboard_account(
            p_subject text,
            p_email text,
            p_name text,
            p_org_name text,
            p_slug text,
            p_discipline text,
            p_project_name text
        )
        RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, app
        AS $$
        DECLARE
            user_uuid uuid := p_subject::uuid;
            org_uuid uuid := gen_random_uuid();
            project_uuid uuid := gen_random_uuid();
            membership_uuid uuid := gen_random_uuid();
        BEGIN
            INSERT INTO users (id, keycloak_subject, email, name, status)
            VALUES (user_uuid, p_subject, p_email, p_name, 'active')
            ON CONFLICT (id) DO UPDATE
                SET keycloak_subject = EXCLUDED.keycloak_subject,
                    email            = EXCLUDED.email,
                    name             = COALESCE(users.name, EXCLUDED.name),
                    status           = 'active';

            IF EXISTS (SELECT 1 FROM organizations WHERE slug = p_slug) THEN
                RAISE EXCEPTION 'slug_taken' USING ERRCODE = 'unique_violation';
            END IF;

            INSERT INTO organizations (id, name, slug, plan, status)
            VALUES (org_uuid, p_org_name, p_slug, 'free', 'active');

            INSERT INTO memberships (id, user_id, org_id, role)
            VALUES (membership_uuid, user_uuid, org_uuid, 'owner');

            INSERT INTO projects (id, org_id, name, discipline)
            VALUES (project_uuid, org_uuid, p_project_name, p_discipline::discipline);

            INSERT INTO activity_log
                (id, org_id, actor_user_id, action, resource_type, resource_id, payload)
            VALUES (
                gen_random_uuid(), org_uuid, user_uuid,
                'account.onboarded', 'organization', org_uuid,
                jsonb_build_object(
                    'organization_name', p_org_name,
                    'slug', p_slug,
                    'primary_discipline', p_discipline
                )
            );
            INSERT INTO activity_log
                (id, org_id, actor_user_id, action, resource_type, resource_id, payload)
            VALUES (
                gen_random_uuid(), org_uuid, user_uuid,
                'project.create', 'project', project_uuid,
                jsonb_build_object('name', p_project_name, 'discipline', p_discipline)
            );

            RETURN jsonb_build_object(
                'user_id', user_uuid,
                'organization_id', org_uuid,
                'organization_slug', p_slug,
                'organization_name', p_org_name,
                'project_id', project_uuid,
                'project_name', p_project_name,
                'discipline', p_discipline
            );
        END;
        $$;
        """
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION "
        "app.onboard_account(text, text, text, text, text, text, text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION "
        "app.onboard_account(text, text, text, text, text, text, text) TO verolas_app"
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS app.onboard_account(text, text, text, text, text, text, text)"
    )
    op.execute("DROP FUNCTION IF EXISTS app.account_view(text)")
