"""Tool adapters dispatched by class_id.

A tool adapter takes a job payload and returns a serialisable result
plus optional output files. The dispatcher in `verolas_bridge.runner`
looks up the right adapter by the job's `class_id`.

Adapter modules register themselves via the `@register` decorator at
import time. `bootstrap_tools()` imports every adapter so the
registrations are present even if no job has been dispatched yet.

Many adapters depend on vendor SDKs that only install on Windows
next to a licensed copy of the engineering software (SOFiSTiK,
Tekla, SAP2000, etc.). Each handler imports its SDK lazily inside
the function body and returns a clean error when the SDK is missing.
That lets a single bridge build serve whichever subset of tools the
firm actually has on a given host.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


_REGISTRY: dict[str, ToolHandler] = {}


def register(class_id: str) -> Callable[[ToolHandler], ToolHandler]:
    """Decorator: register a tool handler for a connector class id."""

    def wrap(fn: ToolHandler) -> ToolHandler:
        _REGISTRY[class_id] = fn
        return fn

    return wrap


def handler_for(class_id: str) -> ToolHandler | None:
    return _REGISTRY.get(class_id)


def bootstrap_tools() -> None:
    """Import every adapter so their handlers register with this module."""
    from verolas_bridge.tools import csi_suite as _csi
    from verolas_bridge.tools import idea_statica as _idea
    from verolas_bridge.tools import plaxis as _plaxis
    from verolas_bridge.tools import projectwise as _pw
    from verolas_bridge.tools import rfem as _rfem
    from verolas_bridge.tools import rhino as _rhino
    from verolas_bridge.tools import sofistik as _sofistik
    from verolas_bridge.tools import staad as _staad
    from verolas_bridge.tools import tekla as _tekla

    _ = (_csi, _idea, _plaxis, _pw, _rfem, _rhino, _sofistik, _staad, _tekla)


__all__ = ["ToolHandler", "bootstrap_tools", "handler_for", "register"]
