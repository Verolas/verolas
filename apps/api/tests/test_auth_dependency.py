"""Auth dependency tests against the v1 routes."""

from __future__ import annotations

import httpx


async def test_v1_users_me_requires_bearer(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer token required."


async def test_v1_users_me_rejects_invalid_token(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/v1/users/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


async def test_v1_users_me_with_valid_token_reaches_501(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/v1/users/me",
        headers={"Authorization": "Bearer owner-token"},
    )
    # Auth passes; the route returns 501 because the database wiring is
    # deferred to the next workstream.
    assert response.status_code == 501


async def test_v1_organizations_list_with_viewer_reaches_501(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/v1/organizations/",
        headers={"Authorization": "Bearer viewer-token"},
    )
    assert response.status_code == 501
