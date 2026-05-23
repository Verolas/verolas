"""File upload route tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import boto3
import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from moto import mock_aws
from verolas_storage import PresignedUrlService, StorageSettings

from tests.conftest import StubTokenVerifier
from verolas_api.main import create_app
from verolas_api.settings import Settings


@pytest.fixture
def mocked_storage() -> Iterator[PresignedUrlService]:
    with mock_aws():
        settings = StorageSettings(
            endpoint_url=None,
            region="us-east-1",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            bucket="verolas-files-dev",
        )
        admin = boto3.client(
            "s3",
            region_name=settings.region,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
        )
        admin.create_bucket(Bucket=settings.bucket)
        yield PresignedUrlService(settings)


@pytest.fixture
def files_app(token_verifier: StubTokenVerifier, mocked_storage: PresignedUrlService) -> FastAPI:
    return create_app(
        settings=Settings(log_json=False, environment="test"),
        token_verifier=token_verifier,  # type: ignore[arg-type]
        storage_service=mocked_storage,
    )


@pytest_asyncio.fixture
async def files_client(files_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(files_app):
        transport = httpx.ASGITransport(app=files_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as ac:
            yield ac


async def test_initiate_upload_returns_presigned_put_for_small_file(
    files_client: httpx.AsyncClient,
) -> None:
    response = await files_client.post(
        "/v1/files/",
        headers={"Authorization": "Bearer owner-token"},
        json={
            "filename": "drawing.dwg",
            "content_type": "image/vnd.dwg",
            "size_bytes": 1024,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["kind"] == "cad_drawing"
    assert payload["macro_sandbox_required"] is False
    assert payload["single_part_upload"] is not None
    assert payload["multipart_upload_id"] is None


async def test_initiate_upload_flags_macro_files(files_client: httpx.AsyncClient) -> None:
    response = await files_client.post(
        "/v1/files/",
        headers={"Authorization": "Bearer owner-token"},
        json={
            "filename": "kostenrechnung.xlsm",
            "size_bytes": 2048,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["kind"] == "office_macro"
    assert payload["macro_sandbox_required"] is True


async def test_initiate_upload_supports_multipart_for_large_files(
    files_client: httpx.AsyncClient,
) -> None:
    response = await files_client.post(
        "/v1/files/",
        headers={"Authorization": "Bearer owner-token"},
        json={
            "filename": "scan.ifc",
            "content_type": "application/octet-stream",
            "size_bytes": 250 * 1024 * 1024,
            "multipart_part_count": 5,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["single_part_upload"] is None
    assert payload["multipart_upload_id"] is not None
    assert payload["multipart_part_urls"] is not None
    assert len(payload["multipart_part_urls"]) == 5


async def test_initiate_upload_requires_auth(files_client: httpx.AsyncClient) -> None:
    response = await files_client.post(
        "/v1/files/",
        json={"filename": "x.txt", "size_bytes": 1},
    )
    assert response.status_code == 401


async def test_complete_upload_returns_501(files_client: httpx.AsyncClient) -> None:
    response = await files_client.post(
        "/v1/files/some-id/complete",
        headers={"Authorization": "Bearer owner-token"},
    )
    assert response.status_code == 501
