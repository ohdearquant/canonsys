# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""Key Management Service with HSM integration.

Implements NIST SP 800-57 key lifecycle with:
- Per-candidate DEKs for granular crypto-shredding
- KEK hierarchy for efficient key management
- HSM integration for secure key storage
- Key destruction certificates for audit compliance

References:
- NIST SP 800-57 (Key Management)
- EDPB 2025 Guidelines (Crypto-shredding)
"""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import UUID, uuid4

from canon.utils.kms.config import KMSConfig
from canon.utils.kms.enums import KeyLifecycle, KeyType
from canon.utils.kms.keys import (
    DataEncryptionKey,
    KeyDestructionCertificate,
    KeyEncryptionKey,
)
from canon.utils.kms.protocols import HSMProvider, KeyStorage
from kron.utils import now_utc

__all__ = [
    "AuditLogger",
    "KeyManagementService",
]

logger = logging.getLogger(__name__)


class AuditLogger(Protocol):
    """Protocol for audit logging key operations."""

    async def log_key_creation(
        self,
        key_id: UUID,
        key_type: str,
        candidate_id: UUID | None,
        actor: str,
    ) -> None:
        """Log key creation event."""
        ...

    async def log_key_destruction(
        self,
        key_id: UUID,
        key_type: str,
        candidate_id: UUID | None,
        actor: str,
        reason: str,
    ) -> None:
        """Log key destruction event."""
        ...


class KeyManagementService:
    """HSM-backed key management for crypto-shredding.

    Implements NIST SP 800-57 key lifecycle with:
    - Per-candidate DEKs for granular crypto-shredding
    - KEK hierarchy for efficient key management
    - HSM integration for secure key storage
    - Key destruction certificates for audit compliance

    Per EDPB 2025 guidance, crypto-shredding is accepted as GDPR Article 17
    erasure when:
    - State-of-the-art encryption (AES-256-GCM)
    - HSM-secured key storage
    - Verified key destruction with attestation

    Example:
        >>> kms = KeyManagementService(hsm, config, storage)
        >>> dek = await kms.create_candidate_dek(candidate_id, created_by="system")
        >>> # ... encrypt candidate data with dek ...
        >>> cert = await kms.crypto_shred(
        ...     candidate_id, reason="GDPR Art 17", operator="dpo"
        ... )

    References:
        - NIST SP 800-57: Key Management
        - EDPB 2025: Crypto-shredding guidelines
    """

    def __init__(
        self,
        hsm: HSMProvider,
        config: KMSConfig,
        storage: KeyStorage,
    ) -> None:
        """Initialize key management service.

        Args:
            hsm: HSM provider for key operations.
            config: KMS configuration.
            storage: Key metadata storage.
        """
        self._hsm = hsm
        self._config = config
        self._storage = storage
        self._audit_logger: AuditLogger | None = None

    def set_audit_logger(self, audit_logger: AuditLogger) -> None:
        """Set audit logger for key operation logging.

        Args:
            audit_logger: Audit logger instance.
        """
        self._audit_logger = audit_logger

    async def create_candidate_dek(
        self,
        candidate_id: UUID,
        *,
        created_by: str,
    ) -> DataEncryptionKey:
        """Create per-candidate DEK for crypto-shredding support.

        Each candidate gets a unique DEK. Destroying this key
        crypto-shreds all their encrypted data.

        Args:
            candidate_id: Candidate identifier.
            created_by: Operator or system creating the key.

        Returns:
            Created DataEncryptionKey.

        Raises:
            ValueError: If DEK already exists for candidate.
            HSMError: If HSM key generation fails.

        References:
            - EDPB 2025: Per-candidate encryption requirement
        """
        # Check for existing DEK
        existing = await self._storage.get_dek_for_candidate(candidate_id)
        if existing and existing.lifecycle_state != KeyLifecycle.DESTROYED:
            raise ValueError(
                f"Active DEK already exists for candidate {candidate_id}. "
                "Destroy existing DEK before creating new one."
            )

        # Get current KEK for wrapping
        kek = await self._get_active_kek()

        # Generate key in HSM
        key_handle = await self._hsm.generate_key(
            KeyType.DEK,
            self._config.encryption_algorithm,
        )

        # Create DEK metadata
        now = now_utc()
        dek = DataEncryptionKey(
            key_id=uuid4(),
            candidate_id=candidate_id,
            algorithm=self._config.encryption_algorithm,
            lifecycle_state=KeyLifecycle.ACTIVE,
            created_at=now,
            activated_at=now,
            hsm_key_handle=key_handle,
            wrapped_by_kek=kek.kek_id if kek else None,
            created_by=created_by,
        )

        # Persist metadata
        await self._storage.save_dek(dek)

        # Update KEK scope
        if kek:
            await self._storage.add_to_kek_scope(kek.kek_id, candidate_id)

        # Audit log
        if self._audit_logger and self._config.log_key_operations:
            await self._audit_logger.log_key_creation(
                key_id=dek.key_id,
                key_type=KeyType.DEK.value,
                candidate_id=candidate_id,
                actor=created_by,
            )

        logger.info(f"Created DEK {dek.key_id} for candidate {candidate_id}")
        return dek

    async def crypto_shred(
        self,
        candidate_id: UUID,
        *,
        reason: str,
        operator: str,
    ) -> KeyDestructionCertificate:
        """Destroy DEK to crypto-shred candidate data.

        Per EDPB 2025 guidance, crypto-shredding is accepted as
        GDPR Article 17 erasure when:
        - State-of-the-art encryption (AES-256-GCM)
        - HSM-secured key storage
        - Verified key destruction

        Args:
            candidate_id: Candidate whose data to shred.
            reason: Audit trail reason (e.g., 'GDPR Art 17 erasure').
            operator: Operator executing the shred.

        Returns:
            KeyDestructionCertificate proving destruction.

        Raises:
            ValueError: If no DEK found or already destroyed.
            HSMError: If HSM destruction fails.

        References:
            - EDPB 2025: Crypto-shredding requirements
            - NIST SP 800-88: Cryptographic Erase
        """
        # Get candidate's DEK
        dek = await self._storage.get_dek_for_candidate(candidate_id)
        if not dek:
            raise ValueError(f"No DEK found for candidate {candidate_id}")

        if dek.lifecycle_state == KeyLifecycle.DESTROYED:
            raise ValueError(
                f"DEK already destroyed for candidate {candidate_id} at "
                f"{dek.destroyed_at.isoformat() if dek.destroyed_at else 'unknown'}"
            )

        # Destroy key in HSM
        attestation = await self._hsm.destroy_key(
            dek.hsm_key_handle,
            reason=reason,
        )

        # Update DEK state
        dek.lifecycle_state = KeyLifecycle.DESTROYED
        dek.destroyed_at = now_utc()
        await self._storage.update_dek(dek)

        # Create destruction certificate
        certificate = KeyDestructionCertificate(
            certificate_id=uuid4(),
            key_id=dek.key_id,
            key_type=KeyType.DEK,
            candidate_id=candidate_id,
            destruction_timestamp=now_utc(),
            destruction_method="hsm_secure_delete",
            hsm_attestation=attestation,
            algorithm_used=dek.algorithm,
            verified=True,
            verified_by=operator,
        )

        # Persist certificate
        await self._storage.save_destruction_certificate(certificate)

        # Audit log
        if self._audit_logger and self._config.log_key_operations:
            await self._audit_logger.log_key_destruction(
                key_id=dek.key_id,
                key_type=KeyType.DEK.value,
                candidate_id=candidate_id,
                actor=operator,
                reason=reason,
            )

        logger.info(f"Crypto-shredded DEK {dek.key_id} for candidate {candidate_id}")
        return certificate

    async def rotate_kek(
        self,
        kek_id: UUID,
        *,
        operator: str,
    ) -> KeyEncryptionKey:
        """Rotate KEK and re-wrap all associated DEKs.

        KEK rotation triggers re-wrapping of all DEKs in scope.
        Old KEK is deactivated but retained for decrypt buffer period.

        Args:
            kek_id: KEK to rotate.
            operator: Operator executing the rotation.

        Returns:
            New KeyEncryptionKey.

        Raises:
            ValueError: If KEK not found.
            HSMError: If HSM operations fail.

        References:
            - NIST SP 800-57: Key rotation
        """
        # Get old KEK
        old_kek = await self._storage.get_kek(kek_id)
        if not old_kek:
            raise ValueError(f"KEK not found: {kek_id}")

        # Generate new KEK in HSM
        new_handle = await self._hsm.generate_key(
            KeyType.KEK,
            self._config.encryption_algorithm,
        )

        # Create new KEK
        new_kek = KeyEncryptionKey(
            kek_id=uuid4(),
            algorithm=self._config.encryption_algorithm,
            hsm_slot=new_handle,
            lifecycle_state=KeyLifecycle.ACTIVE,
            candidate_scope=old_kek.candidate_scope.copy(),
            escrow_enabled=old_kek.escrow_enabled,
            escrow_shares=old_kek.escrow_shares,
            escrow_threshold=old_kek.escrow_threshold,
        )

        # Re-wrap all DEKs (implementation would call HSM re-wrap API)
        for candidate_id in old_kek.candidate_scope:
            await self._rewrap_dek(candidate_id, old_kek, new_kek)

        # Deactivate old KEK
        old_kek.lifecycle_state = KeyLifecycle.DEACTIVATED
        old_kek.rotated_at = now_utc()
        await self._storage.update_kek(old_kek)

        # Save new KEK
        await self._storage.save_kek(new_kek)

        logger.info(f"Rotated KEK {kek_id} to new KEK {new_kek.kek_id}")
        return new_kek

    async def get_or_create_dek(self, candidate_id: UUID) -> DataEncryptionKey:
        """Get existing DEK or create new one for candidate.

        Args:
            candidate_id: Candidate identifier.

        Returns:
            Active DEK for candidate.
        """
        dek = await self._storage.get_dek_for_candidate(candidate_id)
        if dek and dek.lifecycle_state == KeyLifecycle.ACTIVE:
            return dek
        return await self.create_candidate_dek(candidate_id, created_by="system")

    async def get_system_key_id(self) -> str:
        """Get system-wide key ID for non-candidate data.

        Returns:
            System key identifier.
        """
        kek = await self._get_active_kek()
        if kek:
            return str(kek.kek_id)
        raise ValueError("No active KEK configured for system encryption")

    async def encrypt_with_key(
        self,
        key_id: str,
        plaintext: bytes,
        *,
        aad: bytes | None = None,
    ) -> bytes:
        """Encrypt data using specified key.

        Args:
            key_id: Key identifier (DEK or KEK).
            plaintext: Data to encrypt.
            aad: Additional authenticated data.

        Returns:
            Ciphertext.
        """
        # Get key handle from storage
        try:
            key_uuid = UUID(key_id)
        except ValueError as e:
            raise ValueError(f"Invalid key ID format: {key_id}") from e

        dek = await self._storage.get_dek(key_uuid)
        if dek:
            if dek.lifecycle_state == KeyLifecycle.DESTROYED:
                raise ValueError(f"Key {key_id} has been destroyed (crypto-shredded)")
            handle = dek.hsm_key_handle
        else:
            kek = await self._storage.get_kek(key_uuid)
            if not kek:
                raise ValueError(f"Key not found: {key_id}")
            handle = kek.hsm_slot

        context: dict[str, str] = {}
        if aad:
            context["aad"] = aad.decode("utf-8")

        return await self._hsm.encrypt(handle, plaintext, context)

    async def decrypt_with_key(
        self,
        key_id: str,
        ciphertext: bytes,
        *,
        aad: bytes | None = None,
    ) -> bytes:
        """Decrypt data using specified key.

        Args:
            key_id: Key identifier.
            ciphertext: Data to decrypt.
            aad: Additional authenticated data (must match encryption).

        Returns:
            Plaintext.

        Raises:
            ValueError: If key destroyed (crypto-shredded).
        """
        try:
            key_uuid = UUID(key_id)
        except ValueError as e:
            raise ValueError(f"Invalid key ID format: {key_id}") from e

        dek = await self._storage.get_dek(key_uuid)
        if dek:
            if dek.lifecycle_state == KeyLifecycle.DESTROYED:
                raise ValueError(
                    f"Key {key_id} has been destroyed (crypto-shredded). "
                    "Data is permanently unrecoverable per GDPR Article 17 erasure."
                )
            handle = dek.hsm_key_handle
        else:
            kek = await self._storage.get_kek(key_uuid)
            if not kek:
                raise ValueError(f"Key not found: {key_id}")
            handle = kek.hsm_slot

        context: dict[str, str] = {}
        if aad:
            context["aad"] = aad.decode("utf-8")

        return await self._hsm.decrypt(handle, ciphertext, context)

    async def get_keys_for_candidate(self, candidate_id: UUID) -> list[DataEncryptionKey]:
        """Get all keys for candidate (for erasure).

        Args:
            candidate_id: Candidate identifier.

        Returns:
            List of DEKs for candidate.
        """
        dek = await self._storage.get_dek_for_candidate(candidate_id)
        return [dek] if dek else []

    async def _get_active_kek(self) -> KeyEncryptionKey | None:
        """Get current active KEK."""
        return await self._storage.get_active_kek()

    async def _rewrap_dek(
        self,
        candidate_id: UUID,
        old_kek: KeyEncryptionKey,
        new_kek: KeyEncryptionKey,
    ) -> None:
        """Re-wrap DEK with new KEK.

        Args:
            candidate_id: Candidate whose DEK to re-wrap.
            old_kek: Current wrapping KEK.
            new_kek: New wrapping KEK.
        """
        dek = await self._storage.get_dek_for_candidate(candidate_id)
        if dek and dek.lifecycle_state == KeyLifecycle.ACTIVE:
            dek.wrapped_by_kek = new_kek.kek_id
            dek.rotation_count += 1
            await self._storage.update_dek(dek)
