# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""HashiCorp Vault HSM provider implementation.

Implements HSMProvider protocol using Vault Transit secrets engine for:
- Key generation and management
- Key destruction (crypto-shredding)
- Encryption/decryption operations
- Evidence signing and verification (FRE 902)

Environment Variables:
    CANON_VAULT_ADDR: Vault server address
    CANON_VAULT_TOKEN: Vault authentication token
    CANON_VAULT_NAMESPACE: Vault namespace (optional, enterprise)
    CANON_VAULT_MOUNT_POINT: Transit mount point (default: transit)

Security References:
    - FIPS 140-2 Level 3: Vault Enterprise with HSM seal
    - NIST SP 800-57: Key Management
    - CWE-347: Cryptographic signature verification
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from canon.utils import EncryptionAlgorithm, KeyType

from .aws_kms import (
    AuditLogEntry,
    SignatureResult,
    SigningAlgorithm,
    VerificationResult,
)

logger = logging.getLogger(__name__)


class VaultError(Exception):
    """HashiCorp Vault operation error."""

    def __init__(self, operation: str, message: str):
        self.operation = operation
        super().__init__(f"Vault {operation} failed: {message}")


class VaultProvider:
    """HashiCorp Vault implementation of HSMProvider protocol.

    Uses Vault Transit secrets engine for HSM-backed operations.
    Supports on-premises and hybrid deployments.

    Usage:
        provider = VaultProvider(
            vault_addr="https://vault.example.com:8200",
            token="s.xxxxxxxx",
            key_name="canonsys-evidence"
        )
        ciphertext = await provider.encrypt(key_handle, plaintext, context)

    Environment:
        CANON_VAULT_ADDR, CANON_VAULT_TOKEN for credentials
        Or use Vault agent injection in Kubernetes
    """

    def __init__(
        self,
        vault_addr: str | None = None,
        token: str | None = None,
        key_name: str = "canonsys-evidence",
        mount_point: str = "transit",
        namespace: str | None = None,
    ):
        """Initialize Vault provider.

        Args:
            vault_addr: Vault server address
            token: Vault authentication token
            key_name: Transit key name
            mount_point: Transit secrets engine mount point
            namespace: Vault namespace (enterprise only)
        """
        self._vault_addr = (vault_addr or os.environ.get("CANON_VAULT_ADDR", "")).rstrip("/")
        self._token = token or os.environ.get("CANON_VAULT_TOKEN", "")
        self._key_name = key_name
        self._mount_point = mount_point or os.environ.get("CANON_VAULT_MOUNT_POINT", "transit")
        self._namespace = namespace or os.environ.get("CANON_VAULT_NAMESPACE")
        self._client: Any = None
        self._audit_log: list[AuditLogEntry] = []

    async def _get_client(self) -> Any:
        """Get or create hvac client.

        Returns:
            hvac Vault client.

        Raises:
            VaultError: If hvac is not available or auth fails.
        """
        if self._client is None:
            try:
                import hvac
            except ImportError as err:
                raise VaultError(
                    "initialization",
                    "hvac package required. Install with: pip install hvac",
                ) from err

            self._client = hvac.Client(
                url=self._vault_addr,
                token=self._token,
                namespace=self._namespace,
            )

            if not self._client.is_authenticated():
                raise VaultError("authentication", "Failed to authenticate with Vault")

        return self._client

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
            event_id=f"vault_{uuid4().hex[:12]}",
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
        log_fn("Vault audit: %s key=%s success=%s", event_type, key_id, success)
        return entry

    # -------------------------------------------------------------------------
    # HSMProvider Protocol Implementation
    # -------------------------------------------------------------------------

    async def generate_key(
        self,
        key_type: KeyType,
        algorithm: EncryptionAlgorithm,
    ) -> str:
        """Create a new key in Vault Transit.

        Args:
            key_type: Type of key (DEK, KEK)
            algorithm: Encryption algorithm

        Returns:
            Key name/path in Vault
        """
        client = await self._get_client()

        # Map to Vault key type
        vault_key_type = "aes256-gcm96"  # Default for encryption
        if key_type == KeyType.KEK:
            vault_key_type = "aes256-gcm96"

        key_name = f"{self._key_name}-{key_type.value.lower()}-{uuid4().hex[:8]}"

        try:
            client.secrets.transit.create_key(
                name=key_name,
                key_type=vault_key_type,
                mount_point=self._mount_point,
            )

            self._log_audit(
                "key_generated",
                key_name,
                key_type=key_type.value,
                vault_key_type=vault_key_type,
            )
            return key_name

        except Exception as e:
            self._log_audit(
                "key_generated",
                key_name,
                success=False,
                error_message=str(e),
            )
            raise VaultError("generate_key", str(e)) from e

    async def destroy_key(
        self,
        key_handle: str,
        reason: str,
    ) -> str:
        """Delete key from Vault Transit.

        Per NIST SP 800-88, key material is cryptographically erased.

        Args:
            key_handle: Key name in Vault
            reason: Audit trail reason

        Returns:
            Attestation string proving destruction
        """
        client = await self._get_client()

        try:
            # First, update deletion_allowed config
            client.secrets.transit.update_key_configuration(
                name=key_handle,
                deletion_allowed=True,
                mount_point=self._mount_point,
            )

            # Then delete the key
            client.secrets.transit.delete_key(
                name=key_handle,
                mount_point=self._mount_point,
            )

            attestation = (
                f"Vault Transit key '{key_handle}' deleted at "
                f"{datetime.now(UTC).isoformat()}. Reason: {reason}. "
                "Key material cryptographically erased per NIST SP 800-88."
            )

            self._log_audit("key_destroyed", key_handle, reason=reason)
            return attestation

        except Exception as e:
            self._log_audit(
                "key_destroyed",
                key_handle,
                success=False,
                error_message=str(e),
            )
            raise VaultError("destroy_key", str(e)) from e

    async def encrypt(
        self,
        key_handle: str,
        plaintext: bytes,
        context: dict[str, str],
    ) -> bytes:
        """Encrypt data using Vault Transit.

        Uses convergent encryption with context as additional data.

        Args:
            key_handle: Key name in Vault
            plaintext: Data to encrypt
            context: Encryption context

        Returns:
            Ciphertext (Vault format: vault:v1:base64)
        """
        client = await self._get_client()

        try:
            # Encode for Vault
            b64_plaintext = base64.b64encode(plaintext).decode("ascii")

            # Context for convergent encryption
            b64_context = None
            if context:
                context_str = "|".join(f"{k}={v}" for k, v in sorted(context.items()))
                b64_context = base64.b64encode(context_str.encode()).decode("ascii")

            response = client.secrets.transit.encrypt_data(
                name=key_handle or self._key_name,
                plaintext=b64_plaintext,
                context=b64_context,
                mount_point=self._mount_point,
            )

            ciphertext = response["data"]["ciphertext"]

            self._log_audit(
                "encrypt",
                key_handle or self._key_name,
                operation_hash=hashlib.sha256(plaintext).hexdigest()[:16],
            )

            return ciphertext.encode("utf-8")

        except Exception as e:
            self._log_audit(
                "encrypt",
                key_handle or self._key_name,
                success=False,
                error_message=str(e),
            )
            raise VaultError("encrypt", str(e)) from e

    async def decrypt(
        self,
        key_handle: str,
        ciphertext: bytes,
        context: dict[str, str],
    ) -> bytes:
        """Decrypt data using Vault Transit.

        Args:
            key_handle: Key name in Vault
            ciphertext: Data to decrypt (Vault format)
            context: Encryption context (must match encryption)

        Returns:
            Decrypted plaintext
        """
        client = await self._get_client()

        try:
            # Context for convergent encryption
            b64_context = None
            if context:
                context_str = "|".join(f"{k}={v}" for k, v in sorted(context.items()))
                b64_context = base64.b64encode(context_str.encode()).decode("ascii")

            response = client.secrets.transit.decrypt_data(
                name=key_handle or self._key_name,
                ciphertext=ciphertext.decode("utf-8"),
                context=b64_context,
                mount_point=self._mount_point,
            )

            plaintext = base64.b64decode(response["data"]["plaintext"])

            self._log_audit("decrypt", key_handle or self._key_name)
            return plaintext

        except Exception as e:
            error_msg = str(e).lower()
            if "invalid" in error_msg or "decrypt" in error_msg:
                self._log_audit(
                    "decrypt",
                    key_handle or self._key_name,
                    success=False,
                    error_message="Key destroyed or context mismatch",
                )
                raise VaultError(
                    "decrypt",
                    "Decryption failed - key may have been destroyed (crypto-shredded)",
                ) from e

            self._log_audit(
                "decrypt",
                key_handle or self._key_name,
                success=False,
                error_message=str(e),
            )
            raise VaultError("decrypt", str(e)) from e

    # -------------------------------------------------------------------------
    # Signing Operations (FRE 902)
    # -------------------------------------------------------------------------

    async def sign(
        self,
        data: bytes,
        key_id: str | None = None,
        algorithm: SigningAlgorithm = SigningAlgorithm.HMAC_SHA256,
        caller_id: str | None = None,
    ) -> SignatureResult:
        """Sign data for FRE 902 evidence authentication.

        Args:
            data: Data to sign
            key_id: Signing key name (default: configured key)
            algorithm: Signing algorithm (Vault uses key config)
            caller_id: Caller identifier for audit

        Returns:
            SignatureResult with signature
        """
        client = await self._get_client()
        key_name = key_id or self._key_name
        operation_hash = hashlib.sha256(data).hexdigest()

        try:
            b64_data = base64.b64encode(data).decode("ascii")

            response = client.secrets.transit.sign_data(
                name=key_name,
                hash_input=b64_data,
                hash_algorithm="sha2-256",
                prehashed=False,
                mount_point=self._mount_point,
            )

            # Parse Vault signature format: vault:v1:base64signature
            vault_signature = response["data"]["signature"]
            parts = vault_signature.split(":")
            signature = parts[-1] if len(parts) >= 3 else vault_signature

            self._log_audit(
                "sign",
                key_name,
                operation_hash=operation_hash[:16],
                caller_id=caller_id,
            )

            return SignatureResult(
                signature=signature,
                key_id=key_name,
                algorithm=algorithm,
                timestamp=datetime.now(UTC),
            )

        except Exception as e:
            self._log_audit(
                "sign",
                key_name,
                success=False,
                error_message=str(e),
                caller_id=caller_id,
            )
            raise VaultError("sign", str(e)) from e

    async def verify(
        self,
        data: bytes,
        signature: str,
        key_id: str | None = None,
        algorithm: SigningAlgorithm = SigningAlgorithm.HMAC_SHA256,
        caller_id: str | None = None,
    ) -> VerificationResult:
        """Verify signature for evidence authentication.

        Args:
            data: Original data
            signature: Signature to verify
            key_id: Signing key name
            algorithm: Signing algorithm
            caller_id: Caller identifier for audit

        Returns:
            VerificationResult with validity status
        """
        client = await self._get_client()
        key_name = key_id or self._key_name
        operation_hash = hashlib.sha256(data).hexdigest()

        try:
            b64_data = base64.b64encode(data).decode("ascii")

            # Reconstruct Vault signature format if needed
            if not signature.startswith("vault:"):
                signature = f"vault:v1:{signature}"

            response = client.secrets.transit.verify_signed_data(
                name=key_name,
                hash_input=b64_data,
                signature=signature,
                hash_algorithm="sha2-256",
                prehashed=False,
                mount_point=self._mount_point,
            )

            is_valid = response["data"].get("valid", False)

            self._log_audit(
                "verify",
                key_name,
                operation_hash=operation_hash[:16],
                caller_id=caller_id,
                is_valid=is_valid,
            )

            return VerificationResult(
                is_valid=is_valid,
                key_id=key_name,
                algorithm=algorithm,
                verified_at=datetime.now(UTC),
            )

        except Exception as e:
            self._log_audit(
                "verify",
                key_name,
                success=False,
                error_message=str(e),
                caller_id=caller_id,
            )
            return VerificationResult(
                is_valid=False,
                key_id=key_name,
                algorithm=algorithm,
                verified_at=datetime.now(UTC),
                error_message=str(e),
            )

    # -------------------------------------------------------------------------
    # Key Rotation
    # -------------------------------------------------------------------------

    async def rotate_key(
        self,
        key_name: str | None = None,
        caller_id: str | None = None,
    ) -> int:
        """Rotate a Transit key.

        Creates new key version while maintaining old versions for decryption.

        Args:
            key_name: Key to rotate (default: configured key)
            caller_id: Caller identifier for audit

        Returns:
            New key version number
        """
        client = await self._get_client()
        key = key_name or self._key_name

        try:
            client.secrets.transit.rotate_key(
                name=key,
                mount_point=self._mount_point,
            )

            # Get new version
            key_info = client.secrets.transit.read_key(
                name=key,
                mount_point=self._mount_point,
            )
            new_version = key_info["data"]["latest_version"]

            self._log_audit(
                "key_rotated",
                key,
                caller_id=caller_id,
                new_version=new_version,
            )

            return new_version

        except Exception as e:
            self._log_audit(
                "key_rotated",
                key,
                success=False,
                error_message=str(e),
                caller_id=caller_id,
            )
            raise VaultError("rotate_key", str(e)) from e

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
