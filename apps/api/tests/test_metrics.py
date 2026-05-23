"""Prometheus exposition and request metrics tests."""

from __future__ import annotations

import httpx


async def test_metrics_endpoint_returns_prometheus_exposition(client: httpx.AsyncClient) -> None:
    await client.get("/healthz")
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "verolas_requests_total" in body
    assert "verolas_request_duration_seconds" in body


async def test_request_counter_records_route_and_tier(client: httpx.AsyncClient) -> None:
    for _ in range(3):
        await client.get("/healthz")
    response = await client.get("/metrics")
    body = response.text
    assert 'route="/healthz"' in body
    assert 'tier="1"' in body
    assert 'method="GET"' in body
