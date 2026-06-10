# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""Abstract timestamp service interface.

Per RFC 3161, a TSA provides cryptographic proof that a document
existed at a particular time, which is essential for FRE 902(13)
self-authentication of electronic records.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from kron.utils import HashAlgorithm

from .types import TimestampVerificationResult

__all__ = ["TimestampService"]


class TimestampService(ABC):
    """Abstract timestamp service interface.

    Implementations may use:
    - External TSA (DigiCert, Entrust, FreeTSA)
    - Internal PKI with HSM-backed TSA
    - Cloud KMS with timestamping capability

    Example:
        class MyTSA(TimestampService):
            async def stamp(self, data, *, hash_algorithm=HashAlgorithm.SHA256):
                # Implement TSA request
                ...

        tsa = MyTSA(url="http://timestamp.digicert.com")
        token, timestamp = await tsa.stamp(document_bytes)
    """

    @abstractmethod
    async def stamp(
        self,
        data: bytes | str,
        *,
        hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> tuple[str, datetime]:
        """Request timestamp for data.

        Computes hash of data and sends timestamp request to TSA.
        Returns base64-encoded token suitable for storage and the
        extracted timestamp.

        Args:
            data: Data to timestamp (will be hashed)
            hash_algorithm: Hash algorithm to use

        Returns:
            Tuple of (base64-encoded token, timestamp datetime UTC)

        Raises:
            RuntimeError: If TSA request fails after retries
        """
        ...

    @abstractmethod
    async def stamp_hash(
        self,
        hash_value: str,
        *,
        hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> tuple[str, datetime]:
        """Request timestamp for pre-computed hash.

        Use when hash is already computed (e.g., from hash chain).

        Args:
            hash_value: Hex-encoded hash to timestamp
            hash_algorithm: Hash algorithm that produced hash_value

        Returns:
            Tuple of (base64-encoded token, timestamp datetime UTC)

        Raises:
            RuntimeError: If TSA request fails after retries
        """
        ...

    @abstractmethod
    async def verify(
        self,
        token: str,
        data: bytes | str | None = None,
        hash_value: str | None = None,
    ) -> TimestampVerificationResult:
        """Verify timestamp token.

        Verifies:
        1. Token format is valid RFC 3161
        2. TSA signature is valid (if certificate available)
        3. Message imprint matches data/hash_value

        Must provide either data or hash_value.

        Args:
            token: Base64-encoded timestamp token
            data: Original data to verify against (optional)
            hash_value: Pre-computed hash to verify against (optional)

        Returns:
            TimestampVerificationResult with verification details

        Raises:
            ValueError: If neither data nor hash_value provided
        """
        ...
