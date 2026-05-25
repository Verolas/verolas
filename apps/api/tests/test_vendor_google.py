"""Unit tests for the Google Workspace fetchers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from verolas_api.connector_instances import fetcher_for
from verolas_api.vendors.google import (
    list_gmail_mailbox,
    list_google_drives,
    list_google_spreadsheets,
)


@pytest.fixture
def credentials() -> dict[str, Any]:
    return {"access_token": "tok-abc", "refresh_token": "r-xyz"}


def test_registry_picks_up_google_fetchers() -> None:
    assert fetcher_for("google-drive") is list_google_drives
    assert fetcher_for("google-sheets") is list_google_spreadsheets
    assert fetcher_for("gmail") is list_gmail_mailbox


@pytest.mark.asyncio
async def test_google_drives_includes_my_drive_and_shared(
    credentials: dict[str, Any],
) -> None:
    shared = {
        "drives": [
            {"id": "0AABC", "name": "Engineering"},
            {"id": "0AXYZ", "name": "Permits"},
        ]
    }

    async def fake_get(client: Any, url: str, token: str, params: Any = None) -> dict[str, Any]:
        return shared

    with patch("verolas_api.vendors.google._api_get", new=AsyncMock(side_effect=fake_get)):
        options = await list_google_drives(credentials)

    refs = [o.ref for o in options]
    assert "drive:my" in refs
    assert "drive:0AABC" in refs
    assert "drive:0AXYZ" in refs
    assert options[0].label == "My Drive"


@pytest.mark.asyncio
async def test_google_sheets_lists_spreadsheets(credentials: dict[str, Any]) -> None:
    files_page = {
        "files": [
            {
                "id": "sheet-1",
                "name": "Load takedowns Q3",
                "webViewLink": "https://docs.google.com/spreadsheets/d/sheet-1",
            },
            {
                "id": "sheet-2",
                "name": "Punching shear matrix",
                "webViewLink": "https://docs.google.com/spreadsheets/d/sheet-2",
            },
        ]
    }

    async def fake_get(client: Any, url: str, token: str, params: Any = None) -> dict[str, Any]:
        return files_page

    with patch("verolas_api.vendors.google._api_get", new=AsyncMock(side_effect=fake_get)):
        options = await list_google_spreadsheets(credentials)

    assert {o.ref for o in options} == {"spreadsheet:sheet-1", "spreadsheet:sheet-2"}
    assert options[0].label == "Load takedowns Q3"


@pytest.mark.asyncio
async def test_gmail_returns_single_mailbox(credentials: dict[str, Any]) -> None:
    profile = {"emailAddress": "shramish@verolas.com"}

    async def fake_get(client: Any, url: str, token: str, params: Any = None) -> dict[str, Any]:
        return profile

    with patch("verolas_api.vendors.google._api_get", new=AsyncMock(side_effect=fake_get)):
        options = await list_gmail_mailbox(credentials)

    assert len(options) == 1
    assert options[0].ref == "mailbox:shramish@verolas.com"
    assert options[0].label == "shramish@verolas.com"
