"""RBAC roles. One source of truth, used everywhere.

The Postgres enum `membership_role` in the tenancy migration and the Keycloak
realm roles in `infra/helm/keycloak/realm-template.json` mirror this enum
name for name. Any change here lands in lockstep with both.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """The six Verolas org roles, ordered low to high privilege."""

    VIEWER = "viewer"
    AUDITOR = "auditor"
    ENGINEER = "engineer"
    REVIEWER = "reviewer"
    ADMIN = "admin"
    OWNER = "owner"


_PRIVILEGE_ORDER: dict[Role, int] = {
    Role.VIEWER: 10,
    Role.AUDITOR: 15,
    Role.ENGINEER: 20,
    Role.REVIEWER: 30,
    Role.ADMIN: 40,
    Role.OWNER: 50,
}


def role_at_least(actual: Role, required: Role) -> bool:
    """Return True if `actual` is at least as privileged as `required`.

    Auditor and viewer are intentionally not comparable to engineer or above
    on privilege: auditor reads audit logs that engineers cannot see, viewer
    reads project data that auditors cannot see. The ordering above is for
    role escalation checks (e.g., "does this user have admin or better").
    Use explicit role membership checks for the audit and viewer split.
    """
    return _PRIVILEGE_ORDER[actual] >= _PRIVILEGE_ORDER[required]
