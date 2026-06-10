# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""Key models for HSM-backed key management.

References:
- NIST SP 800-57 (Key Management)
- EDPB 2025 Guidelines (Crypto-shredding)
- FIPS 140-2/3 (Key storage requirements)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from canon.utils.kms.enums import EncryptionAlgorithm, KeyLifecycle, KeyType
from kron.utils import now_utc

__all__ = [
    "DataEncryptionKey",
    "KeyDestructionCertificate",
    "KeyEncryptionKey",
]


@dataclass
class DataEncryptionKey:
    """Per-candidate Data Encryption Key (DEK).

    Each candidate has a unique DEK for their personal data.
    Destroying this key = crypto-shredding the candidate's data,
    rendering all encrypted evidence permanently unreadable.

    Per EDPB 2025 guidance, this approach satisfies GDPR Article 17
    when combined with HSM-secured key storage and verified destruction.

    Attributes:
        key_id: Unique key identifier (UUID).
        candidate_id: Associated candidate (1:1 mapping).
        algorithm: Encryption algorithm used.
        lifecycle_state: Current key state per NIST SP 800-57.
        created_at: Key generation timestamp.
        activated_at: When key became active.
        rotated_at: Last rotation timestamp.
        destroyed_at: Destruction timestamp (crypto-shredding).
        hsm_key_handle: Reference to key material in HSM.
        wrapped_by_kek: Parent KEK that wraps this DEK.
        created_by: Operator who created the key.
        rotation_count: Number of rotations performed.

    References:
        - NIST SP 800-57: Key Management
        - EDPB 2025: Crypto-shredding guidelines
    """

    key_id: UUID
    """Unique key identifier."""

    candidate_id: UUID
    """Associated candidate. One DEK per candidate."""

    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    """Encryption algorithm. AES-256-GCM default."""

    lifecycle_state: KeyLifecycle = KeyLifecycle.ACTIVE
    """Current state per NIST SP 800-57."""

    created_at: datetime = field(default_factory=now_utc)
    """Key generation timestamp."""

    activated_at: datetime | None = None
    """When key became active for encryption."""

    rotated_at: datetime | None = None
    """Last rotation timestamp."""

    destroyed_at: datetime | None = None
    """Destruction timestamp. Set on crypto-shred."""

    hsm_key_handle: str = ""
    """Reference to key material in HSM. Never expose raw key."""

    wrapped_by_kek: UUID | None = None
    """Parent KEK that wraps this DEK."""

    created_by: str = ""
    """Operator or system that created the key."""

    rotation_count: int = 0
    """Number of rotations performed."""


@dataclass
class KeyEncryptionKey:
    """Key Encryption Key (KEK) stored in HSM.

    KEKs wrap (encrypt) DEKs in the key hierarchy.
    A single KEK may wrap multiple DEKs for efficiency.
    KEK rotation triggers re-wrapping of all associated DEKs.

    Per FIPS 140-2/3, KEKs MUST remain in HSM boundary.
    Only encrypted DEKs leave the HSM.

    Attributes:
        kek_id: Unique KEK identifier.
        algorithm: Encryption algorithm.
        hsm_slot: HSM slot/alias containing the key.
        lifecycle_state: Current key state.
        created_at: Key generation timestamp.
        rotated_at: Last rotation timestamp.
        candidate_scope: List of candidate IDs whose DEKs are wrapped.
        escrow_enabled: Whether key escrow is enabled for this KEK.
        escrow_shares: Number of escrow shares created.
        escrow_threshold: M-of-N threshold for recovery.

    References:
        - FIPS 140-2/3: Key wrapping requirements
        - NIST SP 800-57: Key hierarchy
    """

    kek_id: UUID
    """Unique KEK identifier."""

    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    """Encryption algorithm. AES-256-GCM default."""

    hsm_slot: str = ""
    """HSM slot/alias. E.g., 'alias/canonsys-kek-2025'."""

    lifecycle_state: KeyLifecycle = KeyLifecycle.ACTIVE
    """Current state per NIST SP 800-57."""

    created_at: datetime = field(default_factory=now_utc)
    """Key generation timestamp."""

    rotated_at: datetime | None = None
    """Last rotation timestamp. None if never rotated."""

    candidate_scope: list[UUID] = field(default_factory=list)
    """Candidate IDs whose DEKs are wrapped by this KEK."""

    escrow_enabled: bool = False
    """Whether key escrow is enabled for litigation hold."""

    escrow_shares: int = 0
    """Number of escrow shares created (N in M-of-N)."""

    escrow_threshold: int = 0
    """Recovery threshold (M in M-of-N)."""


@dataclass(frozen=True)
class KeyDestructionCertificate:
    """Proof of key destruction for compliance audits.

    Per EDPB 2025 guidance, key destruction must be:
    - Verifiable via HSM attestation
    - Timestamped for audit trail
    - Logged for DPA inspection

    This certificate provides cryptographic proof that a key
    has been irreversibly destroyed, satisfying GDPR Article 17
    erasure requirements through crypto-shredding.

    Attributes:
        certificate_id: Unique certificate identifier.
        key_id: Destroyed key identifier.
        key_type: Type of key destroyed (DEK, KEK, etc.).
        candidate_id: Associated candidate (for DEKs).
        destruction_timestamp: When destruction occurred.
        destruction_method: How key was destroyed (hsm_secure_delete).
        hsm_attestation: Cryptographic attestation from HSM.
        algorithm_used: Algorithm of destroyed key.
        verified: Whether destruction was verified.
        verified_by: Operator who verified destruction.

    References:
        - EDPB 2025: Crypto-shredding requirements
        - NIST SP 800-88: Cryptographic Erase verification
    """

    certificate_id: UUID
    """Unique certificate identifier."""

    key_id: UUID
    """Destroyed key identifier."""

    key_type: KeyType
    """Type of key destroyed."""

    candidate_id: UUID | None
    """Associated candidate (for DEKs). None for KEKs."""

    destruction_timestamp: datetime
    """When destruction occurred (UTC)."""

    destruction_method: str
    """Destruction method. E.g., 'hsm_secure_delete'."""

    hsm_attestation: str
    """Cryptographic attestation from HSM proving destruction."""

    algorithm_used: EncryptionAlgorithm
    """Algorithm of the destroyed key."""

    verified: bool
    """Whether destruction was verified by second operator."""

    verified_by: str | None = None
    """Operator who verified destruction (dual authorization)."""
