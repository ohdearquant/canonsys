# Copyright (c) 2026 HaiyangLi
# SPDX-License-Identifier: Apache-2.0
"""Tests for evidence/timestamp/batch.py module.

Tests validate batch timestamping via Merkle trees for efficient
high-volume timestamp operations.

Exports Tested (3 symbols):
    - BatchTimestampRequest: Request to timestamp batch of hashes
    - BatchTimestampResult: Result with root token and individual proofs
    - BatchTimestampService: Service for batch timestamping via Merkle trees

ADR Reference: ADR-201-timestamp

IMPORTANT (per ChatGPT Pro validation):
    Merkle-root timestamping proves "this set existed NO LATER THAN T."
    It does NOT prove exact time each individual leaf was created.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from canon.utils.tsa.batch import (
    BatchTimestampRequest,
    BatchTimestampResult,
    BatchTimestampService,
)
from canon.utils.tsa.merkle import MerkleProof, MerkleTree
from kron.utils import HashAlgorithm

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_hashes() -> list[str]:
    """Sample hash values for batch testing."""
    return [
        "a" * 64,  # Hash 1
        "b" * 64,  # Hash 2
        "c" * 64,  # Hash 3
        "d" * 64,  # Hash 4
    ]


@pytest.fixture
def single_hash() -> list[str]:
    """Single hash for edge case testing."""
    return ["e" * 64]


@pytest.fixture
def mock_tsa_service() -> AsyncMock:
    """Create mock TSA service for testing."""
    service = AsyncMock()
    service.stamp_hash = AsyncMock(
        return_value=(
            "base64_encoded_token_mock",
            datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )
    )
    return service


@pytest.fixture
def batch_service(mock_tsa_service: AsyncMock) -> BatchTimestampService:
    """Create BatchTimestampService with mock TSA."""
    return BatchTimestampService(mock_tsa_service)


# =============================================================================
# BatchTimestampRequest Tests
# =============================================================================


class TestBatchTimestampRequest:
    """Tests for BatchTimestampRequest dataclass."""

    def test_create_basic(self, sample_hashes: list[str]) -> None:
        """Test creating batch request with defaults."""
        request = BatchTimestampRequest.create(sample_hashes)

        assert isinstance(request.request_id, UUID)
        assert request.hash_values == sample_hashes
        assert request.hash_algorithm == HashAlgorithm.SHA256
        assert request.batch_type == "routine"

    def test_create_with_algorithm(self, sample_hashes: list[str]) -> None:
        """Test creating batch request with custom algorithm."""
        request = BatchTimestampRequest.create(
            sample_hashes,
            hash_algorithm=HashAlgorithm.SHA384,
        )

        assert request.hash_algorithm == HashAlgorithm.SHA384

    def test_create_with_batch_type_audit(self, sample_hashes: list[str]) -> None:
        """Test creating batch request with audit type."""
        request = BatchTimestampRequest.create(
            sample_hashes,
            batch_type="audit",
        )

        assert request.batch_type == "audit"

    def test_create_with_batch_type_metrics(self, sample_hashes: list[str]) -> None:
        """Test creating batch request with metrics type."""
        request = BatchTimestampRequest.create(
            sample_hashes,
            batch_type="metrics",
        )

        assert request.batch_type == "metrics"

    def test_create_generates_unique_ids(self, sample_hashes: list[str]) -> None:
        """Test that each create() generates unique request_id."""
        request1 = BatchTimestampRequest.create(sample_hashes)
        request2 = BatchTimestampRequest.create(sample_hashes)

        assert request1.request_id != request2.request_id

    def test_direct_instantiation(self, sample_hashes: list[str]) -> None:
        """Test direct instantiation with explicit ID."""
        explicit_id = uuid4()
        request = BatchTimestampRequest(
            request_id=explicit_id,
            hash_values=sample_hashes,
            hash_algorithm=HashAlgorithm.SHA256,
            batch_type="routine",
        )

        assert request.request_id == explicit_id

    def test_create_single_hash(self, single_hash: list[str]) -> None:
        """Test creating batch request with single hash."""
        request = BatchTimestampRequest.create(single_hash)

        assert len(request.hash_values) == 1

    def test_create_empty_list(self) -> None:
        """Test creating batch request with empty list."""
        request = BatchTimestampRequest.create([])

        assert request.hash_values == []


# =============================================================================
# BatchTimestampResult Tests
# =============================================================================


class TestBatchTimestampResult:
    """Tests for BatchTimestampResult dataclass."""

    def test_item_count_property(self, sample_hashes: list[str]) -> None:
        """Test item_count returns correct number."""
        tree = MerkleTree(sample_hashes)
        proofs = {h: tree.get_proof(h) for h in sample_hashes}

        result = BatchTimestampResult(
            request_id=uuid4(),
            merkle_root=tree.root,
            merkle_root_token="mock_token",
            merkle_root_timestamp=datetime.now(UTC),
            individual_proofs=proofs,
        )

        assert result.item_count == 4

    def test_get_proof_existing(self, sample_hashes: list[str]) -> None:
        """Test getting proof for existing hash."""
        tree = MerkleTree(sample_hashes)
        proofs = {h: tree.get_proof(h) for h in sample_hashes}

        result = BatchTimestampResult(
            request_id=uuid4(),
            merkle_root=tree.root,
            merkle_root_token="mock_token",
            merkle_root_timestamp=datetime.now(UTC),
            individual_proofs=proofs,
        )

        proof = result.get_proof(sample_hashes[0])

        assert proof is not None
        assert proof.leaf_hash == sample_hashes[0]

    def test_get_proof_nonexistent(self, sample_hashes: list[str]) -> None:
        """Test getting proof for nonexistent hash returns None."""
        tree = MerkleTree(sample_hashes)
        proofs = {h: tree.get_proof(h) for h in sample_hashes}

        result = BatchTimestampResult(
            request_id=uuid4(),
            merkle_root=tree.root,
            merkle_root_token="mock_token",
            merkle_root_timestamp=datetime.now(UTC),
            individual_proofs=proofs,
        )

        proof = result.get_proof("nonexistent" + "0" * 54)

        assert proof is None

    def test_created_at_default(self, sample_hashes: list[str]) -> None:
        """Test that created_at defaults to current time."""
        tree = MerkleTree(sample_hashes)
        proofs = {h: tree.get_proof(h) for h in sample_hashes}

        before = datetime.now(UTC)
        result = BatchTimestampResult(
            request_id=uuid4(),
            merkle_root=tree.root,
            merkle_root_token="mock_token",
            merkle_root_timestamp=datetime.now(UTC),
            individual_proofs=proofs,
        )
        after = datetime.now(UTC)

        assert before <= result.created_at <= after

    def test_all_proofs_verify(self, sample_hashes: list[str]) -> None:
        """Test that all proofs in result are valid."""
        tree = MerkleTree(sample_hashes)
        proofs = {h: tree.get_proof(h) for h in sample_hashes}

        result = BatchTimestampResult(
            request_id=uuid4(),
            merkle_root=tree.root,
            merkle_root_token="mock_token",
            merkle_root_timestamp=datetime.now(UTC),
            individual_proofs=proofs,
        )

        for hash_val in sample_hashes:
            proof = result.get_proof(hash_val)
            assert proof is not None
            assert proof.verify()


# =============================================================================
# BatchTimestampService Tests
# =============================================================================


class TestBatchTimestampService:
    """Tests for BatchTimestampService class."""

    def test_init(self, mock_tsa_service: AsyncMock) -> None:
        """Test service initialization."""
        service = BatchTimestampService(mock_tsa_service)

        assert service._tsa is mock_tsa_service

    @pytest.mark.asyncio
    async def test_timestamp_batch_basic(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
        mock_tsa_service: AsyncMock,
    ) -> None:
        """Test basic batch timestamping."""
        request = BatchTimestampRequest.create(sample_hashes)

        result = await batch_service.timestamp_batch(request)

        assert result.request_id == request.request_id
        assert len(result.merkle_root) == 64
        assert result.merkle_root_token == "base64_encoded_token_mock"
        assert result.merkle_root_timestamp == datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_timestamp_batch_calls_tsa_once(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
        mock_tsa_service: AsyncMock,
    ) -> None:
        """Test that TSA is called exactly once for batch."""
        request = BatchTimestampRequest.create(sample_hashes)

        await batch_service.timestamp_batch(request)

        # Should only call stamp_hash once (for the Merkle root)
        mock_tsa_service.stamp_hash.assert_called_once()

    @pytest.mark.asyncio
    async def test_timestamp_batch_passes_correct_root(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
        mock_tsa_service: AsyncMock,
    ) -> None:
        """Test that correct Merkle root is sent to TSA."""
        request = BatchTimestampRequest.create(sample_hashes)
        expected_tree = MerkleTree(sample_hashes)

        await batch_service.timestamp_batch(request)

        # Verify the root hash passed to TSA
        call_args = mock_tsa_service.stamp_hash.call_args
        assert call_args[0][0] == expected_tree.root

    @pytest.mark.asyncio
    async def test_timestamp_batch_passes_algorithm(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
        mock_tsa_service: AsyncMock,
    ) -> None:
        """Test that hash algorithm is passed to TSA."""
        request = BatchTimestampRequest.create(
            sample_hashes,
            hash_algorithm=HashAlgorithm.SHA384,
        )

        await batch_service.timestamp_batch(request)

        call_args = mock_tsa_service.stamp_hash.call_args
        assert call_args.kwargs["hash_algorithm"] == HashAlgorithm.SHA384

    @pytest.mark.asyncio
    async def test_timestamp_batch_generates_proofs(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
    ) -> None:
        """Test that individual proofs are generated for each hash."""
        request = BatchTimestampRequest.create(sample_hashes)

        result = await batch_service.timestamp_batch(request)

        assert result.item_count == len(sample_hashes)
        for hash_val in sample_hashes:
            proof = result.get_proof(hash_val)
            assert proof is not None

    @pytest.mark.asyncio
    async def test_timestamp_batch_proofs_are_valid(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
    ) -> None:
        """Test that all generated proofs verify correctly."""
        request = BatchTimestampRequest.create(sample_hashes)

        result = await batch_service.timestamp_batch(request)

        for hash_val in sample_hashes:
            proof = result.get_proof(hash_val)
            assert proof is not None
            assert proof.verify()
            assert proof.root_hash == result.merkle_root

    @pytest.mark.asyncio
    async def test_timestamp_batch_single_item(
        self,
        batch_service: BatchTimestampService,
        single_hash: list[str],
    ) -> None:
        """Test batch timestamping with single item."""
        request = BatchTimestampRequest.create(single_hash)

        result = await batch_service.timestamp_batch(request)

        assert result.item_count == 1
        proof = result.get_proof(single_hash[0])
        assert proof is not None
        assert proof.verify()

    @pytest.mark.asyncio
    async def test_timestamp_batch_empty_raises_error(
        self,
        batch_service: BatchTimestampService,
    ) -> None:
        """Test that empty batch raises ValueError."""
        request = BatchTimestampRequest.create([])

        with pytest.raises(ValueError, match="Cannot timestamp empty batch"):
            await batch_service.timestamp_batch(request)

    @pytest.mark.asyncio
    async def test_timestamp_batch_preserves_request_id(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
    ) -> None:
        """Test that result preserves request ID for correlation."""
        request = BatchTimestampRequest.create(sample_hashes)

        result = await batch_service.timestamp_batch(request)

        assert result.request_id == request.request_id


# =============================================================================
# BatchTimestampService verify_inclusion Tests
# =============================================================================


class TestBatchTimestampServiceVerifyInclusion:
    """Tests for verify_inclusion method."""

    def test_verify_inclusion_valid(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
    ) -> None:
        """Test verifying valid inclusion."""
        tree = MerkleTree(sample_hashes)
        hash_to_verify = sample_hashes[1]
        proof = tree.get_proof(hash_to_verify)

        is_valid = batch_service.verify_inclusion(
            leaf_hash=hash_to_verify,
            proof=proof,
            expected_root=tree.root,
        )

        assert is_valid is True

    def test_verify_inclusion_wrong_root(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
    ) -> None:
        """Test verification fails with wrong expected root."""
        tree = MerkleTree(sample_hashes)
        hash_to_verify = sample_hashes[0]
        proof = tree.get_proof(hash_to_verify)

        is_valid = batch_service.verify_inclusion(
            leaf_hash=hash_to_verify,
            proof=proof,
            expected_root="wrong" + "0" * 59,
        )

        assert is_valid is False

    def test_verify_inclusion_wrong_leaf_hash(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
    ) -> None:
        """Test verification fails when leaf hash doesn't match proof."""
        tree = MerkleTree(sample_hashes)
        proof = tree.get_proof(sample_hashes[0])

        is_valid = batch_service.verify_inclusion(
            leaf_hash="different" + "0" * 55,  # Different from proof.leaf_hash
            proof=proof,
            expected_root=tree.root,
        )

        assert is_valid is False

    def test_verify_inclusion_tampered_proof(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
    ) -> None:
        """Test verification fails with tampered proof path."""
        tree = MerkleTree(sample_hashes)
        original_proof = tree.get_proof(sample_hashes[0])

        # Create tampered proof with wrong sibling hash
        tampered_path = list(original_proof.proof_path)
        if tampered_path:
            tampered_path[0] = ("f" * 64, tampered_path[0][1])

        tampered_proof = MerkleProof(
            leaf_hash=original_proof.leaf_hash,
            proof_path=tuple(tampered_path),
            root_hash=original_proof.root_hash,
            leaf_index=original_proof.leaf_index,
        )

        is_valid = batch_service.verify_inclusion(
            leaf_hash=sample_hashes[0],
            proof=tampered_proof,
            expected_root=tree.root,
        )

        assert is_valid is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestBatchTimestampIntegration:
    """Integration tests for complete batch timestamp workflows."""

    @pytest.mark.asyncio
    async def test_complete_batch_workflow(
        self,
        batch_service: BatchTimestampService,
        sample_hashes: list[str],
    ) -> None:
        """Test complete workflow: request -> timestamp -> verify."""
        # 1. Create request
        request = BatchTimestampRequest.create(sample_hashes, batch_type="audit")

        # 2. Execute batch timestamp
        result = await batch_service.timestamp_batch(request)

        # 3. Verify each item's inclusion
        for hash_val in sample_hashes:
            proof = result.get_proof(hash_val)
            assert proof is not None

            is_valid = batch_service.verify_inclusion(
                leaf_hash=hash_val,
                proof=proof,
                expected_root=result.merkle_root,
            )
            assert is_valid

    @pytest.mark.asyncio
    async def test_batch_different_from_individual_order(
        self,
        batch_service: BatchTimestampService,
    ) -> None:
        """Test that different hash order produces different root."""
        hashes_original = ["a" * 64, "b" * 64, "c" * 64]
        hashes_reversed = ["c" * 64, "b" * 64, "a" * 64]

        request1 = BatchTimestampRequest.create(hashes_original)
        request2 = BatchTimestampRequest.create(hashes_reversed)

        result1 = await batch_service.timestamp_batch(request1)
        result2 = await batch_service.timestamp_batch(request2)

        # Different order produces different Merkle root
        assert result1.merkle_root != result2.merkle_root

    @pytest.mark.asyncio
    async def test_odd_number_of_hashes(
        self,
        batch_service: BatchTimestampService,
    ) -> None:
        """Test batch with odd number of hashes (tests padding)."""
        odd_hashes = ["a" * 64, "b" * 64, "c" * 64]  # 3 hashes

        request = BatchTimestampRequest.create(odd_hashes)
        result = await batch_service.timestamp_batch(request)

        assert result.item_count == 3
        for hash_val in odd_hashes:
            proof = result.get_proof(hash_val)
            assert proof is not None
            assert proof.verify()

    @pytest.mark.asyncio
    async def test_large_batch(
        self,
        batch_service: BatchTimestampService,
    ) -> None:
        """Test batch with many items."""
        # Generate 100 unique hashes
        large_batch = [f"{i:064x}" for i in range(100)]

        request = BatchTimestampRequest.create(large_batch)
        result = await batch_service.timestamp_batch(request)

        assert result.item_count == 100
        # Spot check a few proofs
        for i in [0, 49, 99]:
            proof = result.get_proof(large_batch[i])
            assert proof is not None
            assert proof.verify()

    @pytest.mark.asyncio
    async def test_proof_size_is_logarithmic(
        self,
        batch_service: BatchTimestampService,
    ) -> None:
        """Test that proof size grows logarithmically with batch size.

        For N items, proof should have ~log2(N) steps.
        """
        # 16 items -> 4 proof steps
        batch_16 = [f"{i:064x}" for i in range(16)]
        # 64 items -> 6 proof steps
        batch_64 = [f"{i:064x}" for i in range(64)]

        request_16 = BatchTimestampRequest.create(batch_16)
        request_64 = BatchTimestampRequest.create(batch_64)

        result_16 = await batch_service.timestamp_batch(request_16)
        result_64 = await batch_service.timestamp_batch(request_64)

        proof_16 = result_16.get_proof(batch_16[0])
        proof_64 = result_64.get_proof(batch_64[0])

        assert proof_16 is not None
        assert proof_64 is not None

        # 16 items: depth = 4, 64 items: depth = 6
        # Proof path length should be tree depth - 1
        assert len(proof_16.proof_path) == 4
        assert len(proof_64.proof_path) == 6
