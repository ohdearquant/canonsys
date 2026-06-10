# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Tests for evidence/timestamp/requests.py module.

Tests validate RFC 3161 timestamp request dataclass implementation.

Exports Tested (1 symbol):
    - TimestampRequest: RFC 3161 TimeStampReq equivalent

ADR Reference: ADR-201-timestamp

RFC 3161 Reference (Section 2.4.1):
    - messageImprint: Hash of data being timestamped
    - hashAlgorithm: OID identifying hash algorithm
    - nonce: Random value to prevent replay (optional but recommended)
    - certReq: Whether to include TSA certificate in response
"""

from __future__ import annotations

import hashlib

import pytest

from canon.utils.tsa import TimestampRequest
from kron.utils import HashAlgorithm

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_data() -> bytes:
    """Sample binary data for testing."""
    return b"This is test data for timestamping"


@pytest.fixture
def sample_string_data() -> str:
    """Sample string data for testing."""
    return "This is string data for timestamping"


@pytest.fixture
def sha256_hash() -> bytes:
    """Pre-computed SHA-256 hash for testing."""
    return hashlib.sha256(b"test data").digest()


@pytest.fixture
def sha384_hash() -> bytes:
    """Pre-computed SHA-384 hash for testing."""
    return hashlib.sha384(b"test data").digest()


@pytest.fixture
def sha512_hash() -> bytes:
    """Pre-computed SHA-512 hash for testing."""
    return hashlib.sha512(b"test data").digest()


# =============================================================================
# TimestampRequest Direct Instantiation Tests
# =============================================================================


class TestTimestampRequestInstantiation:
    """Tests for direct TimestampRequest instantiation."""

    def test_create_with_sha256(self, sha256_hash: bytes) -> None:
        """Test creating request with SHA-256 hash."""
        request = TimestampRequest(
            message_imprint=sha256_hash,
            hash_algorithm=HashAlgorithm.SHA256,
        )

        assert request.message_imprint == sha256_hash
        assert request.hash_algorithm == HashAlgorithm.SHA256
        assert request.cert_req is True  # Default

    def test_create_with_sha384(self, sha384_hash: bytes) -> None:
        """Test creating request with SHA-384 hash."""
        request = TimestampRequest(
            message_imprint=sha384_hash,
            hash_algorithm=HashAlgorithm.SHA384,
        )

        assert request.message_imprint == sha384_hash
        assert request.hash_algorithm == HashAlgorithm.SHA384

    def test_create_with_sha512(self, sha512_hash: bytes) -> None:
        """Test creating request with SHA-512 hash."""
        request = TimestampRequest(
            message_imprint=sha512_hash,
            hash_algorithm=HashAlgorithm.SHA512,
        )

        assert request.message_imprint == sha512_hash
        assert request.hash_algorithm == HashAlgorithm.SHA512

    def test_create_with_nonce(self, sha256_hash: bytes) -> None:
        """Test creating request with explicit nonce."""
        nonce = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        request = TimestampRequest(
            message_imprint=sha256_hash,
            hash_algorithm=HashAlgorithm.SHA256,
            nonce=nonce,
        )

        assert request.nonce == nonce

    def test_create_with_request_policy(self, sha256_hash: bytes) -> None:
        """Test creating request with request policy OID."""
        policy_oid = "1.2.3.4.5.6"
        request = TimestampRequest(
            message_imprint=sha256_hash,
            hash_algorithm=HashAlgorithm.SHA256,
            request_policy=policy_oid,
        )

        assert request.request_policy == policy_oid

    def test_create_with_cert_req_false(self, sha256_hash: bytes) -> None:
        """Test creating request without certificate request."""
        request = TimestampRequest(
            message_imprint=sha256_hash,
            hash_algorithm=HashAlgorithm.SHA256,
            cert_req=False,
        )

        assert request.cert_req is False

    def test_default_values(self, sha256_hash: bytes) -> None:
        """Test default values are set correctly."""
        request = TimestampRequest(
            message_imprint=sha256_hash,
            hash_algorithm=HashAlgorithm.SHA256,
        )

        assert request.nonce is None
        assert request.request_policy is None
        assert request.cert_req is True


# =============================================================================
# TimestampRequest Validation Tests
# =============================================================================


class TestTimestampRequestValidation:
    """Tests for TimestampRequest __post_init__ validation."""

    def test_sha256_correct_length(self) -> None:
        """Test SHA-256 with correct 32-byte hash passes validation."""
        hash_bytes = b"\x00" * 32  # 32 bytes = 256 bits
        request = TimestampRequest(
            message_imprint=hash_bytes,
            hash_algorithm=HashAlgorithm.SHA256,
        )

        assert len(request.message_imprint) == 32

    def test_sha256_wrong_length_raises(self) -> None:
        """Test SHA-256 with wrong length raises ValueError."""
        wrong_length = b"\x00" * 31  # 31 bytes, should be 32

        with pytest.raises(ValueError) as exc_info:
            TimestampRequest(
                message_imprint=wrong_length,
                hash_algorithm=HashAlgorithm.SHA256,
            )

        assert "length 31 does not match" in str(exc_info.value)
        assert "sha256 expected length 32" in str(exc_info.value)

    def test_sha384_correct_length(self) -> None:
        """Test SHA-384 with correct 48-byte hash passes validation."""
        hash_bytes = b"\x00" * 48  # 48 bytes = 384 bits
        request = TimestampRequest(
            message_imprint=hash_bytes,
            hash_algorithm=HashAlgorithm.SHA384,
        )

        assert len(request.message_imprint) == 48

    def test_sha384_wrong_length_raises(self) -> None:
        """Test SHA-384 with wrong length raises ValueError."""
        wrong_length = b"\x00" * 32  # 32 bytes, should be 48

        with pytest.raises(ValueError) as exc_info:
            TimestampRequest(
                message_imprint=wrong_length,
                hash_algorithm=HashAlgorithm.SHA384,
            )

        assert "length 32 does not match" in str(exc_info.value)
        assert "sha384 expected length 48" in str(exc_info.value)

    def test_sha512_correct_length(self) -> None:
        """Test SHA-512 with correct 64-byte hash passes validation."""
        hash_bytes = b"\x00" * 64  # 64 bytes = 512 bits
        request = TimestampRequest(
            message_imprint=hash_bytes,
            hash_algorithm=HashAlgorithm.SHA512,
        )

        assert len(request.message_imprint) == 64

    def test_sha512_wrong_length_raises(self) -> None:
        """Test SHA-512 with wrong length raises ValueError."""
        wrong_length = b"\x00" * 32  # 32 bytes, should be 64

        with pytest.raises(ValueError) as exc_info:
            TimestampRequest(
                message_imprint=wrong_length,
                hash_algorithm=HashAlgorithm.SHA512,
            )

        assert "length 32 does not match" in str(exc_info.value)
        assert "sha512 expected length 64" in str(exc_info.value)

    def test_empty_hash_raises(self) -> None:
        """Test empty hash raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            TimestampRequest(
                message_imprint=b"",
                hash_algorithm=HashAlgorithm.SHA256,
            )

        assert "length 0 does not match" in str(exc_info.value)


# =============================================================================
# TimestampRequest.from_data Tests
# =============================================================================


class TestTimestampRequestFromData:
    """Tests for TimestampRequest.from_data factory method."""

    def test_from_data_bytes(self, sample_data: bytes) -> None:
        """Test creating request from bytes data."""
        request = TimestampRequest.from_data(sample_data)

        expected_hash = hashlib.sha256(sample_data).digest()
        assert request.message_imprint == expected_hash
        assert request.hash_algorithm == HashAlgorithm.SHA256

    def test_from_data_string(self, sample_string_data: str) -> None:
        """Test creating request from string data (UTF-8 encoded)."""
        request = TimestampRequest.from_data(sample_string_data)

        expected_hash = hashlib.sha256(sample_string_data.encode("utf-8")).digest()
        assert request.message_imprint == expected_hash

    def test_from_data_with_sha384(self, sample_data: bytes) -> None:
        """Test creating request with SHA-384 algorithm."""
        request = TimestampRequest.from_data(
            sample_data,
            hash_algorithm=HashAlgorithm.SHA384,
        )

        expected_hash = hashlib.sha384(sample_data).digest()
        assert request.message_imprint == expected_hash
        assert request.hash_algorithm == HashAlgorithm.SHA384

    def test_from_data_with_sha512(self, sample_data: bytes) -> None:
        """Test creating request with SHA-512 algorithm."""
        request = TimestampRequest.from_data(
            sample_data,
            hash_algorithm=HashAlgorithm.SHA512,
        )

        expected_hash = hashlib.sha512(sample_data).digest()
        assert request.message_imprint == expected_hash
        assert request.hash_algorithm == HashAlgorithm.SHA512

    def test_from_data_includes_nonce_by_default(self, sample_data: bytes) -> None:
        """Test that nonce is included by default (SEC-003 compliance)."""
        request = TimestampRequest.from_data(sample_data)

        assert request.nonce is not None
        # SEC-003: 128-bit nonce = 16 bytes
        assert len(request.nonce) == 16

    def test_from_data_nonce_is_random(self, sample_data: bytes) -> None:
        """Test that each request gets a unique random nonce."""
        request1 = TimestampRequest.from_data(sample_data)
        request2 = TimestampRequest.from_data(sample_data)

        # Nonces should be different (random)
        assert request1.nonce != request2.nonce

    def test_from_data_without_nonce(self, sample_data: bytes) -> None:
        """Test creating request without nonce."""
        request = TimestampRequest.from_data(
            sample_data,
            include_nonce=False,
        )

        assert request.nonce is None

    def test_from_data_with_request_policy(self, sample_data: bytes) -> None:
        """Test creating request with request policy OID."""
        policy = "1.2.3.4.5.6.7"
        request = TimestampRequest.from_data(
            sample_data,
            request_policy=policy,
        )

        assert request.request_policy == policy

    def test_from_data_without_cert_req(self, sample_data: bytes) -> None:
        """Test creating request without certificate request."""
        request = TimestampRequest.from_data(
            sample_data,
            cert_req=False,
        )

        assert request.cert_req is False

    def test_from_data_empty_bytes(self) -> None:
        """Test creating request from empty bytes."""
        request = TimestampRequest.from_data(b"")

        expected_hash = hashlib.sha256(b"").digest()
        assert request.message_imprint == expected_hash

    def test_from_data_empty_string(self) -> None:
        """Test creating request from empty string."""
        request = TimestampRequest.from_data("")

        expected_hash = hashlib.sha256(b"").digest()
        assert request.message_imprint == expected_hash


# =============================================================================
# TimestampRequest Immutability Tests
# =============================================================================


class TestTimestampRequestImmutability:
    """Tests for TimestampRequest frozen dataclass behavior."""

    def test_request_is_frozen(self, sha256_hash: bytes) -> None:
        """Test that request is immutable (frozen dataclass)."""
        request = TimestampRequest(
            message_imprint=sha256_hash,
            hash_algorithm=HashAlgorithm.SHA256,
        )

        with pytest.raises(AttributeError):
            request.message_imprint = b"new_hash"  # type: ignore[misc]

    def test_request_is_hashable(self, sha256_hash: bytes) -> None:
        """Test that request can be used in sets/dicts (hashable)."""
        request = TimestampRequest(
            message_imprint=sha256_hash,
            hash_algorithm=HashAlgorithm.SHA256,
        )

        # Should be hashable
        request_set = {request}
        assert request in request_set


# =============================================================================
# TimestampRequest Edge Cases
# =============================================================================


class TestTimestampRequestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_unicode_string_data(self) -> None:
        """Test handling of unicode string data."""
        unicode_data = "Hello World with special chars"
        request = TimestampRequest.from_data(unicode_data)

        expected_hash = hashlib.sha256(unicode_data.encode("utf-8")).digest()
        assert request.message_imprint == expected_hash

    def test_binary_data_with_null_bytes(self) -> None:
        """Test handling of binary data containing null bytes."""
        binary_data = b"\x00\x00\x00data\x00\x00"
        request = TimestampRequest.from_data(binary_data)

        expected_hash = hashlib.sha256(binary_data).digest()
        assert request.message_imprint == expected_hash

    def test_large_data(self) -> None:
        """Test handling of large data input."""
        large_data = b"x" * 10_000_000  # 10MB
        request = TimestampRequest.from_data(large_data)

        expected_hash = hashlib.sha256(large_data).digest()
        assert request.message_imprint == expected_hash

    def test_all_parameters_combined(self) -> None:
        """Test creating request with all parameters specified."""
        data = b"test data"
        nonce = b"\x01" * 16

        request = TimestampRequest.from_data(
            data,
            hash_algorithm=HashAlgorithm.SHA512,
            include_nonce=True,
            request_policy="1.2.3.4",
            cert_req=False,
        )

        assert request.hash_algorithm == HashAlgorithm.SHA512
        assert request.nonce is not None
        assert len(request.nonce) == 16
        assert request.request_policy == "1.2.3.4"
        assert request.cert_req is False


# =============================================================================
# RFC 3161 Compliance Tests
# =============================================================================


class TestRFC3161Compliance:
    """Tests validating RFC 3161 compliance.

    RFC 3161 Section 2.4.1 defines TimeStampReq structure:
    - messageImprint: REQUIRED - Hash of data
    - hashAlgorithm: REQUIRED - OID of hash algorithm
    - nonce: OPTIONAL - Anti-replay value (recommended)
    - certReq: OPTIONAL - Request TSA cert in response (default TRUE)
    - reqPolicy: OPTIONAL - Requested TSA policy
    """

    def test_message_imprint_is_required(self) -> None:
        """RFC 3161: messageImprint is REQUIRED."""
        # Cannot create request without message_imprint
        # (enforced by dataclass required field)
        with pytest.raises(TypeError):
            TimestampRequest(hash_algorithm=HashAlgorithm.SHA256)  # type: ignore[call-arg]

    def test_hash_algorithm_is_required(self) -> None:
        """RFC 3161: hashAlgorithm is REQUIRED."""
        # Cannot create request without hash_algorithm
        with pytest.raises(TypeError):
            TimestampRequest(message_imprint=b"\x00" * 32)  # type: ignore[call-arg]

    def test_nonce_is_optional_but_recommended(self) -> None:
        """RFC 3161: nonce is OPTIONAL but RECOMMENDED for replay protection."""
        hash_bytes = b"\x00" * 32

        # With nonce (recommended)
        request_with_nonce = TimestampRequest.from_data(b"test", include_nonce=True)
        assert request_with_nonce.nonce is not None

        # Without nonce (valid but not recommended)
        request_without_nonce = TimestampRequest.from_data(b"test", include_nonce=False)
        assert request_without_nonce.nonce is None

    def test_cert_req_defaults_to_true(self) -> None:
        """RFC 3161: certReq defaults to TRUE per specification."""
        request = TimestampRequest.from_data(b"test")

        assert request.cert_req is True

    def test_request_policy_is_optional(self) -> None:
        """RFC 3161: reqPolicy is OPTIONAL."""
        # Without policy
        request_no_policy = TimestampRequest.from_data(b"test")
        assert request_no_policy.request_policy is None

        # With policy
        request_with_policy = TimestampRequest.from_data(
            b"test",
            request_policy="1.2.3.4.5",
        )
        assert request_with_policy.request_policy == "1.2.3.4.5"

    def test_nonce_entropy_sec003(self) -> None:
        """SEC-003: Nonce should have 128-bit entropy (16 bytes).

        RFC 3161 recommends at least 64-bit; we use 128-bit for stronger
        replay protection.
        """
        request = TimestampRequest.from_data(b"test")

        assert request.nonce is not None
        assert len(request.nonce) == 16  # 128 bits = 16 bytes


# =============================================================================
# Integration Tests
# =============================================================================


class TestTimestampRequestIntegration:
    """Integration tests for complete timestamp request workflows."""

    def test_deterministic_hash_for_same_data(self) -> None:
        """Test that same data always produces same hash."""
        data = b"deterministic test data"

        request1 = TimestampRequest.from_data(data, include_nonce=False)
        request2 = TimestampRequest.from_data(data, include_nonce=False)

        assert request1.message_imprint == request2.message_imprint

    def test_different_data_produces_different_hash(self) -> None:
        """Test that different data produces different hashes."""
        data1 = b"first data"
        data2 = b"second data"

        request1 = TimestampRequest.from_data(data1, include_nonce=False)
        request2 = TimestampRequest.from_data(data2, include_nonce=False)

        assert request1.message_imprint != request2.message_imprint

    def test_hash_algorithm_consistency(self) -> None:
        """Test that hash matches expected algorithm output."""
        data = b"algorithm test"

        # SHA-256
        req_256 = TimestampRequest.from_data(data, hash_algorithm=HashAlgorithm.SHA256)
        assert req_256.message_imprint == hashlib.sha256(data).digest()
        assert len(req_256.message_imprint) == 32

        # SHA-384
        req_384 = TimestampRequest.from_data(data, hash_algorithm=HashAlgorithm.SHA384)
        assert req_384.message_imprint == hashlib.sha384(data).digest()
        assert len(req_384.message_imprint) == 48

        # SHA-512
        req_512 = TimestampRequest.from_data(data, hash_algorithm=HashAlgorithm.SHA512)
        assert req_512.message_imprint == hashlib.sha512(data).digest()
        assert len(req_512.message_imprint) == 64
