# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Storage service - thin wrapper over S3Endpoint."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import BinaryIO

__all__ = ("StorageService", "StoredFile", "UploadResult")


@dataclass(slots=True, frozen=True)
class StoredFile:
    """Metadata about a stored file."""

    key: str
    url: str
    size: int
    content_type: str
    etag: str | None = None
    last_modified: datetime | None = None
    metadata: dict[str, str] | None = None


@dataclass(slots=True)
class UploadResult:
    """Result of an upload operation."""

    key: str
    url: str
    size: int
    content_type: str
    etag: str
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None

    @property
    def is_success(self) -> bool:
        return self.error is None


class StorageService:
    """Storage service using S3Endpoint.

    Usage:
        service = StorageService()
        result = await service.upload("docs/file.pdf", data, "application/pdf")
        data = await service.download("docs/file.pdf")
    """

    def __init__(
        self,
        bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
    ):
        from .s3_endpoint import S3Endpoint

        self._endpoint = S3Endpoint(
            bucket=bucket,
            region=region,
            endpoint_url=endpoint_url,
        )

    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload file to S3."""
        if hasattr(data, "read"):
            data = data.read()

        response = await self._endpoint.call(
            {
                "operation": "upload",
                "key": key,
                "data": data,
                "content_type": content_type,
                "metadata": metadata,
            }
        )

        if response.status == "error":
            raise RuntimeError(f"Upload failed: {response.error}")

        return UploadResult(
            key=response.data["key"],
            url=response.data["url"],
            size=response.data["size"],
            content_type=response.data["content_type"] or content_type,
            etag=response.data["etag"],
        )

    async def download(self, key: str) -> bytes:
        """Download file from S3."""
        response = await self._endpoint.call(
            {
                "operation": "download",
                "key": key,
            }
        )

        if response.status == "error":
            raise RuntimeError(f"Download failed: {response.error}")

        return response.data["data"]

    async def delete(self, key: str) -> bool:
        """Delete file from S3."""
        response = await self._endpoint.call(
            {
                "operation": "delete",
                "key": key,
            }
        )

        if response.status == "error":
            raise RuntimeError(f"Delete failed: {response.error}")

        return response.data["deleted"]

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        for_upload: bool = False,
    ) -> str:
        """Generate presigned URL."""
        response = await self._endpoint.call(
            {
                "operation": "presign",
                "key": key,
                "expires_in": expires_in,
                "for_upload": for_upload,
            }
        )

        if response.status == "error":
            raise RuntimeError(f"Presign failed: {response.error}")

        return response.data["url"]

    async def get_metadata(self, key: str) -> StoredFile:
        """Get file metadata."""
        response = await self._endpoint.call(
            {
                "operation": "head",
                "key": key,
            }
        )

        if response.status == "error":
            raise RuntimeError(f"File not found: {key}")

        return StoredFile(
            key=response.data["key"],
            url=response.data["url"],
            size=response.data["size"],
            content_type=response.data["content_type"],
            etag=response.data["etag"],
            last_modified=response.data.get("last_modified"),
            metadata=response.data.get("metadata"),
        )

    async def list_files(
        self,
        prefix: str = "",
        max_results: int = 1000,
    ) -> list[StoredFile]:
        """List files in bucket."""
        response = await self._endpoint.call(
            {
                "operation": "list",
                "key": "",
                "prefix": prefix,
                "max_keys": max_results,
            }
        )

        if response.status == "error":
            raise RuntimeError(f"List failed: {response.error}")

        return [
            StoredFile(
                key=f["key"],
                url=f["url"],
                size=f["size"],
                content_type="application/octet-stream",
                etag=f.get("etag"),
                last_modified=f.get("last_modified"),
            )
            for f in response.data["files"]
        ]
