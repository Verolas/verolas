"""Helpers for tool adapters that depend on a vendor SDK.

Most Tier C engineering apps (SOFiSTiK, Tekla, SAP2000, ETABS,
STAAD, IDEA StatiCa, Plaxis) ship Windows-only Python bindings or
.NET assemblies. The bridge tries to import them at job time; if
the SDK is not present, the adapter returns a clear error to the
cloud so the firm knows which package is missing on that host.

We import lazily (inside the handler, not at module load) so a
bridge that only hosts SOFiSTiK never tries to import the Tekla
.NET bindings.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType


class SDKNotAvailable(RuntimeError):
    """Raised when the vendor SDK could not be imported.

    The runner catches this and reports the job failed with a clear
    message instead of letting the bridge crash.
    """


def import_sdk(module: str, install_hint: str) -> ModuleType:
    """Import a vendor SDK or raise SDKNotAvailable with a helpful message.

    `install_hint` is one short sentence that explains what needs to
    happen on the bridge host for this SDK to load (e.g. install the
    vendor's Python package, or run on Windows next to a licensed
    product install).
    """
    try:
        return import_module(module)
    except ImportError as exc:
        raise SDKNotAvailable(
            f"{module} is not installed on this bridge host. {install_hint}"
        ) from exc


__all__ = ["SDKNotAvailable", "import_sdk"]
