"""Unit tests for the Slack + Box + Dropbox fetchers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from verolas_api.connector_instances import fetcher_for
from verolas_api.vendors.box import list_box_folders
from verolas_api.vendors.dropbox import list_dropbox_folders
from verolas_api.vendors.slack import list_slack_channels


@pytest.fixture
def credentials() -> dict[str, Any]:
    return {"access_token": "tok-abc", "refresh_token": "r-xyz"}


def test_registry_picks_up_new_fetchers() -> None:
    assert fetcher_for("slack") is list_slack_channels
    assert fetcher_for("box") is list_box_folders
    assert fetcher_for("dropbox") is list_dropbox_folders


@pytest.mark.asyncio
async def test_slack_lists_channels(credentials: dict[str, Any]) -> None:
    page = {
        "ok": True,
        "channels": [
            {"id": "C111", "name": "general", "is_private": False},
            {"id": "C222", "name": "permits", "is_private": True},
        ],
    }

    async def fake(client: Any, path: str, token: str, params: Any = None) -> dict[str, Any]:
        return page

    with patch("verolas_api.vendors.slack._slack_get", new=AsyncMock(side_effect=fake)):
        options = await list_slack_channels(credentials)

    refs = [o.ref for o in options]
    assert refs == ["channel:C111", "channel:C222"]
    assert options[0].label == "#general"
    assert options[1].hint == "private"


@pytest.mark.asyncio
async def test_box_lists_root_plus_top_level_folders(credentials: dict[str, Any]) -> None:
    page = {
        "total_count": 2,
        "entries": [
            {"id": "100", "type": "folder", "name": "Designs"},
            {"id": "200", "type": "file", "name": "readme.txt"},
            {"id": "300", "type": "folder", "name": "Permits"},
        ],
    }

    async def fake(client: Any, path: str, token: str, params: Any = None) -> dict[str, Any]:
        return page

    with patch("verolas_api.vendors.box._box_get", new=AsyncMock(side_effect=fake)):
        options = await list_box_folders(credentials)

    refs = [o.ref for o in options]
    assert "folder:0" in refs
    assert "folder:100" in refs
    assert "folder:300" in refs
    assert "folder:200" not in refs


@pytest.mark.asyncio
async def test_dropbox_lists_root_plus_folders(credentials: dict[str, Any]) -> None:
    page = {
        "entries": [
            {".tag": "folder", "name": "Projects", "path_lower": "/projects"},
            {".tag": "file", "name": "notes.txt", "path_lower": "/notes.txt"},
        ],
        "has_more": False,
    }

    async def fake(client: Any, path: str, token: str, body: Any) -> dict[str, Any]:
        return page

    with patch(
        "verolas_api.vendors.dropbox._dropbox_post",
        new=AsyncMock(side_effect=fake),
    ):
        options = await list_dropbox_folders(credentials)

    refs = [o.ref for o in options]
    assert "folder:/" in refs
    assert "folder:/projects" in refs
    assert "folder:/notes.txt" not in refs
