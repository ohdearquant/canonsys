# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Storage provider - AWS S3 file storage.

Usage:
    from app.providers.storage import StorageService, StoredFile

    service = StorageService()
    result = await service.upload("docs/file.pdf", data, "application/pdf")
    data = await service.download("docs/file.pdf")
"""

from .s3_endpoint import S3Endpoint, S3Request, create_s3_config
from .service import StorageService, StoredFile, UploadResult

__all__ = [
    "S3Endpoint",
    "S3Request",
    "StorageService",
    "StoredFile",
    "UploadResult",
    "create_s3_config",
]
