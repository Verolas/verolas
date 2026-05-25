"""STAAD.Pro adapter (OpenSTAAD via Windows COM)."""

from __future__ import annotations

from typing import Any

from verolas_bridge.tools import register
from verolas_bridge.tools._sdk import import_sdk

INSTALL_HINT = (
    "Install STAAD.Pro on the bridge host (Windows) and "
    "`pip install pywin32` so OpenSTAAD COM is reachable from Python."
)


@register("staad")
async def run_staad_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a STAAD.Pro job by action."""
    action = payload.get("action") or "ping"
    pythoncom = import_sdk("pythoncom", INSTALL_HINT)
    win32com = import_sdk("win32com.client", INSTALL_HINT)

    pythoncom.CoInitialize()
    try:
        openstaad = win32com.Dispatch("StaadPro.OpenSTAAD")
        if action == "ping":
            version = openstaad.GetSTAADVersion()
            return {"action": "ping", "staad_version": str(version)}
        if action == "open_model":
            path = payload.get("path")
            if not isinstance(path, str):
                raise RuntimeError("open_model requires a 'path' field")
            openstaad.OpenSTAADFile(path, False)
            return {"action": "open_model", "path": path}
        raise RuntimeError(f"STAAD action '{action}' not implemented in this bridge build")
    finally:
        pythoncom.CoUninitialize()


__all__ = ["run_staad_job"]
