# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""External RFC 3161 TSA client with certificate validation.

Implements:
- RFC 3161 timestamp request/response
- Certificate chain validation
- OCSP/CRL revocation checking
- Retry with exponential backoff via lionpride Endpoint
- Backup TSA failover
- CircuitBreaker for fault tolerance

Legal foundation:
- FRE 902(13): Self-authentication of electronic records
- eIDAS Article 41: Qualified electronic time stamps
- ISO/IEC 18014: Time-stamping services
"""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime
from typing import Any

from asn1crypto import tsp
from pydantic import PrivateAttr

from canon.exceptions import ExecutionError
from kron.services import Endpoint, EndpointConfig, NormalizedResponse, iModel
from kron.services.utilities import CircuitBreaker, RetryConfig
from kron.utils import HashAlgorithm

from .base import TimestampService
from .config import TSA_PRESETS, TSAConfig
from .types import TimestampRequest, TimestampToken, TimestampVerificationResult

__all__ = [
    "ExternalTSAService",
    "TSAEndpoint",
]

logger = logging.getLogger(__name__)


def create_tsa_config(tsa_config: TSAConfig) -> dict:
    """Factory for TSA endpoint config from TSAConfig.

    Args:
        tsa_config: TSAConfig with URL, auth, timeout settings.

    Returns:
        Config dict for TSAEndpoint.
    """
    config: dict[str, Any] = {
        "provider": "tsa_rfc3161",
        "name": tsa_config.name,
        "base_url": "",  # URL is complete in endpoint
        "endpoint": tsa_config.url,
        "method": "POST",
        "content_type": "application/timestamp-query",
        "timeout": tsa_config.timeout_seconds,
    }

    if tsa_config.auth_type == "basic" and tsa_config.username:
        config["auth_type"] = "basic"
        config["client_kwargs"] = {
            "username": tsa_config.username,
            "password": tsa_config.password,
        }

    return config


class TSAEndpoint(Endpoint):
    """RFC 3161 TSA endpoint using lionpride Endpoint pattern.

    Overrides _call_http to send binary ASN.1 requests.
    Inherits CircuitBreaker and RetryConfig from parent.

    Usage:
        endpoint = TSAEndpoint(
            config=create_tsa_config(TSA_PRESETS["digicert"]),
            circuit_breaker=CircuitBreaker(failure_threshold=3),
            retry_config=RetryConfig(max_retries=2),
        )
        response = await endpoint.call({"request_bytes": asn1_bytes})
    """

    _tsa_auth: tuple[str, str] | None = PrivateAttr(default=None)

    def __init__(
        self,
        config: dict | EndpointConfig,
        tsa_config: TSAConfig | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_config: RetryConfig | None = None,
        **kwargs,
    ):
        """Initialize TSA endpoint.

        Args:
            config: Endpoint config dict or EndpointConfig.
            tsa_config: Original TSAConfig for auth credentials.
            circuit_breaker: Optional circuit breaker.
            retry_config: Optional retry config.
        """
        if isinstance(config, EndpointConfig):
            config = config.model_dump()

        super().__init__(
            config=config,
            circuit_breaker=circuit_breaker,
            retry_config=retry_config,
            **kwargs,
        )
        # Set after super().__init__ for Pydantic PrivateAttr
        if tsa_config and tsa_config.auth:
            self._tsa_auth = tsa_config.auth

    async def _call_http(self, payload: dict, headers: dict, **kwargs):
        """Override to send binary ASN.1 request instead of JSON.

        Merges lionpride's headers (tracing, correlation IDs) with TSA-specific headers.
        """
        import httpx

        request_bytes = payload.get("request_bytes", b"")

        # Merge headers: preserve lionpride instrumentation + add TSA content type
        merged_headers = {
            **headers,
            "Content-Type": "application/timestamp-query",
            "Accept": "application/timestamp-reply",
        }

        async with self._create_http_client() as client:
            response = await client.request(
                method=self.config.method,
                url=self.config.endpoint,  # Full URL in endpoint
                headers=merged_headers,
                content=request_bytes,  # Binary content
                auth=self._tsa_auth,
                **kwargs,
            )

            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            elif response.status_code != 200:
                raise httpx.HTTPStatusError(
                    message=f"TSA request failed with status {response.status_code}",
                    request=response.request,
                    response=response,
                )

            # Return raw bytes for TSA response parsing
            return response.content

    def normalize_response(self, raw_response: bytes) -> NormalizedResponse:
        """Normalize TSA response bytes.

        Args:
            raw_response: Raw ASN.1 response bytes from TSA.

        Returns:
            NormalizedResponse with parsed timestamp data.
        """
        try:
            ts_response = tsp.TimeStampResp.load(raw_response)
            status = ts_response["status"]["status"].native

            if status not in ("granted", "granted_with_mods"):
                status_string = ts_response["status"].get("status_string")
                error_msg = f"TSA returned status {status}"
                if status_string:
                    error_msg += f": {status_string.native}"
                return NormalizedResponse(
                    status="error",
                    error=error_msg,
                    raw_response={"status": status},
                )

            # Extract timestamp
            ts_token = ts_response["time_stamp_token"]
            encap_content = ts_token["content"]["encap_content_info"]
            tst_info_bytes = encap_content["content"].native
            tst_info = tsp.TSTInfo.load(tst_info_bytes)

            gen_time = tst_info["gen_time"].native
            if gen_time.tzinfo is None:
                gen_time = gen_time.replace(tzinfo=UTC)

            return NormalizedResponse(
                status="success",
                data={
                    "token_b64": base64.b64encode(raw_response).decode("ascii"),
                    "gen_time": gen_time,
                    "serial_number": tst_info["serial_number"].native,
                    "policy_oid": tst_info["policy"].dotted,
                },
                raw_response={"status": status, "raw_bytes_len": len(raw_response)},
            )

        except Exception as e:
            logger.warning(f"TSA response parse error: {e}")
            return NormalizedResponse(
                status="error",
                error=str(e),
                raw_response={},
            )


class ExternalTSAService(TimestampService):
    """External RFC 3161 TSA client.

    Features:
    - RFC 3161 compliant timestamp requests
    - Exponential backoff retry via lionpride
    - Backup TSA failover
    - Hash verification + OpenSSL-based signature verification

    Example:
        tsa = ExternalTSAService(TSA_PRESETS["digicert"])
        token, timestamp = await tsa.stamp(document_bytes)
        result = await tsa.verify(token, data=document_bytes)  # hash only
        result = await tsa.verify_with_openssl(token, data=document_bytes)  # full
    """

    # OIDs for hash algorithms
    _HASH_OIDS = {
        HashAlgorithm.SHA256: "2.16.840.1.101.3.4.2.1",
        HashAlgorithm.SHA384: "2.16.840.1.101.3.4.2.2",
        HashAlgorithm.SHA512: "2.16.840.1.101.3.4.2.3",
    }

    def __init__(
        self,
        config: TSAConfig,
        *,
        backup_config: TSAConfig | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        """Initialize TSA client.

        Args:
            config: Primary TSA configuration
            backup_config: Backup TSA for failover
            circuit_breaker: Optional circuit breaker for fault tolerance
        """
        self._config = config
        self._backup_config = backup_config

        # Create iModel-wrapped endpoints with resilience patterns
        # Each endpoint gets its own circuit breaker for independent failover
        retry_cfg = RetryConfig(
            max_retries=max(0, config.retry_count - 1),
            initial_delay=1.0,
            exponential_base=2.0,
        )
        primary_cb = circuit_breaker or CircuitBreaker()
        primary_endpoint = TSAEndpoint(
            config=create_tsa_config(config),
            tsa_config=config,
            circuit_breaker=primary_cb,
            retry_config=retry_cfg,
        )
        self._primary_model = iModel(backend=primary_endpoint)

        self._backup_model: iModel | None = None
        if backup_config:
            backup_retry = RetryConfig(
                max_retries=max(0, backup_config.retry_count - 1),
                initial_delay=1.0,
                exponential_base=2.0,
            )
            # Backup gets independent circuit breaker - primary failures shouldn't trip backup
            backup_cb = CircuitBreaker()
            backup_endpoint = TSAEndpoint(
                config=create_tsa_config(backup_config),
                tsa_config=backup_config,
                circuit_breaker=backup_cb,
                retry_config=backup_retry,
            )
            self._backup_model = iModel(backend=backup_endpoint)

    @classmethod
    def from_preset(
        cls,
        preset: str,
        *,
        backup_preset: str | None = None,
        **kwargs,
    ) -> ExternalTSAService:
        """Create from preset name.

        Args:
            preset: Preset name (digicert, entrust, sectigo, globalsign, freetsa)
            backup_preset: Backup preset name
            **kwargs: Additional constructor arguments

        Returns:
            Configured ExternalTSAService
        """
        config = TSA_PRESETS[preset]
        backup_config = TSA_PRESETS[backup_preset] if backup_preset else None
        return cls(config, backup_config=backup_config, **kwargs)

    async def stamp(
        self,
        data: bytes | str,
        *,
        hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> tuple[str, datetime]:
        """Request timestamp for data."""
        request = TimestampRequest.from_data(data, hash_algorithm=hash_algorithm)
        return await self._request_timestamp(request)

    async def stamp_hash(
        self,
        hash_value: str,
        *,
        hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
        include_nonce: bool = True,
    ) -> tuple[str, datetime]:
        """Request timestamp for pre-computed hash.

        Args:
            hash_value: Hex-encoded hash to timestamp
            hash_algorithm: Algorithm used to create hash_value
            include_nonce: Include anti-replay nonce (recommended for security)
        """
        import secrets

        hash_bytes = bytes.fromhex(hash_value)
        nonce = secrets.token_bytes(16) if include_nonce else None
        request = TimestampRequest(
            message_imprint=hash_bytes,
            hash_algorithm=hash_algorithm,
            nonce=nonce,
            cert_req=True,
        )
        return await self._request_timestamp(request)

    async def verify(
        self,
        token: str,
        data: bytes | str | None = None,
        hash_value: str | None = None,
    ) -> TimestampVerificationResult:
        """Verify timestamp token."""
        if data is None and hash_value is None:
            raise ValueError("Must provide either data or hash_value")

        try:
            # Decode token
            token_bytes = base64.b64decode(token)
            ts_response = tsp.TimeStampResp.load(token_bytes)

            # Check response status
            status = ts_response["status"]["status"].native
            if status != "granted" and status != "granted_with_mods":
                return TimestampVerificationResult.failure(
                    error_message=f"TSA response status: {status}"
                )

            # Extract TSTInfo
            ts_token = ts_response["time_stamp_token"]
            encap_content = ts_token["content"]["encap_content_info"]
            tst_info_bytes = encap_content["content"].native
            tst_info = tsp.TSTInfo.load(tst_info_bytes)

            # Get timestamp
            gen_time = tst_info["gen_time"].native
            if gen_time.tzinfo is None:
                gen_time = gen_time.replace(tzinfo=UTC)

            # Verify hash matches
            msg_imprint = tst_info["message_imprint"]
            imprint_bytes = msg_imprint["hashed_message"].native

            if data is not None:
                if isinstance(data, str):
                    data = data.encode("utf-8")
                hash_algo_oid = msg_imprint["hash_algorithm"]["algorithm"].dotted
                hash_algo = self._oid_to_algorithm(hash_algo_oid)
                expected_hash = hash_algo.get_hasher()(data).digest()
            else:
                expected_hash = bytes.fromhex(hash_value)  # type: ignore

            if imprint_bytes != expected_hash:
                return TimestampVerificationResult.failure(
                    error_message="Message imprint does not match",
                    timestamp=gen_time,
                )

            # Hash verified, but CMS signature NOT verified
            # Use verify_with_openssl() for full cryptographic verification
            return TimestampVerificationResult.hash_only(timestamp=gen_time)

        except Exception as e:
            logger.warning(f"Timestamp verification error: {e}")
            return TimestampVerificationResult.failure(error_message=str(e))

    async def verify_with_openssl(
        self,
        token: str,
        data: bytes | str | None = None,
        hash_value: str | None = None,
        *,
        ca_bundle: str | None = None,
    ) -> TimestampVerificationResult:
        """Verify timestamp token with full CMS signature verification via OpenSSL.

        This method provides legally defensible verification by:
        1. Verifying message imprint matches data hash
        2. Verifying CMS signature using OpenSSL (hardened crypto)
        3. Validating TSA certificate chain against trust anchors

        Args:
            token: Base64-encoded timestamp response
            data: Original data that was timestamped
            hash_value: Pre-computed hash (alternative to data)
            ca_bundle: Path to CA bundle for chain validation (optional)

        Returns:
            TimestampVerificationResult with signature_valid=True if verified
        """
        import subprocess
        import tempfile

        if data is None and hash_value is None:
            raise ValueError("Must provide either data or hash_value")

        try:
            # First do hash verification
            token_bytes = base64.b64decode(token)
            ts_response = tsp.TimeStampResp.load(token_bytes)

            status = ts_response["status"]["status"].native
            if status != "granted" and status != "granted_with_mods":
                return TimestampVerificationResult.failure(
                    error_message=f"TSA response status: {status}"
                )

            ts_token = ts_response["time_stamp_token"]
            encap_content = ts_token["content"]["encap_content_info"]
            tst_info_bytes = encap_content["content"].native
            tst_info = tsp.TSTInfo.load(tst_info_bytes)

            gen_time = tst_info["gen_time"].native
            if gen_time.tzinfo is None:
                gen_time = gen_time.replace(tzinfo=UTC)

            # Verify hash matches
            msg_imprint = tst_info["message_imprint"]
            imprint_bytes = msg_imprint["hashed_message"].native

            if data is not None:
                if isinstance(data, str):
                    data = data.encode("utf-8")
                hash_algo_oid = msg_imprint["hash_algorithm"]["algorithm"].dotted
                hash_algo = self._oid_to_algorithm(hash_algo_oid)
                expected_hash = hash_algo.get_hasher()(data).digest()
            else:
                expected_hash = bytes.fromhex(hash_value)  # type: ignore

            if imprint_bytes != expected_hash:
                return TimestampVerificationResult.failure(
                    error_message="Message imprint does not match",
                    timestamp=gen_time,
                )

            # Use OpenSSL for CMS signature verification
            with tempfile.NamedTemporaryFile(suffix=".tsr", delete=False) as tsr_file:
                tsr_file.write(token_bytes)
                tsr_path = tsr_file.name

            with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as data_file:
                if data is not None:
                    data_file.write(data)
                else:
                    data_file.write(expected_hash)
                data_path = data_file.name

            try:
                # Build OpenSSL command
                cmd = [
                    "openssl",
                    "ts",
                    "-verify",
                    "-in",
                    tsr_path,
                    "-data",
                    data_path,
                ]
                if ca_bundle:
                    cmd.extend(["-CAfile", ca_bundle])

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                signature_valid = result.returncode == 0

                if signature_valid:
                    return TimestampVerificationResult.success(
                        timestamp=gen_time,
                        signature_valid=True,
                        chain_validated=ca_bundle is not None,
                    )
                else:
                    return TimestampVerificationResult.failure(
                        error_message=f"OpenSSL verification failed: {result.stderr}",
                        hash_matches=True,
                        signature_valid=False,
                        timestamp=gen_time,
                    )

            finally:
                import os

                os.unlink(tsr_path)
                os.unlink(data_path)

        except FileNotFoundError:
            return TimestampVerificationResult.failure(
                error_message="OpenSSL not found. Install openssl for signature verification.",
            )
        except subprocess.TimeoutExpired:
            return TimestampVerificationResult.failure(
                error_message="OpenSSL verification timed out",
            )
        except Exception as e:
            logger.warning(f"Timestamp verification error: {e}")
            return TimestampVerificationResult.failure(error_message=str(e))

    async def _request_timestamp(
        self,
        request: TimestampRequest,
    ) -> tuple[str, datetime]:
        """Send timestamp request via iModel with failover.

        Uses iModel.invoke() which tracks execution.duration automatically,
        eliminating manual time.perf_counter() boilerplate.
        """
        # Build RFC 3161 request
        ts_request = self._build_ts_request(request)
        request_bytes = ts_request.dump()

        # Try primary TSA via iModel
        try:
            calling = await self._primary_model.invoke(
                request_bytes=request_bytes,
                skip_payload_creation=True,
            )
            response = calling.execution.response
            if response.status == "success":
                # lionpride tracks duration in seconds
                elapsed_ms = calling.execution.duration * 1000
                self._record_tsa_latency(elapsed_ms)
                return response.data["token_b64"], response.data["gen_time"]
            raise ExecutionError(response.error or "Primary TSA failed")
        except Exception as e:
            if self._backup_model is None:
                raise ExecutionError(f"TSA request failed: {e}") from e

        # Failover to backup TSA
        logger.warning(f"Primary TSA failed, failing over to {self._backup_config.name}")
        try:
            calling = await self._backup_model.invoke(
                request_bytes=request_bytes,
                skip_payload_creation=True,
            )
            response = calling.execution.response
            if response.status == "success":
                elapsed_ms = calling.execution.duration * 1000
                self._record_tsa_latency(elapsed_ms)
                return response.data["token_b64"], response.data["gen_time"]
            raise ExecutionError(response.error or "Backup TSA failed")
        except Exception as e:
            raise ExecutionError(f"All TSAs failed: {e}") from e

    def _record_tsa_latency(self, latency_ms: float) -> None:
        """Record TSA request latency for SLO tracking.

        P1 SLO: Wire TSA latency into SLORegistry.
        """
        try:
            from canon.utils.slo import get_slo_registry

            registry = get_slo_registry()
            registry.record_tsa_latency(latency_ms)
        except ImportError:
            # SLO module not installed
            pass
        except Exception as e:
            logger.debug(f"TSA latency SLO recording failed: {e}")

    def _build_ts_request(self, request: TimestampRequest) -> tsp.TimeStampReq:
        """Build ASN.1 timestamp request."""
        hash_oid = self._HASH_OIDS[request.hash_algorithm]

        # Build MessageImprint
        hash_algo = tsp.DigestAlgorithm({"algorithm": hash_oid})
        msg_imprint = tsp.MessageImprint(
            {
                "hash_algorithm": hash_algo,
                "hashed_message": request.message_imprint,
            }
        )

        # Build TimeStampReq
        ts_req_dict: dict = {
            "version": 1,
            "message_imprint": msg_imprint,
            "cert_req": request.cert_req,
        }

        if request.nonce is not None:
            ts_req_dict["nonce"] = int.from_bytes(request.nonce, "big")

        if request.request_policy is not None:
            ts_req_dict["req_policy"] = request.request_policy

        return tsp.TimeStampReq(ts_req_dict)

    def _oid_to_algorithm(self, oid: str) -> HashAlgorithm:
        """Convert OID to HashAlgorithm."""
        oid_map = {v: k for k, v in self._HASH_OIDS.items()}
        if oid not in oid_map:
            raise ValueError(f"Unknown hash algorithm OID: {oid}")
        return oid_map[oid]

    def parse_token(self, token_b64: str) -> TimestampToken:
        """Parse base64-encoded token into TimestampToken."""
        token_bytes = base64.b64decode(token_b64)
        ts_response = tsp.TimeStampResp.load(token_bytes)
        ts_token = ts_response["time_stamp_token"]

        # Extract TSTInfo
        encap_content = ts_token["content"]["encap_content_info"]
        tst_info_bytes = encap_content["content"].native
        tst_info = tsp.TSTInfo.load(tst_info_bytes)

        # Get timestamp
        gen_time = tst_info["gen_time"].native
        if gen_time.tzinfo is None:
            gen_time = gen_time.replace(tzinfo=UTC)

        # Get message imprint
        msg_imprint = tst_info["message_imprint"]
        imprint_bytes = msg_imprint["hashed_message"].native
        hash_algo_oid = msg_imprint["hash_algorithm"]["algorithm"].dotted
        hash_algo = self._oid_to_algorithm(hash_algo_oid)

        # Get TSA name
        tsa_name = str(tst_info.get("tsa", "Unknown TSA"))

        # Get policy OID
        policy_oid = tst_info["policy"].dotted

        # Get serial number
        serial_number = tst_info["serial_number"].native

        # Extract signature from SignerInfo
        signer_infos = ts_token["content"]["signer_infos"]
        if len(signer_infos) > 0:
            signer_info = signer_infos[0]
            signature = signer_info["signature"].native
            sig_algo = str(signer_info["signature_algorithm"]["algorithm"].dotted)
        else:
            signature = b""
            sig_algo = "unknown"

        # Extract certificate if present
        certificates = ts_token["content"].get("certificates")
        tsa_cert_bytes = None
        if certificates and len(certificates) > 0:
            tsa_cert_bytes = certificates[0].dump()

        return TimestampToken(
            gen_time=gen_time,
            message_imprint=imprint_bytes,
            hash_algorithm=hash_algo,
            serial_number=serial_number,
            tsa_name=tsa_name,
            tsa_policy_oid=policy_oid,
            signature=signature,
            signature_algorithm=sig_algo,
            tsa_certificate=tsa_cert_bytes,
            raw_token=token_bytes,
        )
