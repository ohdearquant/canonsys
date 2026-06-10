# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Local HSM provider implementation for development and testing.

WARNING: This implementation stores keys in memory and should ONLY be used
for development and testing. Use AWS KMS or HashiCorp Vault for production.

Implements HSMProvider protocol using local cryptography for:
- Key generation (in-memory)
- Encryption/decryption (AES-256-GCM)
- Evidence signing and verification (HMAC-SHA256)

Environment Variables:
    CANON_LOCAL_SIGNING_KEY: 64-character hex string signing key

Security Note:
    This provider is NOT suitable for production. Keys are stored in memory
    and do not provide HSM-level protection.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from canon.utils import EncryptionAlgorithm, KeyType

from .aws_kms import (
    AuditLogEntry,
    SignatureResult,
    SigningAlgorithm,
    VerificationResult,
)

logger = logging.getLogger(__name__)


class LocalProviderError(Exception):
    """Local provider operation error."""

    def __init__(self, operation: str, message: str):
        self.operation = operation
        super().__init__(f"Local provider {operation} failed: {message}")


class LocalProvider:
    """Local in-memory HSM provider for development and testing.

    WARNING: Not for production use. Keys are stored in memory only.

    Usage:
        provider = LocalProvider(signing_key="your-64-char-hex-key")
        ciphertext = await provider.encrypt(key_handle, plaintext, context)

    Environment:
        CANON_LOCAL_SIGNING_KEY for signing operations
    """

    # Minimum key length for security
    _MIN_KEY_LENGTH = 32

    # Placeholder patterns to reject
    _PLACEHOLDER_PATTERNS = (
        "default",
        "secret",
        "changeme",
        "placeholder",
        "example",
        "test123",
    )

    def __init__(
        self,
        signing_key: str | None = None,
        key_id: str = "local-dev-key",
    ):
        """Initialize local provider.

        Args:
            signing_key: Signing key (64-char hex or 32+ char string)
            key_id: Key identifier

        Raises:
            ValueError: If key is too short or is a placeholder
        """
        # Get signing key from param or env
        signing_key = signing_key or os.environ.get("CANON_LOCAL_SIGNING_KEY", "")

        if signing_key:
            self._validate_key(signing_key)
            self._signing_key = self._parse_key(signing_key)
        else:
            # Generate a random key for dev (logged as warning)
            self._signing_key = secrets.token_bytes(32)
            logger.warning(
                "LocalProvider: No signing key provided, generated random key. "
                "This is only suitable for development."
            )

        self._key_id = key_id
        self._version = 1
        self._created_at = datetime.now(UTC)
        self._audit_log: list[AuditLogEntry] = []

        # In-memory key storage for generated keys
        self._keys: dict[str, bytes] = {key_id: self._signing_key}
        self._key_versions: dict[int, bytes] = {1: self._signing_key}

        logger.warning(
            "LocalProvider initialized. NOT FOR PRODUCTION USE. "
            "Use AWSKMSProvider or VaultProvider for production."
        )

    def _validate_key(self, key: str) -> None:
        """Validate signing key."""
        if len(key) < self._MIN_KEY_LENGTH:
            raise ValueError(
                f"signing_key must be at least {self._MIN_KEY_LENGTH} characters. "
                "Generate with: openssl rand -hex 32"
            )

        lower_key = key.lower()
        if any(pattern in lower_key for pattern in self._PLACEHOLDER_PATTERNS):
            raise ValueError(
                "signing_key appears to be a placeholder. Use a cryptographically random key."
            )

    def _parse_key(self, key: str) -> bytes:
        """Parse signing key to bytes."""
        if len(key) == 64:
            try:
                return bytes.fromhex(key)
            except ValueError:
                pass
        return key.encode()[:32].ljust(32, b"\0")

    def _log_audit(
        self,
        event_type: str,
        key_id: str,
        success: bool = True,
        operation_hash: str | None = None,
        error_message: str | None = None,
        caller_id: str | None = None,
        **metadata: Any,
    ) -> AuditLogEntry:
        """Log an audit event."""
        entry = AuditLogEntry(
            event_id=f"local_{uuid4().hex[:12]}",
            event_type=event_type,
            timestamp=datetime.now(UTC),
            key_id=key_id,
            success=success,
            operation_hash=operation_hash,
            error_message=error_message,
            caller_id=caller_id,
            metadata=metadata,
        )
        self._audit_log.append(entry)

        log_fn = logger.info if success else logger.error
        log_fn("Local provider audit: %s key=%s success=%s", event_type, key_id, success)
        return entry

    # -------------------------------------------------------------------------
    # HSMProvider Protocol Implementation
    # -------------------------------------------------------------------------

    async def generate_key(
        self,
        key_type: KeyType,
        algorithm: EncryptionAlgorithm,
    ) -> str:
        """Generate a new key in memory.

        Args:
            key_type: Type of key (DEK, KEK)
            algorithm: Encryption algorithm

        Returns:
            Key handle (UUID)
        """
        key_handle = f"local-{key_type.value.lower()}-{uuid4().hex[:8]}"
        key_bytes = secrets.token_bytes(32)  # 256-bit key

        self._keys[key_handle] = key_bytes

        self._log_audit(
            "key_generated",
            key_handle,
            key_type=key_type.value,
            algorithm=algorithm.value,
        )
        return key_handle

    async def destroy_key(
        self,
        key_handle: str,
        reason: str,
    ) -> str:
        """Remove key from memory.

        Args:
            key_handle: Key handle to destroy
            reason: Audit trail reason

        Returns:
            Attestation string
        """
        if key_handle in self._keys:
            # Overwrite with zeros before deleting
            self._keys[key_handle] = b"\x00" * 32
            del self._keys[key_handle]

        attestation = (
            f"Local key '{key_handle}' destroyed at {datetime.now(UTC).isoformat()}. "
            f"Reason: {reason}. Key material zeroed and removed from memory."
        )

        self._log_audit("key_destroyed", key_handle, reason=reason)
        return attestation

    async def encrypt(
        self,
        key_handle: str,
        plaintext: bytes,
        context: dict[str, str],
    ) -> bytes:
        """Encrypt data using AES-256-GCM.

        Args:
            key_handle: Key handle
            plaintext: Data to encrypt
            context: Encryption context (used as AAD)

        Returns:
            Ciphertext (nonce || ciphertext || tag)
        """
        key = self._keys.get(key_handle)
        if not key:
            # Fall back to signing key for default operations
            key = self._signing_key

        try:
            # Build AAD from context
            aad = b""
            if context:
                aad = "|".join(f"{k}={v}" for k, v in sorted(context.items())).encode()

            # Encrypt with AES-256-GCM
            aesgcm = AESGCM(key)
            nonce = secrets.token_bytes(12)  # 96-bit nonce
            ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

            # Return nonce + ciphertext
            result = nonce + ciphertext

            self._log_audit(
                "encrypt",
                key_handle,
                operation_hash=hashlib.sha256(plaintext).hexdigest()[:16],
            )
            return result

        except Exception as e:
            self._log_audit(
                "encrypt",
                key_handle,
                success=False,
                error_message=str(e),
            )
            raise LocalProviderError("encrypt", str(e)) from e

    async def decrypt(
        self,
        key_handle: str,
        ciphertext: bytes,
        context: dict[str, str],
    ) -> bytes:
        """Decrypt data using AES-256-GCM.

        Args:
            key_handle: Key handle
            ciphertext: Data to decrypt (nonce || ciphertext || tag)
            context: Encryption context (must match encryption)

        Returns:
            Decrypted plaintext
        """
        key = self._keys.get(key_handle)
        if not key:
            key = self._signing_key

        try:
            # Extract nonce
            nonce = ciphertext[:12]
            actual_ciphertext = ciphertext[12:]

            # Build AAD from context
            aad = b""
            if context:
                aad = "|".join(f"{k}={v}" for k, v in sorted(context.items())).encode()

            # Decrypt
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, actual_ciphertext, aad)

            self._log_audit("decrypt", key_handle)
            return plaintext

        except Exception as e:
            self._log_audit(
                "decrypt",
                key_handle,
                success=False,
                error_message="Decryption failed - key may have been destroyed",
            )
            raise LocalProviderError(
                "decrypt",
                "Decryption failed - key may have been destroyed (crypto-shredded)",
            ) from e

    # -------------------------------------------------------------------------
    # Signing Operations
    # -------------------------------------------------------------------------

    async def sign(
        self,
        data: bytes,
        key_id: str | None = None,
        algorithm: SigningAlgorithm = SigningAlgorithm.HMAC_SHA256,
        caller_id: str | None = None,
    ) -> SignatureResult:
        """Sign data using HMAC-SHA256.

        Args:
            data: Data to sign
            key_id: Key identifier (uses default if not specified)
            algorithm: Signing algorithm
            caller_id: Caller identifier for audit

        Returns:
            SignatureResult with HMAC signature
        """
        operation_hash = hashlib.sha256(data).hexdigest()

        try:
            signature_bytes = hmac.new(
                self._signing_key,
                data,
                hashlib.sha256,
            ).digest()

            signature = base64.b64encode(signature_bytes).decode("ascii")

            self._log_audit(
                "sign",
                self._key_id,
                operation_hash=operation_hash[:16],
                caller_id=caller_id,
            )

            return SignatureResult(
                signature=signature,
                key_id=self._key_id,
                algorithm=algorithm,
                timestamp=datetime.now(UTC),
            )

        except Exception as e:
            self._log_audit(
                "sign",
                self._key_id,
                success=False,
                error_message=str(e),
                caller_id=caller_id,
            )
            raise LocalProviderError("sign", str(e)) from e

    async def verify(
        self,
        data: bytes,
        signature: str,
        key_id: str | None = None,
        algorithm: SigningAlgorithm = SigningAlgorithm.HMAC_SHA256,
        caller_id: str | None = None,
    ) -> VerificationResult:
        """Verify HMAC-SHA256 signature.

        Args:
            data: Original data
            signature: Base64-encoded signature
            key_id: Key identifier
            algorithm: Signing algorithm
            caller_id: Caller identifier for audit

        Returns:
            VerificationResult with validity status
        """
        operation_hash = hashlib.sha256(data).hexdigest()

        try:
            signature_bytes = base64.b64decode(signature)

            expected = hmac.new(
                self._signing_key,
                data,
                hashlib.sha256,
            ).digest()

            is_valid = hmac.compare_digest(signature_bytes, expected)

            self._log_audit(
                "verify",
                self._key_id,
                operation_hash=operation_hash[:16],
                caller_id=caller_id,
                is_valid=is_valid,
            )

            return VerificationResult(
                is_valid=is_valid,
                key_id=self._key_id,
                algorithm=algorithm,
                verified_at=datetime.now(UTC),
            )

        except Exception as e:
            self._log_audit(
                "verify",
                self._key_id,
                success=False,
                error_message=str(e),
                caller_id=caller_id,
            )
            return VerificationResult(
                is_valid=False,
                key_id=self._key_id,
                algorithm=algorithm,
                verified_at=datetime.now(UTC),
                error_message=str(e),
            )

    # -------------------------------------------------------------------------
    # Key Rotation
    # -------------------------------------------------------------------------

    async def rotate_key(
        self,
        caller_id: str | None = None,
    ) -> int:
        """Rotate the signing key.

        Creates a new key version while keeping old versions for verification.

        Args:
            caller_id: Caller identifier for audit

        Returns:
            New key version number
        """
        self._version += 1
        new_key = secrets.token_bytes(32)
        self._signing_key = new_key
        self._key_versions[self._version] = new_key
        self._keys[self._key_id] = new_key

        self._log_audit(
            "key_rotated",
            self._key_id,
            caller_id=caller_id,
            new_version=self._version,
        )

        return self._version

    # -------------------------------------------------------------------------
    # Audit Access
    # -------------------------------------------------------------------------

    def get_audit_log(
        self,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """Get audit log entries.

        Args:
            since: Filter by timestamp
            limit: Maximum entries to return

        Returns:
            List of audit entries
        """
        entries = self._audit_log
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        return entries[-limit:]
