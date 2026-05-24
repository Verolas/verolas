"""Per-class instance fetchers for the project bind picker.

When a project manager opens the connector binding form, the UI calls
`GET /v1/orgs/{slug}/connectors/{class_id}/instances`. That endpoint
dispatches to a fetcher registered here, passes in the installation's
decrypted access token, and gets back a list of `{ref, label}` rows
the picker renders.

Registering a fetcher is opt-in. Classes without one fall back to the
free-form ref+label form already shipped in the project Connectors
page. Real per-vendor fetchers land in later batches; this PR ships
the dispatcher and an empty registry so the contract is set.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ConnectorInstanceOption:
    """One row a project bind picker shows."""

    ref: str
    label: str
    hint: str | None = None


InstanceFetcher = Callable[[dict[str, Any]], Awaitable[list[ConnectorInstanceOption]]]


_REGISTRY: dict[str, InstanceFetcher] = {}


def register(class_id: str) -> Callable[[InstanceFetcher], InstanceFetcher]:
    """Decorator: register a fetcher for a connector class."""

    def wrap(fn: InstanceFetcher) -> InstanceFetcher:
        _REGISTRY[class_id] = fn
        return fn

    return wrap


def fetcher_for(class_id: str) -> InstanceFetcher | None:
    """Look up a fetcher by class id, or None if not registered."""
    return _REGISTRY.get(class_id)


__all__ = [
    "ConnectorInstanceOption",
    "InstanceFetcher",
    "fetcher_for",
    "register",
]
