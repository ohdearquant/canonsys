# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""TSA type definitions - configs, requests, tokens, verification results."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from kron.utils import HashAlgorithm

__all__ = [
    "TSAConfig",
    "TimestampRequest",
    "TimestampToken",
    "TimestampVerificationResult",
]


# =============================================================================
# TSA Configuration
# =============================================================================


@dataclass(frozen=True)
class TSAConfig:
    """Timestamp Authority configuration.

    Pre-configured settings for connecting to a TSA service.
    Use TSA_PRESETS for common commercial TSAs.

    For production, use a TSA with:
    - ISO 27001 certification
    - AICPA SOC 2 Type II audit
    - WebTrust for CAs certification

    Attributes:
        url: TSA endpoint URL
        name: Human-readable TSA name
        auth_type: Authentication method (none, basic, certificate)
        username: Basic auth username (if auth_type="basic")
        password: Basic auth password (if auth_type="basic")
        timeout_seconds: Request timeout
        retry_count: Number of retries on failure
    """

    url: str
    name: str
    auth_type: Literal["none", "basic", "certificate"] = "none"
    username: str | None = None
    password: str | None = None
    timeout_seconds: float = 30.0
    retry_count: int = 3

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.auth_type == "basic" and (not self.username or not self.password):
            raise ValueError("Basic auth requires username and password")

    @property
    def auth(self) -> tuple[str, str] | None:
        """Get auth tuple for HTTP client."""
        if self.auth_type == "basic" and self.username and self.password:
            return (self.username, self.password)
        return None


# =============================================================================
# Timestamp Request
# =============================================================================


@dataclass(frozen=True)
class TimestampRequest:
    """RFC 3161 TimeStampReq equivalent.

    Per RFC 3161 Section 2.4.1:
    - messageImprint: Hash of data being timestamped
    - hashAlgorithm: OID identifying hash algorithm
    - nonce: Random value to prevent replay (optional but recommended)
    - certReq: Whether to include TSA certificate in response

    Attributes:
        message_imprint: Hash of data to timestamp (raw bytes)
        hash_algorithm: Hash algorithm used to create message_imprint
        nonce: Anti-replay protection (random bytes, optional but recommended)
        request_policy: Requested TSA policy OID (optional)
        cert_req: Whether to include TSA certificate in response
    """

    message_imprint: bytes
    hash_algorithm: HashAlgorithm
    nonce: bytes | None = None
    request_policy: str | None = None
    cert_req: bool = True

    def __post_init__(self) -> None:
        """Validate message imprint length matches hash algorithm."""
        expected_lengths = {
            HashAlgorithm.SHA256: 32,
            HashAlgorithm.SHA384: 48,
            HashAlgorithm.SHA512: 64,
        }
        expected = expected_lengths[self.hash_algorithm]
        actual = len(self.message_imprint)
        if actual != expected:
            raise ValueError(
                f"message_imprint length {actual} does not match "
                f"{self.hash_algorithm.value} expected length {expected}"
            )

    @classmethod
    def from_data(
        cls,
        data: bytes | str,
        *,
        hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
        include_nonce: bool = True,
        request_policy: str | None = None,
        cert_req: bool = True,
    ) -> TimestampRequest:
        """Create request from data by computing hash.

        Args:
            data: Data to timestamp (will be hashed)
            hash_algorithm: Hash algorithm to use
            include_nonce: Whether to include anti-replay nonce
            request_policy: Requested TSA policy OID
            cert_req: Whether to include TSA certificate in response

        Returns:
            TimestampRequest ready to send to TSA
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        hasher = hash_algorithm.get_hasher()
        message_imprint = hasher(data).digest()

        # SEC-003: Use 128-bit nonce for improved entropy
        nonce = secrets.token_bytes(16) if include_nonce else None

        return cls(
            message_imprint=message_imprint,
            hash_algorithm=hash_algorithm,
            nonce=nonce,
            request_policy=request_policy,
            cert_req=cert_req,
        )


# =============================================================================
# Timestamp Token
# =============================================================================


@dataclass(frozen=True)
class TimestampToken:
    """RFC 3161 TimeStampToken (TST).

    Contains the TSA's signed assertion that the hash existed at
    the stated time. This is the cryptographic proof of timing.

    Per RFC 3161 Section 2.4.2, the TimeStampToken contains:
    - TSTInfo: The timestamped data (genTime, messageImprint, etc.)
    - SignerInfo: TSA's signature over TSTInfo

    Attributes:
        gen_time: TSA-asserted timestamp (UTC)
        message_imprint: Original hash that was timestamped
        hash_algorithm: Algorithm used for message_imprint
        serial_number: TSA-assigned unique serial number
        tsa_name: TSA identifier (typically X.500 name)
        tsa_policy_oid: Policy OID under which timestamp was issued
        signature: TSA signature over TSTInfo
        signature_algorithm: Signature algorithm (e.g., "RSA-SHA256")
        tsa_certificate: TSA signing certificate (DER-encoded, optional)
        raw_token: Complete DER-encoded TimeStampToken for storage
        verified: Whether signature has been verified
        verification_time: When verification was performed
    """

    # Core timestamp data
    gen_time: datetime
    message_imprint: bytes
    hash_algorithm: HashAlgorithm
    serial_number: int

    # TSA information
    tsa_name: str
    tsa_policy_oid: str

    # Cryptographic proof
    signature: bytes
    signature_algorithm: str
    tsa_certificate: bytes | None

    # Raw token for storage/verification
    raw_token: bytes

    # Verification status
    verified: bool = False
    verification_time: datetime | None = None

    @property
    def message_imprint_hex(self) -> str:
        """Get message imprint as hex string."""
        return self.message_imprint.hex()

    @property
    def signature_hex(self) -> str:
        """Get signature as hex string."""
        return self.signature.hex()

    def matches_hash(self, hash_value: str | bytes) -> bool:
        """Check if token matches given hash value.

        Args:
            hash_value: Hash to compare (hex string or bytes)

        Returns:
            True if message_imprint matches hash_value
        """
        hash_bytes = bytes.fromhex(hash_value) if isinstance(hash_value, str) else hash_value
        return self.message_imprint == hash_bytes


# =============================================================================
# Verification Result
# =============================================================================


@dataclass(frozen=True)
class TimestampVerificationResult:
    """Result of timestamp token verification.

    Returned by TimestampService.verify() with full audit details
    for compliance documentation.

    Attributes:
        is_valid: Overall verification result
        verified_at: When verification was performed
        hash_matches: Whether message imprint matches data hash
        signature_valid: Whether TSA signature was cryptographically verified
        timestamp: Extracted timestamp from token
        error_message: Error details if verification failed
        chain_validated: Whether certificate chain was validated (via OpenSSL)
    """

    is_valid: bool
    verified_at: datetime
    hash_matches: bool
    signature_valid: bool
    timestamp: datetime
    error_message: str | None = None
    chain_validated: bool = False

    @classmethod
    def success(
        cls,
        *,
        timestamp: datetime,
        signature_valid: bool,
        verified_at: datetime | None = None,
        chain_validated: bool = False,
    ) -> TimestampVerificationResult:
        """Create successful verification result.

        Args:
            timestamp: Timestamp from the token
            signature_valid: Whether CMS signature was cryptographically verified.
                            Must be True for full legal defensibility.
            verified_at: When verification was performed
            chain_validated: Whether certificate chain was validated (via OpenSSL -CAfile)
        """
        return cls(
            is_valid=True,
            verified_at=verified_at or datetime.now(UTC),
            hash_matches=True,
            signature_valid=signature_valid,
            timestamp=timestamp,
            error_message=None,
            chain_validated=chain_validated,
        )

    @classmethod
    def hash_only(
        cls,
        *,
        timestamp: datetime,
        verified_at: datetime | None = None,
    ) -> TimestampVerificationResult:
        """Create result for hash-only verification (signature NOT verified).

        WARNING: This result has signature_valid=False because CMS signature
        was not cryptographically verified. Use verify_with_openssl() for
        full verification including signature validation.
        """
        return cls(
            is_valid=True,  # Hash matches, but signature not verified
            verified_at=verified_at or datetime.now(UTC),
            hash_matches=True,
            signature_valid=False,  # HONEST: we didn't verify signature
            timestamp=timestamp,
            error_message=None,
            chain_validated=False,
        )

    @classmethod
    def failure(
        cls,
        *,
        error_message: str,
        hash_matches: bool = False,
        signature_valid: bool = False,
        timestamp: datetime | None = None,
        verified_at: datetime | None = None,
        chain_validated: bool = False,
    ) -> TimestampVerificationResult:
        """Create failed verification result."""
        return cls(
            is_valid=False,
            verified_at=verified_at or datetime.now(UTC),
            hash_matches=hash_matches,
            signature_valid=signature_valid,
            timestamp=timestamp or datetime.min.replace(tzinfo=UTC),
            error_message=error_message,
            chain_validated=chain_validated,
        )
