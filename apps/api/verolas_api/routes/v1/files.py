"""File upload routes.

Today the storage primitives (presigned URL service, clamd client, macro
detection) light up, but the database row writes that bind the upload
to an `org_id` and `project_id` are 501 until the DB workstream lands.

The bulk of the lifecycle:
- `POST /v1/files` issues a presigned upload, classifies the filename,
  flags macro bearing files. The DB write is deferred.
- `POST /v1/files/{id}/complete` finalises a multipart upload and triggers
  the clamd scan. 501 until the DB row exists.
- `GET /v1/files/{id}` returns metadata. 501 until DB.
- `GET /v1/files/{id}/download` issues a presigned download. 501 until DB.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from verolas_storage import (
    FileKind,
    PresignedUpload,
    PresignedUrlService,
    classify_file,
)

from verolas_api.dependencies import CurrentAuth
from verolas_api.middleware import sla_tier

router = APIRouter(prefix="/files", tags=["files"])


class FileUploadRequest(BaseModel):
    """Client supplied details for a new upload."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    size_bytes: int = Field(ge=0, le=5 * 1024 * 1024 * 1024)
    project_id: str | None = Field(default=None)
    multipart_part_count: int | None = Field(default=None, ge=1, le=10_000)


class FileUploadResponse(BaseModel):
    """Presigned upload intents to hand back to the client."""

    model_config = ConfigDict(extra="forbid")

    file_id: str
    object_key: str
    bucket: str
    kind: FileKind
    macro_sandbox_required: bool
    single_part_upload: PresignedUpload | None
    multipart_upload_id: str | None
    multipart_part_urls: list[PresignedUpload] | None


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
    auth: CurrentAuth,
) -> FileUploadResponse:
    """Issue presigned upload URLs and register the file metadata.

    Today this is partial. We classify the filename, generate the storage
    intent, and return it. Persisting the row to the `files` table happens
    once the DB pool is wired by the next workstream. Without that, every
    upload still works end to end against the object store, but no record
    is kept on the platform side.
    """
    if auth.claims.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not have an active organisation.",
        )

    classification = classify_file(body.filename, body.content_type)
    storage = _storage_from_request(request)
    file_id = str(uuid4())
    object_key = f"orgs/{auth.claims.org_id}/files/{file_id}/{body.filename}"

    if body.multipart_part_count is not None:
        upload_id, part_urls = storage.initiate_multipart(
            key=object_key,
            part_count=body.multipart_part_count,
            content_type=body.content_type,
        )
        return FileUploadResponse(
            file_id=file_id,
            object_key=object_key,
            bucket=storage.bucket,
            kind=classification.kind,
            macro_sandbox_required=classification.requires_macro_sandbox,
            single_part_upload=None,
            multipart_upload_id=upload_id,
            multipart_part_urls=part_urls,
        )

    single = storage.presign_upload(key=object_key, content_type=body.content_type)
    return FileUploadResponse(
        file_id=file_id,
        object_key=object_key,
        bucket=storage.bucket,
        kind=classification.kind,
        macro_sandbox_required=classification.requires_macro_sandbox,
        single_part_upload=single,
        multipart_upload_id=None,
        multipart_part_urls=None,
    )


@router.post("/{file_id}/complete")
@sla_tier(1)
async def complete_upload(file_id: str, auth: CurrentAuth) -> dict[str, str]:
    _ = (file_id, auth)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Complete is wired when the database connection lands. "
            "Multipart finalisation against the object store works through the storage library; "
            "the DB write to mark the file ready is deferred."
        ),
    )


@router.get("/{file_id}")
@sla_tier(1)
async def get_file(file_id: str, auth: CurrentAuth) -> dict[str, str]:
    _ = (file_id, auth)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="File metadata read is wired when the database connection lands.",
    )


@router.get("/{file_id}/download")
@sla_tier(1)
async def get_download_url(file_id: str, auth: CurrentAuth) -> dict[str, str]:
    _ = (file_id, auth)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Download presign is wired when the database connection lands.",
    )
