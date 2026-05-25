"""SAP2000 + ETABS adapter.

CSI ships the OAPI as a .NET assembly (SAP2000v1.dll / ETABSv1.dll).
We reach it through pythonnet on a Windows bridge host running a
licensed SAP2000 or ETABS install.

The class_id `csi-suite` is shared between both products; the
operator selects which one when binding the connector at the project
level. The payload's `product` field tells us which to launch.
"""

from __future__ import annotations

from typing import Any

from verolas_bridge.tools import register
from verolas_bridge.tools._sdk import import_sdk

INSTALL_HINT = (
    "Install SAP2000 or ETABS on the bridge host (Windows) and "
    "`pip install pythonnet` so the OAPI .NET assemblies are reachable."
)


@register("csi-suite")
async def run_csi_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a CSI (SAP2000 or ETABS) job by action."""
    action = payload.get("action") or "ping"
    product = (payload.get("product") or "sap2000").lower()
    if product not in {"sap2000", "etabs"}:
        raise RuntimeError(f"Unknown CSI product '{product}'; expected sap2000 or etabs")

    clr = import_sdk("clr", INSTALL_HINT)
    assembly = "SAP2000v1" if product == "sap2000" else "ETABSv1"
    clr.AddReference(assembly)

    # The dynamic .NET module is loaded only at runtime, so mypy
    # cannot follow this import. The handler catches AttributeError
    # at the OAPI call sites for clarity.
    sap = __import__(assembly, fromlist=["cOAPI", "cHelper"])

    helper = sap.cHelper()
    oapi = helper.CreateObjectProgID(
        f"CSI.{'SAP2000' if product == 'sap2000' else 'ETABS'}.API.SapObject"
    )
    if oapi is None:
        raise RuntimeError(f"Could not create {product} COM object; is the licensed app installed?")
    oapi.ApplicationStart()

    if action == "ping":
        version = oapi.SapModel.GetVersion()[0]
        oapi.ApplicationExit(False)
        return {"action": "ping", "product": product, "version": str(version)}

    if action == "open_model":
        path = payload.get("path")
        if not isinstance(path, str):
            raise RuntimeError("open_model requires a 'path' field")
        oapi.SapModel.File.OpenFile(path)
        oapi.ApplicationExit(False)
        return {"action": "open_model", "product": product, "path": path}

    oapi.ApplicationExit(False)
    raise RuntimeError(f"CSI action '{action}' not implemented in this bridge build")


__all__ = ["run_csi_job"]
