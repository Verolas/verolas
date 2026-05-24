"""SharePoint document library sync.

Walks the bound SharePoint drive via Microsoft Graph's `/delta`
endpoint. On first sync, the delta walk returns everything; on
subsequent runs it returns only changes since the stored
deltaLink. Each item that is a file gets:

1. Downloaded via its `@microsoft.graph.downloadUrl` (a short-lived
   pre-signed URL Graph hands back inline).
2. Streamed to object storage under
   `orgs/{org}/projects/{project}/sync/{binding}/{drive-item}`.
3. Persisted (or updated) as a row in the `files` table tagged with
   the binding_id + external_ref. The partial unique index handles
   upserts: same external_ref under the same binding = same row.

Deleted items returned by `/delta` flip the `files.status` to
'deleted'. Folders are skipped (we sync content, not the tree).
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from psycopg import AsyncConnection
from verolas_storage import PresignedUrlService, classify_file

from verolas_api.sync.result import SyncResult
from verolas_api.vendors.microsoft import _ensure_fresh_token

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
MAX_FILE_BYTES = 1 * 1024 * 1024 * 1024  # 1 GiB upper bound per item


async def sync_sharepoint_binding(
    *,
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
    """Pull every file from the bound SharePoint drive into the project's Vault."""
    drive_id = _drive_id_from_instance_ref(instance_ref)
    if drive_id is None:
        return SyncResult(notes=[f"Could not parse drive id from instance_ref={instance_ref}"])

    token = await _ensure_fresh_token(credentials)

    delta_link = config.get("sharepoint", {}).get("delta_link")
    if isinstance(delta_link, str) and delta_link.startswith(GRAPH_BASE):
        next_path: str | None = delta_link[len(GRAPH_BASE) :]
    else:
        next_path = f"/drives/{drive_id}/root/delta"

    files_added = 0
    files_updated = 0
    files_removed = 0
    bytes_pulled = 0
    cursor: str | None = None

    async with httpx.AsyncClient(timeout=60.0) as client:
        while next_path:
            page = await _graph_get(client, next_path, token)
            for item in page.get("value") or []:
                if not isinstance(item, dict):
                    continue
                external_ref = str(item.get("id") or "")
                if not external_ref:
                    continue
                if item.get("deleted"):
                    files_removed += await _mark_deleted(conn, binding_id, external_ref)
                    continue
                if "folder" in item:
                    continue  # skip directories
                size = item.get("size")
                if not isinstance(size, int) or size <= 0 or size > MAX_FILE_BYTES:
                    continue
                download_url = item.get("@microsoft.graph.downloadUrl")
                filename = str(item.get("name") or "untitled")
                if not isinstance(download_url, str):
                    continue
                added, updated = await _ingest_one(
                    conn=conn,
                    client=client,
                    storage=storage,
                    binding_id=binding_id,
                    project_id=project_id,
                    org_id=org_id,
                    user_id=user_id,
                    external_ref=external_ref,
                    filename=filename,
                    content_type=(item.get("file") or {}).get("mimeType"),
                    size=size,
                    download_url=download_url,
                )
                files_added += added
                files_updated += updated
                bytes_pulled += size
            cursor = page.get("@odata.deltaLink") or page.get("@odata.nextLink")
            if not isinstance(cursor, str) or not cursor.startswith(GRAPH_BASE):
                next_path = None
            elif "@odata.deltaLink" in page:
                # End of this sync run.
                next_path = None
            else:
                next_path = cursor[len(GRAPH_BASE) :]

    return SyncResult(
        files_added=files_added,
        files_updated=files_updated,
        files_removed=files_removed,
        bytes_pulled=bytes_pulled,
        next_cursor=cursor if isinstance(cursor, str) else None,
    )


async def _graph_get(client: httpx.AsyncClient, path: str, token: str) -> dict[str, Any]:
    response = await client.get(
        f"{GRAPH_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Graph GET {path} failed ({response.status_code}): {response.text}")
    payload: Any = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Graph GET {path} returned non-object payload.")
    return payload


def _drive_id_from_instance_ref(instance_ref: str) -> str | None:
    """instance_ref format: `site:<id>/drive:<id>`."""
    parts = instance_ref.split("/")
    for part in parts:
        if part.startswith("drive:"):
            return part.removeprefix("drive:") or None
    return None


async def _mark_deleted(conn: AsyncConnection, binding_id: UUID, external_ref: str) -> int:
    cur = await conn.execute(
        """
        UPDATE files SET status = 'deleted'
        WHERE binding_id = %s AND external_ref = %s AND status <> 'deleted'
        """,
        (binding_id, external_ref),
    )
    return cur.rowcount or 0


async def _ingest_one(
    *,
    conn: AsyncConnection,
    client: httpx.AsyncClient,
    storage: PresignedUrlService,
    binding_id: UUID,
    project_id: UUID,
    org_id: UUID,
    user_id: UUID | None,
    external_ref: str,
    filename: str,
    content_type: str | None,
    size: int,
    download_url: str,
) -> tuple[int, int]:
    """Returns (added, updated)."""
    # Already have this external_ref under this binding?
    cur = await conn.execute(
        "SELECT id, object_key FROM files WHERE binding_id = %s AND external_ref = %s",
        (binding_id, external_ref),
    )
    existing = await cur.fetchone()

    file_id = UUID(str(existing[0])) if existing else uuid4()
    object_key = (
        existing[1]
        if existing
        else f"orgs/{org_id}/projects/{project_id}/sync/{binding_id}/{file_id}/{filename}"
    )

    # Download from SharePoint -> upload to S3.
    # The @microsoft.graph.downloadUrl is an absolute presigned URL; no auth header.
    resp = await client.get(download_url)
    if resp.status_code >= 400:
        raise RuntimeError(f"Download {filename} failed ({resp.status_code}): {resp.text[:200]}")
    body = resp.content
    storage.put_bytes(key=object_key, body=body, content_type=content_type)

    classification = classify_file(filename, content_type)

    if existing:
        await conn.execute(
            """
            UPDATE files
            SET filename = %s, content_type = %s, kind = %s, size_bytes = %s,
                status = 'ready', updated_at = now()
            WHERE id = %s
            """,
            (filename, content_type, classification.kind.value, size, file_id),
        )
        return (0, 1)

    await conn.execute(
        """
        INSERT INTO files (
            id, org_id, project_id, uploaded_by_user_id,
            filename, content_type, kind, macro_sandbox_required,
            bucket, object_key, size_bytes, status,
            binding_id, external_ref
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ready', %s, %s)
        """,
        (
            file_id,
            org_id,
            project_id,
            user_id,
            filename,
            content_type,
            classification.kind.value,
            classification.requires_macro_sandbox,
            storage.bucket,
            object_key,
            size,
            binding_id,
            external_ref,
        ),
    )
    return (1, 0)


# Keep _SHAREPOINT_HOST referenced so deployment env-driven overrides land here later.
_SHAREPOINT_HOST = urlparse(os.environ.get("SHAREPOINT_HOST", "")).hostname or "graph"

__all__ = ["sync_sharepoint_binding"]
