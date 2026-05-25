"""Tool adapters dispatched by class_id.

A tool adapter takes a job payload and returns a serialisable result
plus optional output files. The dispatcher in `verolas_bridge.runner`
looks up the right adapter by the job's `class_id`. None ship in
this release; concrete adapters (RFEM, SOFiSTiK, Tekla, ...) follow.
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


__all__ = ["ToolHandler", "handler_for", "register"]
