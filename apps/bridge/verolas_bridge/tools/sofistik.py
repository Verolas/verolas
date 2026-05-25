"""SOFiSTiK adapter.

SOFiSTiK exposes its workflow via the Python Toolbox bundled with the
SSD installer. The bridge talks to it through the `sofistik_toolbox`
module which only ships with a licensed SOFiSTiK on Windows.

Supported actions:

- `ping`            confirm the toolbox imports
- `run_dat`         submit a .dat input file, wait for completion, return
                    SOFiSTiK's log + result database paths
"""

from __future__ import annotations

from typing import Any

from verolas_bridge.tools import register
from verolas_bridge.tools._sdk import import_sdk

INSTALL_HINT = (
    "Install SOFiSTiK SSD on the bridge host (Windows). "
    "The Python Toolbox ships with the SSD installer."
)


@register("sofistik")
async def run_sofistik_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a SOFiSTiK job by action."""
    action = payload.get("action") or "ping"
    sdk = import_sdk("sofistik_toolbox", INSTALL_HINT)

    if action == "ping":
        return {
            "action": "ping",
            "sofistik_toolbox_version": getattr(sdk, "__version__", "unknown"),
        }

    if action == "run_dat":
        dat_text = payload.get("dat")
        if not isinstance(dat_text, str):
            raise RuntimeError("run_dat requires a 'dat' field with the input deck")
        runner = getattr(sdk, "DatRunner", None)
        if runner is None:
            raise RuntimeError(
                "This sofistik_toolbox build does not expose DatRunner; "
                "upgrade SOFiSTiK SSD on the bridge host."
            )
        # The toolbox's DatRunner API is synchronous and Windows-bound.
        # We invoke it directly; the asyncio runner will block this
        # task while the calc runs, which is fine for one bridge per
        # workstation. Multi-job concurrency lands when the bridge
        # gains a worker pool.
        result = runner().run(dat_text)
        return {"action": "run_dat", "result": dict(result) if hasattr(result, "items") else {}}

    raise RuntimeError(f"SOFiSTiK action '{action}' not implemented in this bridge build")


__all__ = ["run_sofistik_job"]
