"""Unit tests for the connector catalog and schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from verolas_api.connectors import CONNECTORS, by_category, lookup
from verolas_api.schemas.connector import (
    ConnectorBindingCreate,
    ConnectorInstallationCreate,
    ConnectorWaitlistCreate,
)


def test_catalog_is_nonempty() -> None:
    assert len(CONNECTORS) >= 25, "catalog should ship the launch connectors"


def test_every_connector_has_required_fields() -> None:
    for cid, spec in CONNECTORS.items():
        assert spec.id == cid
        assert spec.name
        assert spec.vendor
        assert spec.blurb
        assert spec.instance_label
        assert spec.tier in {"A", "B", "C", "internal"}
        assert spec.region_tags, f"{cid} must be tagged for at least one region"


def test_lookup_returns_none_for_unknown() -> None:
    assert lookup("does-not-exist") is None
    assert lookup("ms-sharepoint") is not None


def test_by_category_covers_all_entries() -> None:
    grouped = by_category()
    flat = [spec for entries in grouped.values() for spec in entries]
    assert len(flat) == len(CONNECTORS)


def test_verolas_library_is_internal() -> None:
    spec = lookup("verolas-library")
    assert spec is not None
    assert spec.tier == "internal"
    assert spec.auth_method == "internal"


def test_installation_create_validates_class_id() -> None:
    body = ConnectorInstallationCreate(class_id="ms-sharepoint")
    assert body.class_id == "ms-sharepoint"
    with pytest.raises(ValidationError):
        ConnectorInstallationCreate(class_id="")


def test_binding_create_requires_label() -> None:
    with pytest.raises(ValidationError):
        ConnectorBindingCreate(
            installation_id="00000000-0000-0000-0000-000000000001",  # type: ignore[arg-type]
            instance_ref="lib-1",
            instance_label="",
        )


def test_waitlist_create_truncates_note() -> None:
    body = ConnectorWaitlistCreate(class_id="sofistik", note="need by Q3")
    assert body.note == "need by Q3"
