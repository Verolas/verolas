"""Unit tests for the Autodesk APS fetcher."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from verolas_api.connector_instances import fetcher_for
from verolas_api.vendors.autodesk import list_aps_projects


@pytest.fixture
def credentials() -> dict[str, Any]:
    return {"access_token": "tok-abc", "refresh_token": "r-xyz"}


def test_registry_picks_up_autodesk_fetcher() -> None:
    assert fetcher_for("autodesk-aps") is list_aps_projects


@pytest.mark.asyncio
async def test_lists_projects_under_each_hub(credentials: dict[str, Any]) -> None:
    hubs_page = {
        "data": [
            {
                "id": "b.hub-1",
                "attributes": {
                    "name": "Verolas ACC",
                    "extension": {"type": "hubs:autodesk.bim360:Account"},
                },
            }
        ]
    }
    projects_page = {
        "data": [
            {"id": "b.proj-A", "attributes": {"name": "HQ Tower"}},
            {"id": "b.proj-B", "attributes": {"name": "Bridge North"}},
        ]
    }

    async def fake_get(client: object, path: str, token: str) -> dict[str, Any]:
        if path == "/project/v1/hubs":
            return hubs_page
        return projects_page

    with patch(
        "verolas_api.vendors.autodesk._aps_get",
        new=AsyncMock(side_effect=fake_get),
    ):
        options = await list_aps_projects(credentials)

    assert len(options) == 2
    assert options[0].ref == "hub:b.hub-1/project:b.proj-A"
    assert options[0].label == "Verolas ACC / HQ Tower"
    assert options[0].hint == "hubs:autodesk.bim360:Account"
