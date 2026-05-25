"""Thin httpx wrapper for talking to the Verolas cloud."""

from __future__ import annotations

from typing import Any

import httpx

from verolas_bridge import __version__


class BridgeClient:
    """Per-process httpx client carrying the bridge bearer token."""

    def __init__(self, *, api_base_url: str, token: str) -> None:
        self._base = api_base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": f"verolas-bridge/{__version__}",
                "Accept": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def poll(self) -> list[dict[str, Any]]:
        """Claim queued jobs. Empty list means nothing to do."""
        response = await self._client.get(f"{self._base}/v1/bridges/poll")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("poll endpoint returned non-list payload")
        return [row for row in payload if isinstance(row, dict)]

    async def submit_result(
        self,
        job_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        body: dict[str, Any] = {"status": status, "result": result or {}}
        if error is not None:
            body["error"] = error
        response = await self._client.post(
            f"{self._base}/v1/bridges/jobs/{job_id}/result",
            json=body,
        )
        response.raise_for_status()
