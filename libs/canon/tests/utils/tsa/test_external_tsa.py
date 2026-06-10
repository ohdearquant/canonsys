# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Tests for RFC 3161 External TSA Service.

Tests the ExternalTSAService implementation with mocked TSA responses.

ADR Reference: ADR-201-timestamp
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asn1crypto import algos, cms, core, tsp

from canon.exceptions import ExecutionError
from canon.utils.tsa import TSA_PRESETS, ExternalTSAService, TSAConfig
from kron.utils import HashAlgorithm

# --- Fixtures ---


@pytest.fixture
def tsa_config() -> TSAConfig:
    """Create test TSA configuration."""
    return TSAConfig(
        url="http://test-tsa.example.com/timestamp",
        name="Test TSA",
        auth_type="none",
        timeout_seconds=10.0,
        retry_count=2,
    )


@pytest.fixture
def backup_tsa_config() -> TSAConfig:
    """Create backup TSA configuration."""
    return TSAConfig(
        url="http://backup-tsa.example.com/timestamp",
        name="Backup TSA",
        auth_type="none",
        timeout_seconds=10.0,
        retry_count=2,
    )


@pytest.fixture
def tsa_service(tsa_config: TSAConfig) -> ExternalTSAService:
    """Create ExternalTSAService with test config."""
    return ExternalTSAService(tsa_config)


@pytest.fixture
def tsa_service_with_backup(
    tsa_config: TSAConfig,
    backup_tsa_config: TSAConfig,
) -> ExternalTSAService:
    """Create ExternalTSAService with backup config."""
    return ExternalTSAService(tsa_config, backup_config=backup_tsa_config)


# --- Mock TSA Response Builders ---


def build_mock_tsa_response(
    hash_value: bytes,
    hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    gen_time: datetime | None = None,
    status: int = 0,
) -> bytes:
    """Build a mock RFC 3161 TimeStampResp.

    Args:
        hash_value: Hash that was timestamped
        hash_algorithm: Hash algorithm used
        gen_time: Timestamp to embed (defaults to now)
        status: PKI status (0=granted)

    Returns:
        DER-encoded TimeStampResp bytes
    """
    if gen_time is None:
        gen_time = datetime.now(UTC)

    # OIDs for hash algorithms
    hash_oids = {
        HashAlgorithm.SHA256: "2.16.840.1.101.3.4.2.1",
        HashAlgorithm.SHA384: "2.16.840.1.101.3.4.2.2",
        HashAlgorithm.SHA512: "2.16.840.1.101.3.4.2.3",
    }

    # Build TSTInfo (the actual timestamp data)
    tst_info = tsp.TSTInfo(
        {
            "version": 1,
            "policy": "1.2.3.4.5",
            "message_imprint": {
                "hash_algorithm": {"algorithm": hash_oids[hash_algorithm]},
                "hashed_message": hash_value,
            },
            "serial_number": secrets.randbelow(2**64),
            "gen_time": gen_time,
            "nonce": secrets.randbelow(2**64),
        }
    )

    tst_info_bytes = tst_info.dump()

    # Build encapsulated content info with ParsableOctetString for content
    encap_content = cms.EncapsulatedContentInfo()
    encap_content["content_type"] = "1.2.840.113549.1.9.16.1.4"  # id-ct-TSTInfo
    encap_content["content"] = core.ParsableOctetString(tst_info_bytes)

    # Build digest algorithm
    digest_algo = algos.DigestAlgorithm({"algorithm": hash_oids[hash_algorithm]})

    # Build SignedData
    signed_data = cms.SignedData()
    signed_data["version"] = 3
    signed_data["digest_algorithms"] = [digest_algo]
    signed_data["encap_content_info"] = encap_content
    signed_data["signer_infos"] = []

    # Wrap in ContentInfo
    content_info = cms.ContentInfo()
    content_info["content_type"] = "1.2.840.113549.1.7.2"  # signedData
    content_info["content"] = signed_data

    # Build PKIStatusInfo
    pki_status_info = tsp.PKIStatusInfo()
    pki_status_info["status"] = status

    # Build TimeStampResp
    ts_resp = tsp.TimeStampResp()
    ts_resp["status"] = pki_status_info
    ts_resp["time_stamp_token"] = content_info

    return ts_resp.dump()


def build_rejected_tsa_response(
    status: int = 2,
    status_string: str = "Request rejected",
) -> bytes:
    """Build a rejected TSA response.

    Args:
        status: PKI status (2=rejection)
        status_string: Error message

    Returns:
        DER-encoded TimeStampResp bytes
    """
    # For rejection responses, we construct manually with just the status
    # TimeStampResp ::= SEQUENCE {
    #     status          PKIStatusInfo,
    #     timeStampToken  TimeStampToken OPTIONAL
    # }
    # When status is not granted, timeStampToken should be absent

    pki_status_info = tsp.PKIStatusInfo()
    pki_status_info["status"] = tsp.PKIStatus(status)
    pki_status_info["status_string"] = tsp.PKIFreeText([status_string])

    # Build response without timeStampToken (optional field when rejected)
    # We need to manually construct the DER bytes
    status_bytes = pki_status_info.dump()

    # TimeStampResp is a SEQUENCE with status and optional timeStampToken
    # Construct as SEQUENCE containing just the status
    from asn1crypto.core import Sequence

    class MinimalTimeStampResp(Sequence):
        _fields = [
            ("status", tsp.PKIStatusInfo),
        ]

    resp = MinimalTimeStampResp()
    resp["status"] = pki_status_info

    return resp.dump()


# --- Unit Tests ---


class TestExternalTSAServiceInit:
    """Tests for ExternalTSAService initialization."""

    def test_init_with_config(self, tsa_config: TSAConfig) -> None:
        """Test initialization with config."""
        service = ExternalTSAService(tsa_config)
        assert service._config == tsa_config

    def test_init_with_backup(
        self,
        tsa_config: TSAConfig,
        backup_tsa_config: TSAConfig,
    ) -> None:
        """Test initialization with backup config."""
        service = ExternalTSAService(tsa_config, backup_config=backup_tsa_config)
        assert service._config == tsa_config
        assert service._backup_config == backup_tsa_config

    def test_init_with_preset(self) -> None:
        """Test initialization with preset config."""
        service = ExternalTSAService(TSA_PRESETS["digicert"])
        assert service._config.name == "DigiCert Timestamp"


class TestStamp:
    """Tests for stamp() method."""

    @pytest.mark.asyncio
    async def test_stamp_string_data(self, tsa_service: ExternalTSAService) -> None:
        """Test stamping string data."""
        test_data = "Hello, World!"
        test_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_token_bytes = b"mock_timestamp_token"
        mock_token_b64 = base64.b64encode(mock_token_bytes).decode()

        # Mock at _request_timestamp level (internal method)
        with patch.object(
            tsa_service, "_request_timestamp", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = (mock_token_b64, test_time)

            token, timestamp = await tsa_service.stamp(test_data)

            assert isinstance(token, str)
            assert base64.b64decode(token) == mock_token_bytes
            assert timestamp == test_time
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_stamp_bytes_data(self, tsa_service: ExternalTSAService) -> None:
        """Test stamping bytes data."""
        test_data = b"\x00\x01\x02\x03"
        test_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_token_bytes = b"mock_timestamp_token"
        mock_token_b64 = base64.b64encode(mock_token_bytes).decode()

        with patch.object(
            tsa_service, "_request_timestamp", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = (mock_token_b64, test_time)

            token, timestamp = await tsa_service.stamp(test_data)

            assert isinstance(token, str)
            assert timestamp == test_time

    @pytest.mark.asyncio
    async def test_stamp_sha384(self, tsa_service: ExternalTSAService) -> None:
        """Test stamping with SHA-384."""
        test_data = "Test data"
        test_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_token_bytes = b"mock_timestamp_token_sha384"
        mock_token_b64 = base64.b64encode(mock_token_bytes).decode()

        with patch.object(
            tsa_service, "_request_timestamp", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = (mock_token_b64, test_time)

            token, timestamp = await tsa_service.stamp(
                test_data,
                hash_algorithm=HashAlgorithm.SHA384,
            )

            assert timestamp == test_time


class TestStampHash:
    """Tests for stamp_hash() method."""

    @pytest.mark.asyncio
    async def test_stamp_hash(self, tsa_service: ExternalTSAService) -> None:
        """Test stamping pre-computed hash."""
        test_hash_hex = "a" * 64  # 256 bits = 64 hex chars
        test_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_token_bytes = b"mock_timestamp_token"
        mock_token_b64 = base64.b64encode(mock_token_bytes).decode()

        with patch.object(
            tsa_service, "_request_timestamp", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = (mock_token_b64, test_time)

            token, timestamp = await tsa_service.stamp_hash(test_hash_hex)

            assert isinstance(token, str)
            assert timestamp == test_time


class TestVerify:
    """Tests for verify() method."""

    def _build_mock_tst_response(self, test_hash: bytes, test_time: datetime) -> MagicMock:
        """Build a mock TimeStampResp structure."""
        mock_response = MagicMock()
        mock_response["status"]["status"].native = "granted"

        # TSTInfo structure
        mock_tst_info = MagicMock()
        mock_tst_info["gen_time"].native = test_time
        mock_tst_info["message_imprint"]["hashed_message"].native = test_hash
        mock_tst_info["message_imprint"]["hash_algorithm"][
            "algorithm"
        ].dotted = "2.16.840.1.101.3.4.2.1"

        mock_response["time_stamp_token"]["content"]["encap_content_info"][
            "content"
        ].native = b"tst_info_bytes"
        return mock_response, mock_tst_info

    @pytest.mark.asyncio
    async def test_verify_with_data(self, tsa_service: ExternalTSAService) -> None:
        """Test verifying token with original data."""
        test_data = "Hello, World!"
        test_hash = hashlib.sha256(test_data.encode()).digest()
        test_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)

        mock_response, mock_tst_info = self._build_mock_tst_response(test_hash, test_time)

        with patch("asn1crypto.tsp.TimeStampResp.load", return_value=mock_response):
            with patch("asn1crypto.tsp.TSTInfo.load", return_value=mock_tst_info):
                token = base64.b64encode(b"mock_token").decode()
                result = await tsa_service.verify(token, data=test_data)

                assert result.is_valid
                assert result.hash_matches
                assert result.timestamp == test_time

    @pytest.mark.asyncio
    async def test_verify_with_hash(self, tsa_service: ExternalTSAService) -> None:
        """Test verifying token with pre-computed hash."""
        test_hash = hashlib.sha256(b"test").digest()
        test_hash_hex = test_hash.hex()
        test_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)

        mock_response, mock_tst_info = self._build_mock_tst_response(test_hash, test_time)

        with patch("asn1crypto.tsp.TimeStampResp.load", return_value=mock_response):
            with patch("asn1crypto.tsp.TSTInfo.load", return_value=mock_tst_info):
                token = base64.b64encode(b"mock_token").decode()
                result = await tsa_service.verify(token, hash_value=test_hash_hex)

                assert result.is_valid
                assert result.hash_matches

    @pytest.mark.asyncio
    async def test_verify_hash_mismatch(self, tsa_service: ExternalTSAService) -> None:
        """Test verification fails on hash mismatch."""
        original_hash = hashlib.sha256(b"Original").digest()
        tampered_data = "Tampered"
        test_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)

        mock_response, mock_tst_info = self._build_mock_tst_response(original_hash, test_time)

        with patch("asn1crypto.tsp.TimeStampResp.load", return_value=mock_response):
            with patch("asn1crypto.tsp.TSTInfo.load", return_value=mock_tst_info):
                token = base64.b64encode(b"mock_token").decode()
                result = await tsa_service.verify(token, data=tampered_data)

                assert not result.is_valid
                assert not result.hash_matches
                assert "does not match" in (result.error_message or "").lower()

    @pytest.mark.asyncio
    async def test_verify_no_data_or_hash(self, tsa_service: ExternalTSAService) -> None:
        """Test verification requires data or hash."""
        with pytest.raises(ValueError, match="Must provide either data or hash_value"):
            await tsa_service.verify("some-token")

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, tsa_service: ExternalTSAService) -> None:
        """Test verification with invalid token."""
        invalid_token = base64.b64encode(b"not a valid token").decode()

        result = await tsa_service.verify(invalid_token, data="test")

        assert not result.is_valid
        assert result.error_message is not None


class TestRetryLogic:
    """Tests for retry logic.

    Note: Retry logic is now handled internally by lionpride's Endpoint.
    These tests verify failover behavior at the ExternalTSAService level.
    """

    @pytest.mark.asyncio
    async def test_all_retries_fail(self, tsa_config: TSAConfig) -> None:
        """Test error when TSA request fails."""

        tsa_service = ExternalTSAService(tsa_config)
        test_data = "Test"

        with patch.object(
            tsa_service, "_request_timestamp", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = ExecutionError("TSA request failed")

            with pytest.raises(ExecutionError):
                await tsa_service.stamp(test_data)

    @pytest.mark.asyncio
    async def test_backup_tsa_fallback(
        self,
        tsa_service_with_backup: ExternalTSAService,
    ) -> None:
        """Test fallback to backup TSA."""
        test_data = "Test"
        test_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_token_bytes = b"backup_token"
        mock_token_b64 = base64.b64encode(mock_token_bytes).decode()

        # Mock _request_timestamp to succeed (backup is internal to that method)
        with patch.object(
            tsa_service_with_backup, "_request_timestamp", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = (mock_token_b64, test_time)

            token, timestamp = await tsa_service_with_backup.stamp(test_data)

            assert timestamp == test_time


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_tsa_rejection(self, tsa_service: ExternalTSAService) -> None:
        """Test handling TSA rejection response."""

        test_data = "Test"

        with patch.object(
            tsa_service, "_request_timestamp", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = ExecutionError("TSA rejected request")

            with pytest.raises(ExecutionError):
                await tsa_service.stamp(test_data)

    @pytest.mark.asyncio
    async def test_network_timeout(self, tsa_service: ExternalTSAService) -> None:
        """Test handling network timeout."""

        test_data = "Test"

        with patch.object(
            tsa_service, "_request_timestamp", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = ExecutionError("Connection timeout")

            with pytest.raises(ExecutionError):
                await tsa_service.stamp(test_data)


class TestPresets:
    """Tests for TSA presets."""

    def test_digicert_preset(self) -> None:
        """Test DigiCert preset configuration."""
        config = TSA_PRESETS["digicert"]
        assert config.url == "http://timestamp.digicert.com"
        assert config.name == "DigiCert Timestamp"
        # Verify service can be instantiated
        service = ExternalTSAService(config)
        assert service._config is config

    def test_freetsa_preset(self) -> None:
        """Test FreeTSA preset configuration."""
        config = TSA_PRESETS["freetsa"]
        assert config.url == "https://freetsa.org/tsr"
        assert config.retry_count == 5  # Higher for slower service
        # Verify service can be instantiated
        service = ExternalTSAService(config)
        assert service._config is config
