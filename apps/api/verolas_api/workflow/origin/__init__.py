"""Verolas Origin domain logic.

This package holds the shared logic that powers the Origin workflow's
automated nodes: normalized building geometry, CAD parsers (DXF, IFC),
the quality-check module that flags issues for the engineer to review,
the parametric grid engine that lays a structural bay grid over a
parsed footprint, and (in later sub-stages) the rendering pipeline
that turns geometry into SVG, DXF, and IFC artifacts.

Adapters under `verolas_api.workflow.adapters.origin_*` wrap these
modules and integrate them with the workflow engine. Keeping the
domain logic separate from adapter plumbing keeps the parsers and the
grid engine unit-testable without any AdapterContext or storage I/O.
"""

from __future__ import annotations
