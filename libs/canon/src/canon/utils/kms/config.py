# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""KMS configuration.

References:
- NIST SP 800-57 (Key Management)
- FIPS 140-2/3 (Cryptographic Modules)
"""

from __future__ import annotations

from dataclasses import dataclass

from canon.utils.kms.enums import EncryptionAlgorithm

__all__ = [
    "KMSConfig",
]


@dataclass
class KMSConfig:
    """Key Management Service configuration.

    Attributes:
        encryption_algorithm: Default encryption algorithm.
        log_key_operations: Whether to audit log key operations.
        require_dual_auth_for_destroy: Require dual authorization for key destruction.
        kek_rotation_days: Days before KEK rotation is recommended.
        dek_max_encryptions: Max encryptions per DEK before rotation.
    """

    encryption_algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    """Default encryption algorithm. AES-256-GCM per FIPS 140-2/3."""

    log_key_operations: bool = True
    """Audit log all key operations. Required for CNIL compliance."""

    require_dual_auth_for_destroy: bool = True
    """Require second operator for key destruction. NIST SP 800-57."""

    kek_rotation_days: int = 365
    """Days before KEK rotation is recommended."""

    dek_max_encryptions: int = 1_000_000
    """Maximum encryptions per DEK before rotation recommended."""

    hsm_provider: str = "aws_kms"
    """HSM provider: aws_kms, azure_keyvault, gcp_kms, hashicorp_vault."""

    hsm_region: str = "us-east-1"
    """HSM provider region."""

    hsm_key_alias_prefix: str = "alias/canonsys"
    """Prefix for HSM key aliases."""
