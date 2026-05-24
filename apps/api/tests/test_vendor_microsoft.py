"""Unit tests for the Microsoft Graph fetchers.

We stub out httpx so the tests run with no network. The only real
assertion is that the fetchers walk the Graph responses correctly and
turn them into `ConnectorInstanceOption` rows.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from verolas_api.connector_instances import fetcher_for
from verolas_api.vendors.microsoft import (
    list_onedrive_drives,
    list_sharepoint_libraries,
    list_teams_channels,
)


@pytest.fixture
def credentials() -> dict[str, Any]:
    return {"access_token": "tok-abc", "refresh_token": "r-xyz"}


@pytest.mark.asyncio
async def test_registry_picks_up_microsoft_fetchers() -> None:
    assert fetcher_for("ms-sharepoint") is list_sharepoint_libraries
    assert fetcher_for("ms-onedrive") is list_onedrive_drives
    assert fetcher_for("ms-teams") is list_teams_channels


@pytest.mark.asyncio
async def test_sharepoint_returns_site_drive_options(
    credentials: dict[str, Any],
) -> None:
    sites_page = {
        "value": [
            {"id": "site-1", "displayName": "Berlin Studio"},
            {"id": "site-2", "displayName": "Hamburg Studio"},
        ]
    }
    drives_for_site_1 = {"value": [{"id": "drive-A", "name": "Designs", "webUrl": "https://x/a"}]}
    drives_for_site_2 = {"value": [{"id": "drive-B", "name": "Reports", "webUrl": "https://x/b"}]}

    pages = [sites_page, drives_for_site_1, drives_for_site_2]
    call_count = 0

    async def fake_get(path: str, token: str) -> dict[str, Any]:
        nonlocal call_count
        page = pages[call_count]
        call_count += 1
        return page

    with patch(
        "verolas_api.vendors.microsoft._graph_get",
        new=AsyncMock(side_effect=fake_get),
    ):
        options = await list_sharepoint_libraries(credentials)

    assert len(options) == 2
    assert options[0].ref == "site:site-1/drive:drive-A"
    assert options[0].label == "Berlin Studio / Designs"
    assert options[0].hint == "https://x/a"


@pytest.mark.asyncio
async def test_onedrive_includes_personal_and_shared(
    credentials: dict[str, Any],
) -> None:
    me_drive = {"id": "drv-me", "name": "My OneDrive", "webUrl": "https://x/me"}
    shared_page = {
        "value": [
            {"id": "drv-shared", "name": "Team Drive", "webUrl": "https://x/team"},
        ]
    }

    async def fake_get(path: str, token: str) -> dict[str, Any]:
        if path == "/me/drive":
            return me_drive
        return shared_page

    with patch(
        "verolas_api.vendors.microsoft._graph_get",
        new=AsyncMock(side_effect=fake_get),
    ):
        options = await list_onedrive_drives(credentials)

    refs = {o.ref for o in options}
    assert "drive:drv-me" in refs
    assert "drive:drv-shared" in refs


@pytest.mark.asyncio
async def test_teams_walks_channels(credentials: dict[str, Any]) -> None:
    teams_page = {"value": [{"id": "team-1", "displayName": "Studio"}]}
    channels_page = {
        "value": [
            {"id": "ch-general", "displayName": "General", "webUrl": "https://x/g"},
            {"id": "ch-permits", "displayName": "Permits", "webUrl": "https://x/p"},
        ]
    }

    async def fake_get(path: str, token: str) -> dict[str, Any]:
        if path == "/me/joinedTeams":
            return teams_page
        return channels_page

    with patch(
        "verolas_api.vendors.microsoft._graph_get",
        new=AsyncMock(side_effect=fake_get),
    ):
        options = await list_teams_channels(credentials)

    assert {o.ref for o in options} == {
        "team:team-1/channel:ch-general",
        "team:team-1/channel:ch-permits",
    }
