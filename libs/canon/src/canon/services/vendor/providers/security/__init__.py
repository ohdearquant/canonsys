# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""HSM provider implementations.

Concrete implementations of the HSMProvider protocol for various backends:
- AWS KMS: Cloud-native HSM for AWS deployments
- HashiCorp Vault: On-premises/hybrid deployments
- Local: Development and testing only

Architecture (ADR-303):
    lib = protocols (HSMProvider, KeyStorage)
    backend = implementations (AWSKMSProvider, VaultProvider, LocalProvider)

Security References:
    - FIPS 140-2/3: HSM requirements
    - NIST SP 800-57: Key Management
    - FRE 902: Self-authenticating evidence
"""

from __future__ import annotations

from .aws_kms import AWSKMSProvider
from .local import LocalProvider
from .vault import VaultProvider

__all__ = [
    "AWSKMSProvider",
    "LocalProvider",
    "VaultProvider",
]
