"""Pydantic schemas for the connector endpoints.

Three shapes:

- `ConnectorClassOut` — a catalog entry sent to the UI.
- `ConnectorInstallationOut` / `ConnectorInstallationCreate` — one row per
  org per class, returned for the org Integrations page.
- `ConnectorBindingOut` / `ConnectorBindingCreate` — one row per project,
  picking a specific instance from the org installation.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConnectorInstallStatus(StrEnum):
    PENDING = "pending"
    INSTALLED = "installed"
    ERROR = "error"
    UNINSTALLED = "uninstalled"


class ConnectorBindingStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class ConnectorClassOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    vendor: str
    category: str
    tier: str
    auth_method: str
    blurb: str
    region_tags: list[str]
    scopes: list[str]
    docs_url: str | None = None
    instance_label: str


class ConnectorInstallationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_id: str = Field(min_length=1, max_length=80)
    oauth_account: dict[str, Any] = Field(default_factory=dict)
    scopes: list[str] = Field(default_factory=list)


class ConnectorInstallationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    org_id: UUID
    class_id: str
    status: ConnectorInstallStatus
    installed_by_user_id: UUID | None
    scopes: list[str]
    oauth_account: dict[str, Any]
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class ConnectorBindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installation_id: UUID
    instance_ref: str = Field(min_length=1, max_length=400)
    instance_label: str = Field(min_length=1, max_length=200)
    config: dict[str, Any] = Field(default_factory=dict)


class ConnectorBindingOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    org_id: UUID
    installation_id: UUID
    class_id: str
    instance_ref: str
    instance_label: str
    config: dict[str, Any]
    status: ConnectorBindingStatus
    last_sync_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ConnectorWaitlistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_id: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=2000)


class ConnectorWaitlistOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    org_id: UUID
    class_id: str
    requested_by_user_id: UUID | None
    note: str | None
    created_at: datetime


__all__ = [
    "ConnectorBindingCreate",
    "ConnectorBindingOut",
    "ConnectorBindingStatus",
    "ConnectorClassOut",
    "ConnectorInstallStatus",
    "ConnectorInstallationCreate",
    "ConnectorInstallationOut",
    "ConnectorWaitlistCreate",
    "ConnectorWaitlistOut",
]
