"""Per-vendor adapters.

Each module in this package implements the live integration for one
vendor: token refresh, the per-class instance fetchers registered
with `verolas_api.connector_instances`, and (later) the sync workers.

Modules are imported for their side effects at app startup so the
fetcher registrations stick. See `verolas_api.vendors.bootstrap`.
"""

from __future__ import annotations

from verolas_api.vendors import microsoft  # noqa: F401  (register fetchers)

__all__: list[str] = []
