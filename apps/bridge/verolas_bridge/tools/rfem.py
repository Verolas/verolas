"""Dlubal RFEM / RSTAB adapter.

Talks to Dlubal's Web Service (RWS) API. RWS is a REST/JSON server
that runs alongside a licensed RFEM 6 (or RSTAB 9) install on the
operator's workstation; the bridge agent sends model commands and
reads results over HTTP without needing the COM/.NET binding.

For our dev environment we cannot run RFEM (Windows + paid license
required), so this adapter falls back gracefully when the local RWS
endpoint is unreachable: the bridge surfaces a clear error message
to the cloud so the operator knows what is missing.

Job payload (the verolas-api worker posts this into bridge_jobs):

    {
        "action": "static_analysis",
        "model_url": "https://...presigned download for the .rfx file",
        "result_keys": ["combinations", "reactions", "deflections"],
        "rws_url": "http://localhost:8081"   # optional override
    }

The adapter currently supports two actions: `ping` (smoke test) and
`static_analysis` (download model, submit, read summary back).
Additional actions land as the calc product matures.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from verolas_bridge.tools import register

DEFAULT_RWS_URL = "http://localhost:8081"


@register("dlubal-rfem")
async def run_rfem_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a Dlubal RFEM job by action."""
    action = payload.get("action") or "ping"
    rws_url = payload.get("rws_url") or os.environ.get("VEROLAS_BRIDGE_RFEM_URL", DEFAULT_RWS_URL)

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        if action == "ping":
            return await _ping(client, rws_url)
        if action == "static_analysis":
            return await _static_analysis(client, rws_url, payload)
        raise RuntimeError(f"RFEM action '{action}' not implemented in this bridge build")


async def _ping(client: httpx.AsyncClient, rws_url: str) -> dict[str, Any]:
    """Confirm RWS is reachable. Used to verify the bridge can see RFEM."""
    try:
        response = await client.get(f"{rws_url}/api/v1/info", timeout=5.0)
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Could not reach Dlubal RWS at {rws_url} ({type(exc).__name__}). "
            "Make sure RFEM 6 is running on this host with the Web Service enabled."
        ) from exc
    if response.status_code >= 400:
        raise RuntimeError(f"RWS replied {response.status_code}: {response.text[:200]}")
    payload: Any = response.json()
    return {
        "action": "ping",
        "rws_url": rws_url,
        "rfem_info": payload if isinstance(payload, dict) else {"raw": str(payload)[:200]},
    }


async def _static_analysis(
    client: httpx.AsyncClient, rws_url: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Walk the standard RWS sequence: open model, calculate, read summary."""
    model_url = payload.get("model_url")
    if not isinstance(model_url, str):
        raise RuntimeError("static_analysis requires a 'model_url' field")
    result_keys = payload.get("result_keys") or ["combinations"]
    if not isinstance(result_keys, list):
        raise RuntimeError("'result_keys' must be a list of strings")

    # 1. Download the .rfx model bundle from object storage.
    download = await client.get(model_url, timeout=120.0)
    download.raise_for_status()

    # 2. Hand the model bytes to RWS. Real Dlubal RWS expects a multipart
    #    upload to /api/v1/model. We do not have a live licensed RFEM in
    #    the dev environment, so the bridge surfaces a clear error if RWS
    #    cannot be reached. Firms running this on a real workstation get
    #    the full path.
    try:
        open_response = await client.post(
            f"{rws_url}/api/v1/model",
            files={"file": ("model.rfx", download.content)},
            timeout=120.0,
        )
        open_response.raise_for_status()
        model_id = (open_response.json() or {}).get("id")
        if not isinstance(model_id, str):
            raise RuntimeError("RWS open-model response did not include an id")

        # 3. Run the calculation.
        calc = await client.post(
            f"{rws_url}/api/v1/model/{model_id}/calculate",
            timeout=600.0,
        )
        calc.raise_for_status()

        # 4. Read the requested result blocks.
        results: dict[str, Any] = {}
        for key in result_keys:
            r = await client.get(f"{rws_url}/api/v1/model/{model_id}/results/{key}")
            r.raise_for_status()
            results[key] = r.json()

        return {
            "action": "static_analysis",
            "model_id": model_id,
            "results": results,
        }
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Dlubal RWS call failed at {rws_url}: {type(exc).__name__}. "
            "Confirm RFEM 6 is running with Web Service enabled."
        ) from exc


__all__ = ["run_rfem_job"]
