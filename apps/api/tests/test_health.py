"""Health and readiness probe tests."""

from __future__ import annotations

import httpx


async def test_healthz_returns_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_returns_ready(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_request_id_header_is_returned(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    request_id = response.headers.get("x-request-id")
    assert request_id is not None
    assert len(request_id) >= 8


async def test_request_id_header_is_echoed_when_provided(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/healthz",
        headers={"X-Request-ID": "test-correlation-123"},
    )
    assert response.headers["x-request-id"] == "test-correlation-123"
