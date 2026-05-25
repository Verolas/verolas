"""Adapter interface and shared types.

`NodeAdapter` is the contract every concrete adapter implements. The
runs service constructs an `AdapterContext` for each automated node it
dispatches, calls `run(ctx, inputs)`, and writes the returned
`AdapterResult` back to the run state.

Adapters are async because most real ones do I/O (HTTP calls to third
parties, S3 uploads via boto3-wrapped-in-threadpool, etc.). Pure-Python
adapters that do no I/O still implement async for uniformity.

Stage-6 dispatch is inline (synchronous from the API request's
perspective). When stage 6+ adapters take minutes (RFEM solver runs,
SOFiSTiK on Bridge, LLM-backed Origin), the runs service promotes
dispatch to a worker queue without the adapters themselves changing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from verolas_storage import PresignedUrlService


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """A file produced by an adapter, identified by storage key."""

    storage_key: str
    content_type: str
    size_bytes: int
    label: str  # human-readable, e.g. "Statik PDF"


@dataclass(frozen=True, slots=True)
class AdapterContext:
    """Everything an adapter needs to do its job."""

    org_id: UUID
    project_id: UUID
    run_id: UUID
    node_id: UUID
    node_key: str
    params: dict[str, Any]
    storage: PresignedUrlService | None  # None in tests; required in prod


@dataclass(frozen=True, slots=True)
class AdapterResult:
    """What the adapter returns to the runs service."""

    outputs: dict[str, Any] = field(default_factory=dict)
    artifacts: list[ArtifactRef] = field(default_factory=list)
    error: str | None = None  # set on failure; runs service marks node FAILED

    @property
    def succeeded(self) -> bool:
        return self.error is None


class NodeAdapter(ABC):
    """Abstract base. Concrete adapters set `tool` as a class attribute."""

    tool: str  # class-level identifier matching node.params["tool"]

    @abstractmethod
    async def run(
        self,
        ctx: AdapterContext,
        inputs: dict[str, Any],
    ) -> AdapterResult:
        """Execute the adapter.

        `inputs` is a dict keyed by upstream node_key, valued with that
        node's `outputs` dict. Adapters consume only the keys they need;
        adapters never see the full graph state.
        """
        ...
