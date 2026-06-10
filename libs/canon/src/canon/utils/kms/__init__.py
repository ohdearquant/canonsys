# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""HSM-backed Key Management Service for crypto-shredding.

Provides:
- Per-candidate DEKs for granular crypto-shredding
- KEK hierarchy for efficient key management
- HSM integration (AWS KMS, Azure Key Vault, GCP KMS, HashiCorp Vault)
- Key destruction certificates for audit compliance
- NIST SP 800-57 compliant key lifecycle

Legal foundation:
- GDPR Article 17: Right to erasure (crypto-shredding)
- EDPB 2025: Crypto-shredding guidelines
- NIST SP 800-57: Key Management
- FIPS 140-2/3: Cryptographic module requirements
"""

from __future__ import annotations

from canon.utils.kms.config import KMSConfig
from canon.utils.kms.enums import (
    ROLE_PERMISSIONS,
    EncryptionAlgorithm,
    KeyLifecycle,
    KeyType,
    Permission,
    Role,
    SecurityEventType,
    ShredStatus,
)
from canon.utils.kms.keys import (
    DataEncryptionKey,
    KeyDestructionCertificate,
    KeyEncryptionKey,
)
from canon.utils.kms.protocols import (
    AuditStorage,
    HSMProvider,
    KeyStorage,
    LitigationHoldService,
    ShredStorage,
)
from canon.utils.kms.service import AuditLogger, KeyManagementService

__all__ = [
    # Configuration
    "KMSConfig",
    # Enums
    "EncryptionAlgorithm",
    "KeyLifecycle",
    "KeyType",
    "Permission",
    "Role",
    "ROLE_PERMISSIONS",
    "SecurityEventType",
    "ShredStatus",
    # Key models
    "DataEncryptionKey",
    "KeyDestructionCertificate",
    "KeyEncryptionKey",
    # Protocols
    "AuditLogger",
    "AuditStorage",
    "HSMProvider",
    "KeyStorage",
    "LitigationHoldService",
    "ShredStorage",
    # Service
    "KeyManagementService",
]
