"""Adapter framework for workflow automated nodes.

Stages 1-5 ran every automated node with a placeholder completion. Stage
6 introduces real adapters: code that does actual work when an automated
node becomes READY. Each adapter is registered against a `tool` string;
the runs service dispatches the registered adapter for any automated
node whose `params.tool` matches.

This module is the registry. Concrete adapters live in sibling modules
under `verolas_api.workflow.adapters` and self-register at import time.
`bootstrap_workflow_adapters()` is called once at api startup to force
those imports.
"""

from __future__ import annotations

from typing import Final

from verolas_api.workflow.adapters.base import NodeAdapter

_ADAPTERS: Final[dict[str, NodeAdapter]] = {}


def register_adapter(adapter: NodeAdapter) -> None:
    """Register an adapter. Idempotent only if the same instance re-registers."""
    if adapter.tool in _ADAPTERS:
        if _ADAPTERS[adapter.tool] is adapter:
            return
        raise RuntimeError(
            f"Adapter tool {adapter.tool!r} is registered twice with different implementations."
        )
    _ADAPTERS[adapter.tool] = adapter


def get_adapter(tool: str) -> NodeAdapter | None:
    """Return the adapter for `tool` if registered, else None."""
    return _ADAPTERS.get(tool)


def registered_tools() -> list[str]:
    """Return the sorted list of registered adapter tool keys."""
    return sorted(_ADAPTERS.keys())


def clear_adapters_for_tests() -> None:
    """Reset the registry. Tests only."""
    _ADAPTERS.clear()


def bootstrap_workflow_adapters() -> None:
    """Import every adapter module so its registration runs."""
    from verolas_api.workflow.adapters import (
        origin_generator as _origin_generator,
    )
    from verolas_api.workflow.adapters import (
        statik_compile as _statik_compile,
    )

    _ = (_origin_generator, _statik_compile)


__all__ = [
    "NodeAdapter",
    "bootstrap_workflow_adapters",
    "clear_adapters_for_tests",
    "get_adapter",
    "register_adapter",
    "registered_tools",
]
