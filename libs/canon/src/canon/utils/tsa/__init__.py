# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""RFC 3161 timestamp services for legal evidence chain.

Provides:
- External TSA integration (DigiCert, Entrust, etc.)
- Batch timestamping via Merkle trees
- Timestamp verification for FRE 902(13) self-authentication
- Certificate chain validation per RFC 3161

References:
- RFC 3161: Internet X.509 PKI Time-Stamp Protocol
- RFC 3628: Policy Requirements for Time-Stamping Authorities
- FRE 902(13): Self-authentication of electronic records
- eIDAS Article 41: Qualified electronic time stamps
"""

from __future__ import annotations

from kron.utils import HashAlgorithm

from .base import TimestampService
from .batch import BatchTimestampRequest, BatchTimestampResult, BatchTimestampService
from .config import TSA_PRESETS, TSAConfig
from .external_tsa import ExternalTSAService
from .merkle import MerkleProof, MerkleTree, verify_proof
from .types import TimestampRequest, TimestampToken, TimestampVerificationResult

__all__ = [
    # Batch timestamping
    "BatchTimestampRequest",
    "BatchTimestampResult",
    "BatchTimestampService",
    # External TSA client
    "ExternalTSAService",
    # Enums
    "HashAlgorithm",
    # Merkle tree components
    "MerkleProof",
    "MerkleTree",
    "verify_proof",
    # Configuration
    "TSA_PRESETS",
    "TSAConfig",
    # Core types
    "TimestampRequest",
    "TimestampService",
    "TimestampToken",
    "TimestampVerificationResult",
]
