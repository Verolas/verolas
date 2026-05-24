"""Verolas Library endpoints.

The Library is the org's shared content store: standard details,
template calc sheets, reference clauses, master specs, vendor
catalogs. An org admin uploads content here once and mounts any
folder into a project via the existing connectors binding flow.

URLs:

- `GET    /v1/orgs/{slug}/library/folders`
- `POST   /v1/orgs/{slug}/library/folders`
- `DELETE /v1/orgs/{slug}/library/folders/{folder_id}`
- `GET    /v1/orgs/{slug}/library/folders/{folder_id}/files`
- `POST   /v1/orgs/{slug}/library/folders/{folder_id}/files`
  (mirrors the project-scoped upload: presigns + writes the `files`
  row with `library_folder_id` set instead of `project_id`)
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

router = APIRouter(prefix="/orgs/{org_slug}/library", tags=["library"])


class LibraryFolderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class LibraryFolderOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    org_id: UUID
    name: str
    description: str | None
    created_by_user_id: UUID | None
    created_at: Any
    updated_at: Any
    file_count: int


class LibraryFileUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    size_bytes: int = Field(ge=0, le=5 * 1024 * 1024 * 1024)
    multipart_part_count: int | None = Field(default=None, ge=1, le=10_000)


class LibraryFileUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: UUID
    object_key: str
    bucket: str
    kind: FileKind
    macro_sandbox_required: bool
    single_part_upload: PresignedUpload | None
    multipart_upload_id: str | None
    multipart_part_urls: list[PresignedUpload] | None


class LibraryFileOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    org_id: UUID
    library_folder_id: UUID | None
    uploaded_by_user_id: UUID | None
    filename: str
    content_type: str | None
    kind: FileKind
    bucket: str
    object_key: str
    size_bytes: int | None
    status: str
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


@router.get("/folders", response_model=list[LibraryFolderOut])
@sla_tier(2)
async def list_folders(dep: DbOrgConn) -> list[LibraryFolderOut]:
    """List every library folder for the URL-scoped org."""
    conn, _ = dep
    cur = await conn.execute(
        """
        SELECT f.id, f.org_id, f.name, f.description, f.created_by_user_id,
               f.created_at, f.updated_at,
               (
                   SELECT COUNT(*)::int FROM files
                   WHERE library_folder_id = f.id AND status <> 'deleted'
               ) AS file_count
        FROM library_folders f
        ORDER BY f.name ASC
        """
    )
    rows = await cur.fetchall()
    return [
        LibraryFolderOut(
            id=row[0],
            org_id=row[1],
            name=row[2],
            description=row[3],
            created_by_user_id=row[4],
            created_at=row[5],
            updated_at=row[6],
            file_count=row[7],
        )
        for row in rows
    ]


@router.post(
    "/folders",
    response_model=LibraryFolderOut,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(2)
async def create_folder(
    body: LibraryFolderCreate,
    dep: DbOrgConn,
    auth: CurrentAuth,
) -> LibraryFolderOut:
    """Create a new library folder under the URL-scoped org."""
    _ = auth
    conn, ctx = dep
    folder_id = uuid4()
    try:
        cur = await conn.execute(
            """
            INSERT INTO library_folders (
                id, org_id, name, description, created_by_user_id
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id, org_id, name, description, created_by_user_id,
                      created_at, updated_at
            """,
            (folder_id, ctx.organization_id, body.name.strip(), body.description, ctx.user_id),
        )
    except Exception as exc:
        if "library_folders_org_name_unique" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A library folder named '{body.name}' already exists.",
            ) from exc
        raise
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Folder insert returned no row.",
        )
    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="library.folder.created",
        resource_type="library_folder",
        resource_id=row[0],
        payload={"name": row[2]},
    )
    return LibraryFolderOut(
        id=row[0],
        org_id=row[1],
        name=row[2],
        description=row[3],
        created_by_user_id=row[4],
        created_at=row[5],
        updated_at=row[6],
        file_count=0,
    )


@router.delete(
    "/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@sla_tier(2)
async def delete_folder(
    folder_id: UUID,
    dep: DbOrgConn,
    auth: CurrentAuth,
) -> None:
    """Delete a folder. Existing file rows have their `library_folder_id` nulled."""
    _ = auth
    conn, ctx = dep
    cur = await conn.execute(
        "DELETE FROM library_folders WHERE id = %s RETURNING name",
        (folder_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found.",
        )
    await record_activity(
        conn,
        org_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        action="library.folder.deleted",
        resource_type="library_folder",
        resource_id=folder_id,
        payload={"name": row[0]},
    )


@router.get(
    "/folders/{folder_id}/files",
    response_model=list[LibraryFileOut],
)
@sla_tier(2)
async def list_folder_files(
    folder_id: UUID,
    dep: DbOrgConn,
) -> list[LibraryFileOut]:
    """List files in the given folder, newest first."""
    conn, _ = dep
    cur = await conn.execute(
        """
        SELECT id, org_id, library_folder_id, uploaded_by_user_id,
               filename, content_type, kind, bucket, object_key,
               size_bytes, status, created_at, updated_at
        FROM files
        WHERE library_folder_id = %s AND status <> 'deleted'
        ORDER BY created_at DESC
        LIMIT 500
        """,
        (folder_id,),
    )
    rows = await cur.fetchall()
    return [
        LibraryFileOut(
            id=row[0],
            org_id=row[1],
            library_folder_id=row[2],
            uploaded_by_user_id=row[3],
            filename=row[4],
            content_type=row[5],
            kind=FileKind(row[6]),
            bucket=row[7],
            object_key=row[8],
            size_bytes=row[9],
            status=row[10],
            created_at=row[11],
            updated_at=row[12],
        )
        for row in rows
    ]


@router.post(
    "/folders/{folder_id}/files",
    response_model=LibraryFileUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(2)
async def upload_folder_file(
    folder_id: UUID,
    body: LibraryFileUploadRequest,
    request: Request,
    dep: DbOrgConn,
    auth: CurrentAuth,
    org_slug: Annotated[str, Path()],
) -> LibraryFileUploadResponse:
    """Presign an upload and write the initial `files` row under the folder."""
    _ = (auth, org_slug)
    conn, ctx = dep

    # Confirm the folder exists in this org (RLS implicitly enforces org_id).
    cur = await conn.execute("SELECT name FROM library_folders WHERE id = %s", (folder_id,))
    folder_row = await cur.fetchone()
    if folder_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found.",
        )

    classification = classify_file(body.filename, body.content_type)
    storage = _storage_from_request(request)
    file_id = uuid4()
    object_key = f"orgs/{ctx.organization_id}/library/{folder_id}/{file_id}/{body.filename}"

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
            id, org_id, library_folder_id, uploaded_by_user_id,
            filename, content_type, kind, macro_sandbox_required,
            bucket, object_key, multipart_upload_id, size_bytes, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploading')
        """,
        (
            file_id,
            ctx.organization_id,
            folder_id,
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
        action="library.file.uploaded",
        resource_type="file",
        resource_id=file_id,
        payload={
            "folder_id": str(folder_id),
            "filename": body.filename,
            "kind": classification.kind.value,
        },
    )
    return LibraryFileUploadResponse(
        file_id=file_id,
        object_key=object_key,
        bucket=storage.bucket,
        kind=classification.kind,
        macro_sandbox_required=classification.requires_macro_sandbox,
        single_part_upload=single_part,
        multipart_upload_id=upload_id,
        multipart_part_urls=part_urls,
    )


__all__: Annotated[list[str], "exported"] = ["router"]
