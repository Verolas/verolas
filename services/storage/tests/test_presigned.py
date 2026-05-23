"""Presigned URL tests using moto to mock S3."""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from verolas_storage.presigned import PresignedUrlService, StorageSettings


@pytest.fixture
def settings() -> StorageSettings:
    return StorageSettings(
        endpoint_url=None,
        region="us-east-1",
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        bucket="verolas-files-dev",
    )


@pytest.fixture
def mocked_s3(settings: StorageSettings) -> Iterator[None]:
    with mock_aws():
        client = boto3.client(
            "s3",
            region_name=settings.region,
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
        )
        # us-east-1 buckets must be created without a LocationConstraint.
        client.create_bucket(Bucket=settings.bucket)
        yield None


@pytest.fixture
def service(settings: StorageSettings, mocked_s3: None) -> PresignedUrlService:
    _ = mocked_s3
    return PresignedUrlService(settings)


def test_presign_upload_returns_signed_put_url(service: PresignedUrlService) -> None:
    intent = service.presign_upload(key="orgs/X/projects/Y/plan.dwg", content_type="image/vnd.dwg")
    assert intent.method == "PUT"
    assert intent.url.startswith("https://")
    assert "plan.dwg" in intent.url
    assert intent.headers["Content-Type"] == "image/vnd.dwg"
    assert intent.expires_in == 900


def test_presign_download_returns_signed_get_url(service: PresignedUrlService) -> None:
    intent = service.presign_download(key="orgs/X/projects/Y/plan.dwg")
    assert intent.method == "GET"
    assert "plan.dwg" in intent.url


def test_initiate_multipart_returns_upload_id_and_part_urls(
    service: PresignedUrlService,
) -> None:
    upload_id, part_urls = service.initiate_multipart(
        key="orgs/X/large.bim",
        part_count=4,
        content_type="application/octet-stream",
    )
    assert isinstance(upload_id, str) and len(upload_id) > 0
    assert len(part_urls) == 4
    assert all(p.method == "PUT" for p in part_urls)
    assert all("partnumber=" in p.url.lower() for p in part_urls)
    # Each part URL must be distinct so a client cannot upload part 3 to the
    # part 1 URL.
    assert len({p.url for p in part_urls}) == 4


def test_initiate_multipart_rejects_bad_part_count(service: PresignedUrlService) -> None:
    with pytest.raises(ValueError, match="part_count must be"):
        service.initiate_multipart(key="foo", part_count=0)
    with pytest.raises(ValueError, match="part_count must be"):
        service.initiate_multipart(key="foo", part_count=10_001)
