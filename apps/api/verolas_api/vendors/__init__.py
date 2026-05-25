"""Per-vendor adapters.

Each module in this package implements the live integration for one
vendor: token refresh, the per-class instance fetchers registered
with `verolas_api.connector_instances`, and (later) the sync workers.

Call `bootstrap_vendors()` once at app startup to force-load every
adapter. We use an explicit call (rather than a side-effect import
at module top) because tooling can otherwise prune an import whose
return value is never read, leaving fetchers unregistered in prod.
"""

from __future__ import annotations


def bootstrap_vendors() -> None:
    """Import every vendor adapter so its fetcher registrations run."""
    from verolas_api.vendors import autodesk as _autodesk
    from verolas_api.vendors import google as _google
    from verolas_api.vendors import microsoft as _microsoft

    # Reference the modules so linters keep the imports alive.
    _ = (_autodesk, _google, _microsoft)


__all__ = ["bootstrap_vendors"]
