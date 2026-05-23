"""Tests for the role enum and privilege comparison."""

from __future__ import annotations

from verolas_auth.roles import Role, role_at_least


def test_role_values_match_keycloak_realm() -> None:
    expected = {"owner", "admin", "reviewer", "engineer", "viewer", "auditor"}
    assert {r.value for r in Role} == expected


def test_role_at_least_strict_ordering_holds() -> None:
    assert role_at_least(Role.OWNER, Role.ADMIN)
    assert role_at_least(Role.ADMIN, Role.REVIEWER)
    assert role_at_least(Role.REVIEWER, Role.ENGINEER)
    assert not role_at_least(Role.ENGINEER, Role.REVIEWER)
    assert role_at_least(Role.OWNER, Role.OWNER)


def test_role_str_roundtrip() -> None:
    assert Role("owner") is Role.OWNER
    assert Role("auditor") is Role.AUDITOR
