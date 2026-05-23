"""Pydantic schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from verolas_api.schemas import (
    Discipline,
    MembershipRole,
    OrganizationCreate,
    OrganizationStatus,
    ProjectCreate,
    UserCreate,
    UserStatus,
)


def test_user_create_accepts_email() -> None:
    u = UserCreate(email="user@example.com", name="Test User")
    assert u.email == "user@example.com"


def test_user_create_rejects_bad_email() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email")


def test_organization_create_accepts_valid_slug() -> None:
    o = OrganizationCreate(name="Verolas GmbH", slug="verolas-gmbh")
    assert o.slug == "verolas-gmbh"


@pytest.mark.parametrize(
    "bad_slug",
    [
        "with space",
        "-leading-hyphen",
        "trailing-hyphen-",
        "UpperCase",
        "with.period",
        "",
        "x" * 41,
    ],
)
def test_organization_create_rejects_bad_slug(bad_slug: str) -> None:
    with pytest.raises(ValidationError):
        OrganizationCreate(name="Verolas", slug=bad_slug)


def test_project_create_accepts_known_discipline() -> None:
    p = ProjectCreate(name="HQ Bauleitung", discipline=Discipline.STRUCTURAL)
    assert p.discipline is Discipline.STRUCTURAL


def test_role_enum_matches_keycloak_realm_values() -> None:
    expected = {"owner", "admin", "reviewer", "engineer", "viewer", "auditor"}
    assert {r.value for r in MembershipRole} == expected


def test_status_enums_match_postgres_values() -> None:
    assert {s.value for s in UserStatus} == {"active", "invited", "suspended", "deleted"}
    assert {s.value for s in OrganizationStatus} == {"active", "suspended", "deleted"}
