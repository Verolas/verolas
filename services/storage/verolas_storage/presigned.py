"""Presigned URL service.

Wraps boto3 to issue presigned PUT URLs (single upload), presigned GET URLs
(download), and to drive multipart uploads for large files (up to the 5 GB
per file ceiling from the bible).

Single shot uploads (object content under roughly 100 MB):
    intent = service.presign_upload(key="orgs/X/projects/Y/file.dwg")
    # client PUTs file bytes to intent.url with the headers in intent.headers
    # then calls back to /v1/files/{id}/complete

Multipart uploads (anything larger, or any time the client wants resumable):
    multipart = service.initiate_multipart(key=..., part_size_bytes=...)
    # client PUTs each part to its presigned URL
    service.complete_multipart(key=..., upload_id=..., parts=[...])

The service uses synchronous boto3. Presigned URL generation is local and
does not call S3 (it is HMAC over the request). Multipart initiate and
complete do call S3; callers in async code should run them via
`asyncio.to_thread`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.client import Config
from pydantic import BaseModel, Field

_MAX_OBJECT_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB per the bible
_MIN_MULTIPART_PART_SIZE = 5 * 1024 * 1024  # 5 MiB lower bound per S3
_MAX_MULTIPART_PART_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB upper bound per S3
_MAX_MULTIPART_PART_COUNT = 10_000  # S3 hard limit


class StorageSettings(BaseModel):
    """S3 backend connection details, loaded from VEROLAS_STORAGE_* env.

    `endpoint_url` is optional so unit tests can use the boto3 default URL
    and let moto intercept. Production always sets it to the Hetzner Object
    Storage endpoint, e.g. https://nbg1.your-objectstorage.com.
    """

    endpoint_url: str | None = Field(default=None)
    region: str = Field(default="nbg1")
    access_key_id: str
    secret_access_key: str
    bucket: str = Field(description="Bucket name for the active environment")
    signature_version: str = Field(default="s3v4")
    presign_expiry_seconds: int = Field(default=900, ge=60, le=7 * 24 * 3600)


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    """Inbound upload artefact handed to a client."""

    url: str
    method: str
    headers: dict[str, str]
    expires_in: int
    key: str


@dataclass(frozen=True, slots=True)
class PresignedDownload:
    """Outbound download artefact handed to a client."""

    url: str
    method: str
    expires_in: int
    key: str


@dataclass(slots=True)
class _MultipartHandle:
    upload_id: str
    part_urls: list[str] = field(default_factory=list)


class PresignedUrlService:
    """Stateless service over the S3 client.

    Construct once per application, share across requests. The boto3 client
    is thread safe for the presign calls used here.
    """

    def __init__(self, settings: StorageSettings) -> None:
        self._settings = settings
        client_kwargs: dict[str, Any] = {
            "region_name": settings.region,
            "aws_access_key_id": settings.access_key_id,
            "aws_secret_access_key": settings.secret_access_key,
            "config": Config(signature_version=settings.signature_version),
        }
        if settings.endpoint_url:
            client_kwargs["endpoint_url"] = settings.endpoint_url
        self._client = boto3.client("s3", **client_kwargs)

    @property
    def bucket(self) -> str:
        return self._settings.bucket

    @property
    def max_object_size_bytes(self) -> int:
        return _MAX_OBJECT_SIZE_BYTES

    def presign_upload(self, key: str, content_type: str | None = None) -> PresignedUpload:
        """Single shot upload URL. Use for small files."""
        params: dict[str, Any] = {"Bucket": self._settings.bucket, "Key": key}
        if content_type:
            params["ContentType"] = content_type
        url = self._client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=self._settings.presign_expiry_seconds,
            HttpMethod="PUT",
        )
        headers: dict[str, str] = {}
        if content_type:
            headers["Content-Type"] = content_type
        return PresignedUpload(
            url=url,
            method="PUT",
            headers=headers,
            expires_in=self._settings.presign_expiry_seconds,
            key=key,
        )

    def presign_download(self, key: str) -> PresignedDownload:
        """Read URL for a stored object."""
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._settings.bucket, "Key": key},
            ExpiresIn=self._settings.presign_expiry_seconds,
            HttpMethod="GET",
        )
        return PresignedDownload(
            url=url,
            method="GET",
            expires_in=self._settings.presign_expiry_seconds,
            key=key,
        )

    def initiate_multipart(
        self,
        key: str,
        *,
        part_count: int,
        content_type: str | None = None,
    ) -> tuple[str, list[PresignedUpload]]:
        """Start a multipart upload and return the upload id plus part URLs.

        `part_count` is the number of parts the client will upload. Must be
        in [1, 10000] per S3.
        """
        if not 1 <= part_count <= _MAX_MULTIPART_PART_COUNT:
            raise ValueError(
                f"part_count must be in [1, {_MAX_MULTIPART_PART_COUNT}]; got {part_count}"
            )

        create_args: dict[str, Any] = {"Bucket": self._settings.bucket, "Key": key}
        if content_type:
            create_args["ContentType"] = content_type
        response = self._client.create_multipart_upload(**create_args)
        upload_id: str = response["UploadId"]

        part_urls: list[PresignedUpload] = []
        for part_number in range(1, part_count + 1):
            url = self._client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self._settings.bucket,
                    "Key": key,
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=self._settings.presign_expiry_seconds,
                HttpMethod="PUT",
            )
            part_urls.append(
                PresignedUpload(
                    url=url,
                    method="PUT",
                    headers={},
                    expires_in=self._settings.presign_expiry_seconds,
                    key=key,
                )
            )
        return upload_id, part_urls

    def complete_multipart(
        self,
        key: str,
        upload_id: str,
        parts: list[dict[str, Any]],
    ) -> None:
        """Finalise a multipart upload. `parts` is a list of `{ETag, PartNumber}`."""
        self._client.complete_multipart_upload(
            Bucket=self._settings.bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

    def abort_multipart(self, key: str, upload_id: str) -> None:
        """Abort a multipart upload and clean up its parts."""
        self._client.abort_multipart_upload(
            Bucket=self._settings.bucket,
            Key=key,
            UploadId=upload_id,
        )


__all__ = [
    "PresignedDownload",
    "PresignedUpload",
    "PresignedUrlService",
    "StorageSettings",
]
