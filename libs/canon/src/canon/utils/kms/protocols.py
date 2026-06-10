# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""KMS protocol interfaces (Dependency Inversion).

Defines protocol interfaces for HSM, storage, and service integrations.
Enables testing with mock implementations and supports multiple HSM providers.

References:
- FIPS 140-2/3: HSM requirements
- CNIL Security Guide 2024: Audit storage
- GDPR Article 17(3)(e): Litigation hold
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from canon.utils.kms.keys import (
        DataEncryptionKey,
        KeyDestructionCertificate,
        KeyEncryptionKey,
    )

from canon.utils.kms.enums import EncryptionAlgorithm, KeyType

__all__ = [
    "AuditStorage",
    "HSMProvider",
    "KeyStorage",
    "LitigationHoldService",
    "ShredStorage",
]


class HSMProvider(Protocol):
    """Protocol for HSM integration.

    Implementations provide hardware security module operations
    for key generation, destruction, and cryptographic operations.

    Supported implementations:
    - AWS KMS
    - Azure Key Vault
    - Google Cloud KMS
    - HashiCorp Vault Enterprise

    All methods are async to support HSM API latency.

    References:
        - FIPS 140-2/3: HSM requirements
    """

    async def generate_key(
        self,
        key_type: KeyType,
        algorithm: EncryptionAlgorithm,
    ) -> str:
        """Generate key in HSM.

        Args:
            key_type: Type of key to generate (DEK, KEK, etc.).
            algorithm: Encryption algorithm.

        Returns:
            HSM key handle/alias for the generated key.

        Raises:
            HSMError: If key generation fails.
        """
        ...

    async def destroy_key(
        self,
        key_handle: str,
        reason: str,
    ) -> str:
        """Destroy key in HSM (crypto-shredding).

        Per NIST SP 800-88, key material is cryptographically erased.
        Returns attestation proving destruction for audit purposes.

        Args:
            key_handle: HSM key handle to destroy.
            reason: Audit trail reason (e.g., 'GDPR Art 17 erasure').

        Returns:
            HSM attestation string proving destruction.

        Raises:
            HSMError: If destruction fails.
        """
        ...

    async def encrypt(
        self,
        key_handle: str,
        plaintext: bytes,
        context: dict[str, str],
    ) -> bytes:
        """Encrypt data using HSM-stored key.

        Uses authenticated encryption with additional data (AEAD).
        Context is bound as AAD for integrity verification.

        Args:
            key_handle: HSM key handle.
            plaintext: Data to encrypt.
            context: Encryption context (bound as AAD).

        Returns:
            Ciphertext including IV and auth tag.

        Raises:
            HSMError: If encryption fails.
        """
        ...

    async def decrypt(
        self,
        key_handle: str,
        ciphertext: bytes,
        context: dict[str, str],
    ) -> bytes:
        """Decrypt data using HSM-stored key.

        Verifies authentication tag and context binding.

        Args:
            key_handle: HSM key handle.
            ciphertext: Data to decrypt.
            context: Encryption context (must match encryption context).

        Returns:
            Decrypted plaintext.

        Raises:
            HSMError: If decryption or authentication fails.
            KeyDestroyedError: If key has been destroyed (crypto-shredded).
        """
        ...


class KeyStorage(Protocol):
    """Protocol for key metadata persistence.

    Stores key metadata (NOT key material). Key material
    remains exclusively in HSM per FIPS 140-2/3.

    References:
        - FIPS 140-2/3: Key storage requirements
    """

    async def save_dek(self, dek: DataEncryptionKey) -> None:
        """Persist DEK metadata.

        Args:
            dek: DEK to save.
        """
        ...

    async def update_dek(self, dek: DataEncryptionKey) -> None:
        """Update DEK metadata (e.g., lifecycle state change).

        Args:
            dek: Updated DEK.
        """
        ...

    async def get_dek(self, key_id: UUID) -> DataEncryptionKey | None:
        """Get DEK by key ID.

        Args:
            key_id: Key identifier.

        Returns:
            DEK if found, None otherwise.
        """
        ...

    async def get_dek_for_candidate(self, candidate_id: UUID) -> DataEncryptionKey | None:
        """Get active DEK for candidate.

        Args:
            candidate_id: Candidate identifier.

        Returns:
            Active DEK if found, None otherwise.
        """
        ...

    async def save_kek(self, kek: KeyEncryptionKey) -> None:
        """Persist KEK metadata.

        Args:
            kek: KEK to save.
        """
        ...

    async def update_kek(self, kek: KeyEncryptionKey) -> None:
        """Update KEK metadata.

        Args:
            kek: Updated KEK.
        """
        ...

    async def get_kek(self, kek_id: UUID) -> KeyEncryptionKey | None:
        """Get KEK by ID.

        Args:
            kek_id: KEK identifier.

        Returns:
            KEK if found, None otherwise.
        """
        ...

    async def get_active_kek(self) -> KeyEncryptionKey | None:
        """Get current active KEK.

        Returns:
            Active KEK, None if none configured.
        """
        ...

    async def add_to_kek_scope(self, kek_id: UUID, candidate_id: UUID) -> None:
        """Add candidate to KEK scope.

        Args:
            kek_id: KEK identifier.
            candidate_id: Candidate to add to scope.
        """
        ...

    async def save_destruction_certificate(self, certificate: KeyDestructionCertificate) -> None:
        """Persist destruction certificate.

        Args:
            certificate: Certificate to save.
        """
        ...


class AuditStorage(Protocol):
    """Protocol for security audit log persistence.

    Implements append-only storage for tamper-evident audit trail.

    References:
        - CNIL Security Guide 2024
    """

    async def append(self, entry: Any) -> None:
        """Append entry to audit log (append-only).

        Args:
            entry: Audit entry to append.
        """
        ...

    async def get_last_entry(self) -> Any | None:
        """Get most recent audit entry for hash chaining.

        Returns:
            Last entry, None if log is empty.
        """
        ...

    async def get_entries_range(
        self,
        start_entry: UUID | None,
        end_entry: UUID | None,
    ) -> list[Any]:
        """Get entries in range for chain verification.

        Args:
            start_entry: Starting entry ID (inclusive). None for beginning.
            end_entry: Ending entry ID (inclusive). None for end.

        Returns:
            List of entries in order.
        """
        ...


class LitigationHoldService(Protocol):
    """Protocol for litigation hold checking.

    Per GDPR Article 17(3)(e), erasure can be refused when data
    is required for legal claims defense.

    References:
        - GDPR Article 17(3)(e)
    """

    async def is_deletion_blocked(
        self,
        candidate_id: UUID,
        as_of_date: date,
    ) -> tuple[bool, list[Any]]:
        """Check if deletion is blocked by litigation hold.

        Args:
            candidate_id: Candidate to check.
            as_of_date: Date to check against hold period.

        Returns:
            Tuple of (is_blocked, list_of_blocking_holds).
        """
        ...


class ShredStorage(Protocol):
    """Protocol for crypto-shredding persistence."""

    async def get_active_backup_sets(self) -> list[str]:
        """Get list of active backup sets."""
        ...

    async def save_erasure_marker(self, marker: Any) -> None:
        """Save erasure marker for backup reconciliation."""
        ...

    async def get_markers_after(self, timestamp: datetime) -> list[Any]:
        """Get erasure markers created after timestamp."""
        ...

    async def update_marker(self, marker: Any) -> None:
        """Update erasure marker."""
        ...
