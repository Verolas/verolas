"""Project-scoped file upload + listing routes.

Sits at /v1/orgs/{slug}/projects/{project_id}/files/.
Uses the org-scoped dependency so RLS is enforced on every read and write.

Two endpoints:

- `POST /` — presign an upload URL and write the initial `files` row in
  'uploading' state. The client PUTs the bytes directly to object storage,
  then calls the complete endpoint (deferred) to flip the row to 'scanning'.
- `GET  /` — list this project's files, newest first.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict, Field
from verolas_storage import FileKind, PresignedUpload, PresignedUrlService, classify_file

from verolas_api.audit import record_activity
from verolas_api.dependencies import CurrentAuth
from verolas_api.dependencies.org import DbOrgConn
from verolas_api.middleware import sla_tier

router = APIRouter(
    prefix="/orgs/{org_slug}/projects/{project_id}/files",
    tags=["files"],
)


class FileUploadRequest(BaseModel):
    """Client supplied details for a new project-scoped upload."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    size_bytes: int = Field(ge=0, le=5 * 1024 * 1024 * 1024)
    multipart_part_count: int | None = Field(default=None, ge=1, le=10_000)


class FileUploadResponse(BaseModel):
    """Presigned upload intent + the file row id the client should reference."""

    model_config = ConfigDict(extra="forbid")

    file_id: UUID
    object_key: str
    bucket: str
    kind: FileKind
    macro_sandbox_required: bool
    single_part_upload: PresignedUpload | None
    multipart_upload_id: str | None
    multipart_part_urls: list[PresignedUpload] | None


class FileOut(BaseModel):
    """Wire shape for a `files` row."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    org_id: UUID
    project_id: UUID | None
    uploaded_by_user_id: UUID | None
    filename: str
    content_type: str | None
    kind: FileKind
    macro_sandbox_required: bool
    bucket: str
    object_key: str
    size_bytes: int | None
    status: str
    scan_verdict: str | None
    created_at: Any
    updated_at: Any


def _storage_from_request(request: Request) -> PresignedUrlService:
    service: PresignedUrlService | None = getattr(request.app.state, "storage_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not configured on the server.",
        )
    return service


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(1)
async def initiate_upload(
    body: FileUploadRequest,
    request: Request,
    dep: DbOrgConn,
    project_id: Annotated[UUID, Path()],
    auth: CurrentAuth,
) -> FileUploadResponse:
    """Issue presigned upload URLs and write the initial `files` row."""
    _ = auth
    conn, ctx = dep
    classification = classify_file(body.filename, body.content_type)
    storage = _storage_from_request(request)
    file_id = uuid4()
    object_key = f"orgs/{ctx.organization_id}/projects/{project_id}/files/{file_id}/{body.filename}"

    if body.multipart_part_count is not None:
        upload_id, part_urls = storage.initiate_multipart(
            key=object_key,
            part_count=body.multipart_part_count,
            content_type=body.content_type,
        )
        single_part: PresignedUpload | None = None
    else:
        upload_id = None
        part_urls = None
        single_part = storage.presign_upload(key=object_key, content_type=body.content_type)

    await conn.execute(
        """
        INSERT INTO files (
            id, org_id, project_id, uploaded_by_user_id,
            filename, content_type, kind, macro_sandbox_required,
            bucket, object_key, multipart_upload_id, size_bytes, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploading')
        """,
        (
            file_id,
            ctx.organization_id,
            project_id,
            ctx.user_id,
            body.filename,
            body.content_type,
            classification.kind.value,
            classification.requires_macro_sandbox,
            storage.bucket,
            object_key,
            upload_id,
            body.size_bytes,
        ),
    )
    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="file.upload.initiated",
        resource_type="file",
        resource_id=file_id,
        payload={
            "filename": body.filename,
            "kind": classification.kind.value,
            "project_id": str(project_id),
        },
    )
    return FileUploadResponse(
        file_id=file_id,
        object_key=object_key,
        bucket=storage.bucket,
        kind=classification.kind,
        macro_sandbox_required=classification.requires_macro_sandbox,
        single_part_upload=single_part,
        multipart_upload_id=upload_id,
        multipart_part_urls=part_urls,
    )


@router.get("/", response_model=list[FileOut])
@sla_tier(1)
async def list_files(
    dep: DbOrgConn,
    project_id: Annotated[UUID, Path()],
) -> list[FileOut]:
    """List the project's files, newest first."""
    conn, _ = dep
    cur = await conn.execute(
        """
        SELECT id, org_id, project_id, uploaded_by_user_id,
               filename, content_type, kind, macro_sandbox_required,
               bucket, object_key, size_bytes, status, scan_verdict,
               created_at, updated_at
        FROM files
        WHERE project_id = %s AND status <> 'deleted'
        ORDER BY created_at DESC
        LIMIT 500
        """,
        (project_id,),
    )
    rows = await cur.fetchall()
    return [
        FileOut(
            id=row[0],
            org_id=row[1],
            project_id=row[2],
            uploaded_by_user_id=row[3],
            filename=row[4],
            content_type=row[5],
            kind=FileKind(row[6]),
            macro_sandbox_required=row[7],
            bucket=row[8],
            object_key=row[9],
            size_bytes=row[10],
            status=row[11],
            scan_verdict=row[12],
            created_at=row[13],
            updated_at=row[14],
        )
        for row in rows
    ]


__all__: Annotated[list[str], "exported"] = ["router"]
