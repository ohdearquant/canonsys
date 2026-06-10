# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""Batch timestamping via Merkle trees.

IMPORTANT: Merkle-root timestamping proves "this set existed NO LATER THAN T."
It does NOT prove exact time each individual leaf was created.

Recommended usage:
- Merkle batching: Metrics, routine gate checks, periodic logs
- Per-artifact timestamps: Consents, adverse action notices
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from kron.utils import HashAlgorithm, now_utc

from .merkle import MerkleProof, MerkleTree

if TYPE_CHECKING:
    from .base import TimestampService

__all__ = ["BatchTimestampRequest", "BatchTimestampResult", "BatchTimestampService"]


@dataclass
class BatchTimestampRequest:
    """Request to timestamp batch of hashes via Merkle tree.

    Attributes:
        request_id: Unique identifier for this batch request
        hash_values: List of hex-encoded hashes to timestamp
        hash_algorithm: Algorithm used to create hash_values
        batch_type: Type of batch for audit trail
    """

    request_id: UUID
    hash_values: list[str]
    hash_algorithm: HashAlgorithm
    batch_type: Literal["routine", "audit", "metrics"] = "routine"

    @classmethod
    def create(
        cls,
        hash_values: list[str],
        *,
        hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256,
        batch_type: Literal["routine", "audit", "metrics"] = "routine",
    ) -> BatchTimestampRequest:
        """Create new batch request with generated ID."""
        return cls(
            request_id=uuid4(),
            hash_values=hash_values,
            hash_algorithm=hash_algorithm,
            batch_type=batch_type,
        )


@dataclass
class BatchTimestampResult:
    """Result of batch timestamping operation.

    Attributes:
        request_id: Original request identifier
        merkle_root: Root hash of Merkle tree
        merkle_root_token: Base64-encoded TSA token for root
        merkle_root_timestamp: Timestamp from TSA
        individual_proofs: Map of hash -> MerkleProof for each item
        created_at: When batch was processed
    """

    request_id: UUID
    merkle_root: str
    merkle_root_token: str
    merkle_root_timestamp: datetime
    individual_proofs: dict[str, MerkleProof]
    created_at: datetime = field(default_factory=now_utc)

    @property
    def item_count(self) -> int:
        """Get number of items in batch."""
        return len(self.individual_proofs)

    def get_proof(self, hash_value: str) -> MerkleProof | None:
        """Get proof for specific hash."""
        return self.individual_proofs.get(hash_value)


class BatchTimestampService:
    """Optimized batch timestamping using Merkle trees.

    Instead of requesting individual timestamps for each artifact,
    builds a Merkle tree and timestamps only the root.

    Example:
        batch_service = BatchTimestampService(tsa_service)
        request = BatchTimestampRequest.create(
            hash_values=["abc123...", "def456...", "ghi789..."],
        )
        result = await batch_service.timestamp_batch(request)
    """

    def __init__(self, tsa_service: TimestampService) -> None:
        """Initialize batch timestamp service."""
        self._tsa = tsa_service

    async def timestamp_batch(
        self,
        request: BatchTimestampRequest,
    ) -> BatchTimestampResult:
        """Timestamp batch of hashes via Merkle root.

        Args:
            request: Batch timestamp request

        Returns:
            BatchTimestampResult with root token and individual proofs

        Raises:
            ValueError: If request has no hash values
            RuntimeError: If TSA request fails
        """
        if not request.hash_values:
            raise ValueError("Cannot timestamp empty batch")

        # Build Merkle tree
        tree = MerkleTree(request.hash_values)

        # Timestamp root
        root_token, root_timestamp = await self._tsa.stamp_hash(
            tree.root,
            hash_algorithm=request.hash_algorithm,
        )

        # Generate proofs for each leaf
        proofs = {hash_val: tree.get_proof(hash_val) for hash_val in request.hash_values}

        return BatchTimestampResult(
            request_id=request.request_id,
            merkle_root=tree.root,
            merkle_root_token=root_token,
            merkle_root_timestamp=root_timestamp,
            individual_proofs=proofs,
        )

    def verify_inclusion(
        self,
        leaf_hash: str,
        proof: MerkleProof,
        expected_root: str,
    ) -> bool:
        """Verify item inclusion in timestamped batch.

        Args:
            leaf_hash: Hash of item to verify
            proof: MerkleProof from original batch
            expected_root: Expected Merkle root

        Returns:
            True if proof is valid
        """
        return proof.leaf_hash == leaf_hash and proof.root_hash == expected_root and proof.verify()
