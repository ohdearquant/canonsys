# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""S3 storage endpoint using lionpride Endpoint pattern with boto3 SDK."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from canon.utils.endpoints import register_endpoint
from kron.services import Endpoint, EndpointConfig, NormalizedResponse

logger = logging.getLogger(__name__)

__all__ = (
    "S3Endpoint",
    "S3Request",
    "create_s3_config",
)


class S3Request(BaseModel):
    """S3 operation request."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["upload", "download", "delete", "head", "list", "presign"]
    key: str
    data: bytes | None = None
    content_type: str | None = None
    metadata: dict[str, str] | None = None
    prefix: str | None = None
    max_keys: int = 1000
    expires_in: int = 3600
    for_upload: bool = False


def create_s3_config(
    bucket_env: str = "CANON_S3_BUCKET",
    region_env: str = "AWS_REGION",
    timeout: int = 60,
) -> dict:
    """Factory for S3 endpoint config.

    Args:
        bucket_env: Environment variable name for bucket.
        region_env: Environment variable name for region.
        timeout: Request timeout in seconds.

    Returns:
        Config dict for S3Endpoint.
    """
    return {
        "provider": "aws",
        "name": "s3",
        "base_url": "",  # Not used for SDK
        "endpoint": "s3",
        "method": "SDK",
        "timeout": timeout,
        "request_options": S3Request,
        "client_kwargs": {
            "bucket_env": bucket_env,
            "region_env": region_env,
        },
    }


@register_endpoint(provider="aws", endpoint="s3")
class S3Endpoint(Endpoint):
    """S3 storage endpoint using boto3 SDK.

    Overrides call() to use boto3 instead of HTTP.

    Usage:
        endpoint = S3Endpoint()
        response = await endpoint.call({
            "operation": "upload",
            "key": "docs/file.pdf",
            "data": pdf_bytes,
            "content_type": "application/pdf",
        })
    """

    def __init__(
        self,
        config: dict | EndpointConfig | None = None,
        bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        **kwargs,
    ):
        """Initialize S3 endpoint."""
        if config is None:
            config = create_s3_config()
        elif isinstance(config, EndpointConfig):
            config = config.model_dump()

        # Extract bucket/region from config or env
        client_kwargs = config.get("client_kwargs", {})
        self._bucket = bucket or os.getenv(client_kwargs.get("bucket_env", "CANON_S3_BUCKET"))
        self._region = region or os.getenv(
            client_kwargs.get("region_env", "AWS_REGION"), "us-east-1"
        )
        self._endpoint_url = endpoint_url
        self._client: Any = None

        super().__init__(config=config, **kwargs)

    def _get_client(self) -> Any:
        """Get or create boto3 S3 client."""
        if self._client is None:
            try:
                import boto3
            except ImportError as err:
                raise RuntimeError(
                    "boto3 package required. Install with: pip install boto3"
                ) from err

            client_args: dict[str, Any] = {"region_name": self._region}
            if self._endpoint_url:
                client_args["endpoint_url"] = self._endpoint_url

            self._client = boto3.client("s3", **client_args)

        return self._client

    def _get_url(self, key: str) -> str:
        """Generate public URL for a key."""
        if self._endpoint_url:
            return f"{self._endpoint_url}/{self._bucket}/{key}"
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"

    async def call(
        self,
        request: dict | BaseModel,
        **kwargs,
    ) -> NormalizedResponse:
        """Execute S3 operation using boto3 SDK.

        Overrides Endpoint.call() to use SDK instead of HTTP.
        """
        # Validate request
        req = S3Request(**request) if isinstance(request, dict) else request

        if not self._bucket:
            return NormalizedResponse(
                status="error",
                error="Bucket not configured. Set CANON_S3_BUCKET.",
                raw_response={},
            )

        client = self._get_client()
        operation = req.operation

        try:
            if operation == "upload":
                return await self._upload(client, req)
            elif operation == "download":
                return await self._download(client, req)
            elif operation == "delete":
                return await self._delete(client, req)
            elif operation == "head":
                return await self._head(client, req)
            elif operation == "list":
                return await self._list(client, req)
            elif operation == "presign":
                return await self._presign(client, req)
            else:
                return NormalizedResponse(
                    status="error",
                    error=f"Unknown operation: {operation}",
                    raw_response={},
                )
        except Exception as e:
            logger.error("S3 %s failed for %s: %s", operation, req.key, str(e))
            return NormalizedResponse(
                status="error",
                error=str(e),
                raw_response={},
            )

    async def _upload(self, client: Any, req: S3Request) -> NormalizedResponse:
        """Upload file to S3."""
        data = req.data
        if data is None:
            return NormalizedResponse(status="error", error="No data provided", raw_response={})

        etag = hashlib.md5(data).hexdigest()
        size = len(data)

        upload_args: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": req.key,
            "Body": data,
        }
        if req.content_type:
            upload_args["ContentType"] = req.content_type
        if req.metadata:
            upload_args["Metadata"] = req.metadata

        await asyncio.to_thread(client.put_object, **upload_args)

        logger.info("File uploaded to S3: %s (%d bytes)", req.key, size)

        return NormalizedResponse(
            status="success",
            data={
                "key": req.key,
                "url": self._get_url(req.key),
                "size": size,
                "content_type": req.content_type,
                "etag": etag,
            },
            raw_response={"operation": "upload", "key": req.key},
        )

    async def _download(self, client: Any, req: S3Request) -> NormalizedResponse:
        """Download file from S3."""
        response = await asyncio.to_thread(
            client.get_object,
            Bucket=self._bucket,
            Key=req.key,
        )
        data = response["Body"].read()

        logger.info("File downloaded from S3: %s (%d bytes)", req.key, len(data))

        return NormalizedResponse(
            status="success",
            data={
                "key": req.key,
                "data": data,
                "size": len(data),
                "content_type": response.get("ContentType"),
                "etag": response.get("ETag", "").strip('"'),
            },
            raw_response={"operation": "download", "key": req.key},
        )

    async def _delete(self, client: Any, req: S3Request) -> NormalizedResponse:
        """Delete file from S3."""
        # Check if exists first
        try:
            await asyncio.to_thread(
                client.head_object,
                Bucket=self._bucket,
                Key=req.key,
            )
        except client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return NormalizedResponse(
                    status="success",
                    data={"key": req.key, "deleted": False, "reason": "not_found"},
                    raw_response={"operation": "delete", "key": req.key},
                )
            raise

        await asyncio.to_thread(
            client.delete_object,
            Bucket=self._bucket,
            Key=req.key,
        )

        logger.info("File deleted from S3: %s", req.key)

        return NormalizedResponse(
            status="success",
            data={"key": req.key, "deleted": True},
            raw_response={"operation": "delete", "key": req.key},
        )

    async def _head(self, client: Any, req: S3Request) -> NormalizedResponse:
        """Get file metadata from S3."""
        response = await asyncio.to_thread(
            client.head_object,
            Bucket=self._bucket,
            Key=req.key,
        )

        return NormalizedResponse(
            status="success",
            data={
                "key": req.key,
                "url": self._get_url(req.key),
                "size": response.get("ContentLength", 0),
                "content_type": response.get("ContentType", "application/octet-stream"),
                "etag": response.get("ETag", "").strip('"'),
                "last_modified": response.get("LastModified"),
                "metadata": response.get("Metadata"),
            },
            raw_response={"operation": "head", "key": req.key},
        )

    async def _list(self, client: Any, req: S3Request) -> NormalizedResponse:
        """List files in S3 bucket."""
        response = await asyncio.to_thread(
            client.list_objects_v2,
            Bucket=self._bucket,
            Prefix=req.prefix or "",
            MaxKeys=req.max_keys,
        )

        files = []
        for obj in response.get("Contents", []):
            files.append(
                {
                    "key": obj["Key"],
                    "url": self._get_url(obj["Key"]),
                    "size": obj.get("Size", 0),
                    "etag": obj.get("ETag", "").strip('"'),
                    "last_modified": obj.get("LastModified"),
                }
            )

        return NormalizedResponse(
            status="success",
            data={"files": files, "count": len(files)},
            raw_response={"operation": "list", "prefix": req.prefix},
        )

    async def _presign(self, client: Any, req: S3Request) -> NormalizedResponse:
        """Generate presigned URL."""
        method = "put_object" if req.for_upload else "get_object"
        url = await asyncio.to_thread(
            client.generate_presigned_url,
            method,
            Params={"Bucket": self._bucket, "Key": req.key},
            ExpiresIn=req.expires_in,
        )

        logger.debug("Generated presigned URL for %s (expires in %ds)", req.key, req.expires_in)

        return NormalizedResponse(
            status="success",
            data={"key": req.key, "url": url, "expires_in": req.expires_in},
            raw_response={"operation": "presign", "key": req.key},
        )

    def normalize_response(self, raw_response: dict[str, Any]) -> NormalizedResponse:
        """Not used - call() handles normalization directly."""
        return NormalizedResponse(
            status="success",
            data=raw_response,
            raw_response=raw_response,
        )
