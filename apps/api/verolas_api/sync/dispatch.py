"""Dispatch a sync request to the right vendor engine.

Adding a new engine: import it here and add a branch to
`sync_binding()`. The signature is fixed across engines so we can
later swap to a registry-of-callables if it grows past 5-6 vendors.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from verolas_storage import PresignedUrlService

from verolas_api.sync.result import SyncResult
from verolas_api.sync.sharepoint import sync_sharepoint_binding


async def sync_binding(
    *,
    class_id: str,
    conn: AsyncConnection,
    binding_id: UUID,
    project_id: UUID,
    org_id: UUID,
    user_id: UUID | None,
    instance_ref: str,
    config: dict[str, Any],
    credentials: dict[str, Any],
    storage: PresignedUrlService,
) -> SyncResult:
    """Run a sync for the given binding and return what changed."""
    if class_id == "ms-sharepoint":
        return await sync_sharepoint_binding(
            conn=conn,
            binding_id=binding_id,
            project_id=project_id,
            org_id=org_id,
            user_id=user_id,
            instance_ref=instance_ref,
            config=config,
            credentials=credentials,
            storage=storage,
        )
    return SyncResult(notes=[f"No sync engine wired for class '{class_id}' yet."])


__all__ = ["sync_binding"]
