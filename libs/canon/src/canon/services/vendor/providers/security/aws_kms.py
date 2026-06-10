# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""AWS KMS HSM provider implementation.

Implements HSMProvider protocol using AWS Key Management Service for:
- Key generation (DEK/KEK)
- Key destruction (crypto-shredding)
- Encryption/decryption operations
- Evidence signing and verification (FRE 902)

Environment Variables:
    AWS_ACCESS_KEY_ID: AWS credentials
    AWS_SECRET_ACCESS_KEY: AWS credentials
    AWS_REGION: AWS region (default: us-east-1)
    CANON_AWS_KMS_KEY_ID: Default KMS key ID or alias

Security References:
    - FIPS 140-2 Level 3: AWS KMS HSM compliance
    - NIST SP 800-57: Key Management
    - CWE-347: Cryptographic signature verification
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from canon.utils import EncryptionAlgorithm, KeyType

logger = logging.getLogger(__name__)


class AWSKMSError(Exception):
    """AWS KMS operation error."""

    def __init__(self, operation: str, message: str):
        self.operation = operation
        super().__init__(f"AWS KMS {operation} failed: {message}")


class SigningAlgorithm(str, Enum):
    """Supported signing algorithms for KMS."""

    HMAC_SHA256 = "HMAC_SHA_256"
    RSASSA_PKCS1_V1_5_SHA_256 = "RSASSA_PKCS1_V1_5_SHA_256"
    RSASSA_PSS_SHA_256 = "RSASSA_PSS_SHA_256"
    ECDSA_SHA_256 = "ECDSA_SHA_256"


@dataclass
class SignatureResult:
    """Result of a signing operation."""

    signature: str  # Base64-encoded
    key_id: str
    algorithm: SigningAlgorithm
    timestamp: datetime


@dataclass
class VerificationResult:
    """Result of a signature verification."""

    is_valid: bool
    key_id: str
    algorithm: SigningAlgorithm
    verified_at: datetime
    error_message: str | None = None


@dataclass
class AuditLogEntry:
    """Audit log entry for key operations.

    Per CWE-347, all cryptographic operations must be logged.
    """

    event_id: str
    event_type: str
    timestamp: datetime
    key_id: str
    success: bool
    operation_hash: str | None = None
    error_message: str | None = None
    caller_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AWSKMSProvider:
    """AWS KMS implementation of HSMProvider protocol.

    Uses AWS Key Management Service for HSM-backed cryptographic operations.
    Keys never leave the HSM boundary.

    Usage:
        provider = AWSKMSProvider(
            region="us-east-1",
            default_key_id="alias/canonsys-evidence"
        )
        # For encryption
        ciphertext = await provider.encrypt(handle, plaintext, context)
        # For signing
        sig = await provider.sign(data, "alias/signing-key")

    Environment:
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY for credentials
        Or use IAM roles when running on AWS infrastructure
    """

    def __init__(
        self,
        region: str | None = None,
        default_key_id: str | None = None,
    ):
        """Initialize AWS KMS provider.

        Args:
            region: AWS region (default from env or us-east-1)
            default_key_id: Default KMS key ID or alias
        """
        self._region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._default_key_id = default_key_id or os.environ.get("CANON_AWS_KMS_KEY_ID")
        self._client: Any = None
        self._audit_log: list[AuditLogEntry] = []

    async def _get_client(self) -> Any:
        """Get or create boto3 KMS client.

        Returns:
            boto3 KMS client.

        Raises:
            AWSKMSError: If boto3 is not available.
        """
        if self._client is None:
            try:
                import boto3
            except ImportError as err:
                raise AWSKMSError(
                    "initialization",
                    "boto3 package required. Install with: pip install boto3",
                ) from err

            self._client = boto3.client("kms", region_name=self._region)
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
            event_id=f"kms_{uuid4().hex[:12]}",
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
        log_fn(
            "AWS KMS audit: %s key=%s success=%s",
            event_type,
            key_id[:20] + "..." if len(key_id) > 20 else key_id,
            success,
        )
        return entry

    # -------------------------------------------------------------------------
    # HSMProvider Protocol Implementation
    # -------------------------------------------------------------------------

    async def generate_key(
        self,
        key_type: KeyType,
        algorithm: EncryptionAlgorithm,
    ) -> str:
        """Generate a new key in AWS KMS.

        Args:
            key_type: Type of key (DEK, KEK)
            algorithm: Encryption algorithm

        Returns:
            KMS key ID (ARN or alias)

        Note:
            For DEKs, we generate data keys. For KEKs, we create
            symmetric CMKs.
        """
        client = await self._get_client()

        try:
            if key_type == KeyType.DEK:
                # Generate data key (returns plaintext + encrypted copy)
                response = client.generate_data_key(
                    KeyId=self._default_key_id,
                    KeySpec="AES_256",
                )
                # Return the encrypted key blob as handle
                key_handle = base64.b64encode(response["CiphertextBlob"]).decode("ascii")
            else:
                # Create a new CMK for KEK
                response = client.create_key(
                    KeyUsage="ENCRYPT_DECRYPT",
                    KeySpec="SYMMETRIC_DEFAULT",
                    Description=f"canonsys {key_type.value} key",
                    Tags=[
                        {"TagKey": "Application", "TagValue": "canonsys"},
                        {"TagKey": "KeyType", "TagValue": key_type.value},
                    ],
                )
                key_handle = response["KeyMetadata"]["KeyId"]

            self._log_audit(
                "key_generated",
                key_handle[:40],
                key_type=key_type.value,
                algorithm=algorithm.value,
            )
            return key_handle

        except Exception as e:
            self._log_audit(
                "key_generated",
                self._default_key_id or "unknown",
                success=False,
                error_message=str(e),
            )
            raise AWSKMSError("generate_key", str(e)) from e

    async def destroy_key(
        self,
        key_handle: str,
        reason: str,
    ) -> str:
        """Schedule key destruction in AWS KMS.

        Per NIST SP 800-88, schedules cryptographic erasure.

        Args:
            key_handle: KMS key ID to destroy
            reason: Audit trail reason

        Returns:
            Attestation string proving destruction scheduled

        Note:
            AWS KMS has a 7-30 day waiting period before actual deletion.
            For data keys (DEK), we just discard the encrypted blob.
        """
        client = await self._get_client()

        try:
            # Check if this is a data key blob or a CMK
            if key_handle.startswith("arn:") or key_handle.startswith("alias/"):
                # It's a CMK - schedule deletion
                response = client.schedule_key_deletion(
                    KeyId=key_handle,
                    PendingWindowInDays=7,  # Minimum waiting period
                )
                deletion_date = response["DeletionDate"].isoformat()
                attestation = (
                    f"AWS KMS key {key_handle} scheduled for deletion "
                    f"at {deletion_date}. Reason: {reason}"
                )
            else:
                # It's an encrypted data key blob - discard it
                # The plaintext key is already gone from memory
                attestation = (
                    f"Data key blob discarded at {datetime.now(UTC).isoformat()}. "
                    f"Reason: {reason}. Encrypted data is now unrecoverable."
                )

            self._log_audit(
                "key_destroyed",
                key_handle[:40],
                reason=reason,
            )
            return attestation

        except Exception as e:
            self._log_audit(
                "key_destroyed",
                key_handle[:40],
                success=False,
                error_message=str(e),
            )
            raise AWSKMSError("destroy_key", str(e)) from e

    async def encrypt(
        self,
        key_handle: str,
        plaintext: bytes,
        context: dict[str, str],
    ) -> bytes:
        """Encrypt data using KMS key.

        Uses authenticated encryption with encryption context as AAD.

        Args:
            key_handle: KMS key ID or encrypted data key
            plaintext: Data to encrypt
            context: Encryption context (bound as AAD)

        Returns:
            Ciphertext
        """
        client = await self._get_client()

        try:
            response = client.encrypt(
                KeyId=self._default_key_id,
                Plaintext=plaintext,
                EncryptionContext=context,
            )

            self._log_audit(
                "encrypt",
                self._default_key_id or "default",
                operation_hash=hashlib.sha256(plaintext).hexdigest()[:16],
            )
            return response["CiphertextBlob"]

        except Exception as e:
            self._log_audit(
                "encrypt",
                self._default_key_id or "default",
                success=False,
                error_message=str(e),
            )
            raise AWSKMSError("encrypt", str(e)) from e

    async def decrypt(
        self,
        key_handle: str,
        ciphertext: bytes,
        context: dict[str, str],
    ) -> bytes:
        """Decrypt data using KMS key.

        Args:
            key_handle: KMS key ID
            ciphertext: Data to decrypt
            context: Encryption context (must match encryption)

        Returns:
            Decrypted plaintext
        """
        client = await self._get_client()

        try:
            response = client.decrypt(
                CiphertextBlob=ciphertext,
                EncryptionContext=context,
            )

            self._log_audit("decrypt", key_handle[:40] if key_handle else "auto")
            return response["Plaintext"]

        except client.exceptions.InvalidCiphertextException as e:
            self._log_audit(
                "decrypt",
                key_handle[:40] if key_handle else "auto",
                success=False,
                error_message="Key destroyed or context mismatch",
            )
            raise AWSKMSError(
                "decrypt",
                "Decryption failed - key may have been destroyed (crypto-shredded)",
            ) from e
        except Exception as e:
            self._log_audit(
                "decrypt",
                key_handle[:40] if key_handle else "auto",
                success=False,
                error_message=str(e),
            )
            raise AWSKMSError("decrypt", str(e)) from e

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
            key_id: Signing key ID (default: configured key)
            algorithm: Signing algorithm
            caller_id: Caller identifier for audit

        Returns:
            SignatureResult with base64 signature
        """
        client = await self._get_client()
        actual_key_id = key_id or self._default_key_id
        if not actual_key_id:
            raise AWSKMSError("sign", "No signing key configured")

        operation_hash = hashlib.sha256(data).hexdigest()

        try:
            if algorithm == SigningAlgorithm.HMAC_SHA256:
                response = client.generate_mac(
                    KeyId=actual_key_id,
                    Message=data,
                    MacAlgorithm=algorithm.value,
                )
                signature = base64.b64encode(response["Mac"]).decode("ascii")
            else:
                # Asymmetric signing
                response = client.sign(
                    KeyId=actual_key_id,
                    Message=data,
                    MessageType="RAW",
                    SigningAlgorithm=algorithm.value,
                )
                signature = base64.b64encode(response["Signature"]).decode("ascii")

            self._log_audit(
                "sign",
                actual_key_id,
                operation_hash=operation_hash[:16],
                caller_id=caller_id,
                algorithm=algorithm.value,
            )

            return SignatureResult(
                signature=signature,
                key_id=actual_key_id,
                algorithm=algorithm,
                timestamp=datetime.now(UTC),
            )

        except Exception as e:
            self._log_audit(
                "sign",
                actual_key_id,
                success=False,
                error_message=str(e),
                caller_id=caller_id,
            )
            raise AWSKMSError("sign", str(e)) from e

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
            signature: Base64-encoded signature
            key_id: Signing key ID
            algorithm: Signing algorithm
            caller_id: Caller identifier for audit

        Returns:
            VerificationResult with validity status
        """
        client = await self._get_client()
        actual_key_id = key_id or self._default_key_id
        if not actual_key_id:
            raise AWSKMSError("verify", "No signing key configured")

        operation_hash = hashlib.sha256(data).hexdigest()

        try:
            signature_bytes = base64.b64decode(signature)

            if algorithm == SigningAlgorithm.HMAC_SHA256:
                response = client.verify_mac(
                    KeyId=actual_key_id,
                    Message=data,
                    Mac=signature_bytes,
                    MacAlgorithm=algorithm.value,
                )
                is_valid = response.get("MacValid", False)
            else:
                response = client.verify(
                    KeyId=actual_key_id,
                    Message=data,
                    MessageType="RAW",
                    Signature=signature_bytes,
                    SigningAlgorithm=algorithm.value,
                )
                is_valid = response.get("SignatureValid", False)

            self._log_audit(
                "verify",
                actual_key_id,
                operation_hash=operation_hash[:16],
                caller_id=caller_id,
                is_valid=is_valid,
            )

            return VerificationResult(
                is_valid=is_valid,
                key_id=actual_key_id,
                algorithm=algorithm,
                verified_at=datetime.now(UTC),
            )

        except Exception as e:
            self._log_audit(
                "verify",
                actual_key_id,
                success=False,
                error_message=str(e),
                caller_id=caller_id,
            )
            return VerificationResult(
                is_valid=False,
                key_id=actual_key_id,
                algorithm=algorithm,
                verified_at=datetime.now(UTC),
                error_message=str(e),
            )

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
