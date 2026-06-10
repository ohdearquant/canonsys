# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Provider infrastructure - external service integrations.

This module contains PURE INFRASTRUCTURE code. No compliance logic.

Architecture:
    providers/
    ├── storage/            # File storage (S3)
    ├── market/             # External data sources (Apify)
    └── security/           # Key management (KMS, Vault)

Endpoints use the canon.kron.services Endpoint pattern.
"""

# Storage
from .storage import StorageService, StoredFile, UploadResult

__all__ = [
    # Storage
    "StorageService",
    "StoredFile",
    "UploadResult",
]
