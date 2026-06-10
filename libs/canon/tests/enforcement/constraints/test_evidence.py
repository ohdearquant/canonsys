"""Tests for evidence constraint functions.

Tests cover:
- evidence_must_be_bound: Evidence binding to case validation
- chain_must_be_intact: Evidence chain integrity verification
- hash_must_match: Content hash verification
- cep_must_be_sealed: CEP sealed status validation

Truth Machine Semantics:
    Each constraint returns Literal[True] on success (invariant holds) or raises
    a typed exception on failure (invariant violated).
"""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest

from canon.enforcement.constraints import (
    cep_must_be_sealed,
    chain_must_be_intact,
    evidence_must_be_bound,
    hash_must_match,
)
from canon.enforcement.exceptions import (
    CEPNotSealedError,
    ChainBrokenError,
    EvidenceNotBoundError,
    HashMismatchError,
)

# =============================================================================
# evidence_must_be_bound Tests
# =============================================================================


class TestEvidenceMustBeBound:
    """Tests for evidence_must_be_bound constraint."""

    def test_bound_to_correct_case_succeeds(self):
        """Test evidence bound to correct case returns True."""
        evidence_id = uuid4()
        case_id = uuid4()

        result = evidence_must_be_bound(evidence_id, case_id, bound_case_id=case_id)
        assert result is True

    def test_not_bound_raises(self):
        """Test unbound evidence raises EvidenceNotBoundError."""
        evidence_id = uuid4()
        case_id = uuid4()

        with pytest.raises(EvidenceNotBoundError) as exc_info:
            evidence_must_be_bound(evidence_id, case_id, bound_case_id=None)

        exc = exc_info.value
        assert exc.evidence_type == "evidence"
        assert "FRCP Rule 37" in exc.regulation

    def test_bound_to_different_case_raises(self):
        """Test evidence bound to different case raises EvidenceNotBoundError."""
        evidence_id = uuid4()
        expected_case_id = uuid4()
        actual_case_id = uuid4()

        with pytest.raises(EvidenceNotBoundError) as exc_info:
            evidence_must_be_bound(evidence_id, expected_case_id, bound_case_id=actual_case_id)

        assert "SOX Section 802" in exc_info.value.regulation

    def test_string_ids_accepted(self):
        """Test string UUIDs are accepted and compared correctly."""
        evidence_id = str(uuid4())
        case_id = str(uuid4())

        result = evidence_must_be_bound(evidence_id, case_id, bound_case_id=case_id)
        assert result is True

    def test_mixed_uuid_and_string(self):
        """Test mixed UUID and string comparison works."""
        case_uuid = uuid4()
        case_str = str(case_uuid)

        result = evidence_must_be_bound(uuid4(), case_uuid, bound_case_id=case_str)
        assert result is True

    def test_empty_string_case_id_treated_as_unbound(self):
        """Test empty bound_case_id handled correctly - raises due to mismatch."""
        # Empty string is truthy but should fail string comparison
        # Empty string != expected case_id, so it raises EvidenceNotBoundError
        with pytest.raises(EvidenceNotBoundError):
            evidence_must_be_bound(uuid4(), uuid4(), bound_case_id="")


# =============================================================================
# chain_must_be_intact Tests
# =============================================================================


class TestChainMustBeIntact:
    """Tests for chain_must_be_intact constraint."""

    def test_empty_chain_succeeds(self):
        """Test empty evidence chain trivially passes."""
        result = chain_must_be_intact([], chain_hashes=[])
        assert result is True

    def test_single_item_chain_succeeds(self):
        """Test single item chain passes with correct linkage."""
        evidence_ids = [uuid4()]
        # First item has no predecessor (prev_hash="")
        chain_hashes = [("", "hash_of_first")]

        result = chain_must_be_intact(evidence_ids, chain_hashes=chain_hashes)
        assert result is True

    def test_valid_chain_succeeds(self):
        """Test valid chain with proper linkage passes."""
        evidence_ids = [uuid4(), uuid4(), uuid4()]
        chain_hashes = [
            ("", "hash1"),  # First: no predecessor
            ("hash1", "hash2"),  # Second: links to first
            ("hash2", "hash3"),  # Third: links to second
        ]

        result = chain_must_be_intact(evidence_ids, chain_hashes=chain_hashes)
        assert result is True

    def test_broken_chain_raises(self):
        """Test broken chain linkage raises ChainBrokenError."""
        evidence_ids = [uuid4(), uuid4()]
        chain_hashes = [
            ("", "hash1"),
            ("wrong_hash", "hash2"),  # Should be "hash1" not "wrong_hash"
        ]

        with pytest.raises(ChainBrokenError) as exc_info:
            chain_must_be_intact(evidence_ids, chain_hashes=chain_hashes)

        exc = exc_info.value
        assert exc.expected_hash == "hash1"
        assert exc.actual_hash == "wrong_hash"

    def test_missing_chain_hashes_raises(self):
        """Test missing chain hashes raises ChainBrokenError."""
        evidence_ids = [uuid4(), uuid4()]

        with pytest.raises(ChainBrokenError) as exc_info:
            chain_must_be_intact(evidence_ids, chain_hashes=None)

        assert "chain_data_required" in exc_info.value.expected_hash

    def test_empty_chain_hashes_with_evidence_raises(self):
        """Test empty chain hashes with evidence items raises."""
        evidence_ids = [uuid4()]

        with pytest.raises(ChainBrokenError):
            chain_must_be_intact(evidence_ids, chain_hashes=[])

    def test_length_mismatch_raises(self):
        """Test mismatched lengths raises ChainBrokenError."""
        evidence_ids = [uuid4(), uuid4(), uuid4()]
        chain_hashes = [("", "hash1"), ("hash1", "hash2")]  # Missing one

        with pytest.raises(ChainBrokenError) as exc_info:
            chain_must_be_intact(evidence_ids, chain_hashes=chain_hashes)

        assert "3_entries" in exc_info.value.expected_hash
        assert "2_entries" in exc_info.value.actual_hash

    def test_first_item_wrong_prev_hash_raises(self):
        """Test first item with non-empty prev_hash raises."""
        evidence_ids = [uuid4()]
        chain_hashes = [("should_be_empty", "hash1")]  # First should have ""

        with pytest.raises(ChainBrokenError) as exc_info:
            chain_must_be_intact(evidence_ids, chain_hashes=chain_hashes)

        assert exc_info.value.expected_hash == "<genesis>"

    def test_long_chain_validation(self):
        """Test validation of longer chain."""
        evidence_ids = [uuid4() for _ in range(10)]
        chain_hashes = []
        prev = ""
        for i in range(10):
            current = f"hash_{i}"
            chain_hashes.append((prev, current))
            prev = current

        result = chain_must_be_intact(evidence_ids, chain_hashes=chain_hashes)
        assert result is True


# =============================================================================
# hash_must_match Tests
# =============================================================================


class TestHashMustMatch:
    """Tests for hash_must_match constraint."""

    def test_matching_hash_succeeds(self):
        """Test content with matching hash returns True."""
        content = b"test content for hashing"
        expected_hash = hashlib.sha256(content).hexdigest()

        result = hash_must_match(content, expected_hash)
        assert result is True

    def test_mismatched_hash_raises(self):
        """Test content with wrong hash raises HashMismatchError."""
        content = b"test content"
        wrong_hash = "0" * 64  # All zeros

        with pytest.raises(HashMismatchError) as exc_info:
            hash_must_match(content, wrong_hash)

        exc = exc_info.value
        assert exc.expected_hash == wrong_hash
        # actual_hash should be computed from content
        assert exc.actual_hash == hashlib.sha256(content).hexdigest()

    def test_case_insensitive_comparison(self):
        """Test hash comparison is case-insensitive."""
        content = b"test"
        hash_lower = hashlib.sha256(content).hexdigest().lower()
        hash_upper = hashlib.sha256(content).hexdigest().upper()

        # Both should pass
        result1 = hash_must_match(content, hash_lower)
        result2 = hash_must_match(content, hash_upper)
        assert result1 is True
        assert result2 is True

    def test_empty_content(self):
        """Test empty content has valid hash."""
        content = b""
        expected_hash = hashlib.sha256(content).hexdigest()

        result = hash_must_match(content, expected_hash)
        assert result is True

    def test_custom_algorithm_md5(self):
        """Test custom hash algorithm (MD5)."""
        content = b"test content"
        expected_hash = hashlib.md5(content).hexdigest()

        result = hash_must_match(content, expected_hash, algorithm="md5")
        assert result is True

    def test_custom_algorithm_sha512(self):
        """Test custom hash algorithm (SHA-512)."""
        content = b"test content"
        expected_hash = hashlib.sha512(content).hexdigest()

        result = hash_must_match(content, expected_hash, algorithm="sha512")
        assert result is True

    def test_wrong_algorithm_raises(self):
        """Test wrong algorithm produces mismatch."""
        content = b"test content"
        sha256_hash = hashlib.sha256(content).hexdigest()

        # Using MD5 algorithm but SHA256 hash should fail
        with pytest.raises(HashMismatchError):
            hash_must_match(content, sha256_hash, algorithm="md5")

    def test_binary_content(self):
        """Test binary content hashing."""
        content = bytes(range(256))  # All byte values
        expected_hash = hashlib.sha256(content).hexdigest()

        result = hash_must_match(content, expected_hash)
        assert result is True

    def test_regulation_in_error(self):
        """Test error contains regulatory reference."""
        with pytest.raises(HashMismatchError) as exc_info:
            hash_must_match(b"test", "wrong" * 16)

        assert "SOX Section 802" in exc_info.value.regulation


# =============================================================================
# cep_must_be_sealed Tests
# =============================================================================


class TestCepMustBeSealed:
    """Tests for cep_must_be_sealed constraint."""

    def test_sealed_status_succeeds(self):
        """Test SEALED status returns True."""
        result = cep_must_be_sealed("SEALED")
        assert result is True

    def test_lowercase_sealed_succeeds(self):
        """Test lowercase 'sealed' is accepted."""
        result = cep_must_be_sealed("sealed")
        assert result is True

    def test_mixed_case_sealed_succeeds(self):
        """Test mixed case 'Sealed' is accepted."""
        result = cep_must_be_sealed("Sealed")
        assert result is True

    def test_draft_status_raises(self):
        """Test DRAFT status raises CEPNotSealedError."""
        with pytest.raises(CEPNotSealedError) as exc_info:
            cep_must_be_sealed("DRAFT")

        exc = exc_info.value
        assert exc.current_status == "DRAFT"
        assert "FCRA Section 1681m" in exc.regulation

    def test_superseded_status_raises(self):
        """Test SUPERSEDED status raises CEPNotSealedError."""
        with pytest.raises(CEPNotSealedError) as exc_info:
            cep_must_be_sealed("SUPERSEDED")

        assert exc_info.value.current_status == "SUPERSEDED"

    def test_pending_status_raises(self):
        """Test PENDING status raises CEPNotSealedError."""
        with pytest.raises(CEPNotSealedError):
            cep_must_be_sealed("PENDING")

    def test_cep_id_in_error(self):
        """Test cep_id is included in error when provided."""
        cep_id = uuid4()

        with pytest.raises(CEPNotSealedError) as exc_info:
            cep_must_be_sealed("DRAFT", cep_id=cep_id)

        assert exc_info.value.cep_id == cep_id

    def test_cep_id_as_string(self):
        """Test cep_id as string is handled."""
        cep_id_str = str(uuid4())

        with pytest.raises(CEPNotSealedError) as exc_info:
            cep_must_be_sealed("DRAFT", cep_id=cep_id_str)

        # Should convert to UUID
        assert exc_info.value.cep_id is not None

    def test_empty_string_status_raises(self):
        """Test empty string status raises CEPNotSealedError."""
        with pytest.raises(CEPNotSealedError):
            cep_must_be_sealed("")

    def test_required_status_in_context(self):
        """Test error context contains required status."""
        with pytest.raises(CEPNotSealedError) as exc_info:
            cep_must_be_sealed("DRAFT")

        assert exc_info.value.context.get("required_status") == "SEALED"


# =============================================================================
# Truth Machine Composition Tests
# =============================================================================


class TestEvidenceComposition:
    """Tests for composing multiple evidence constraints."""

    def test_all_evidence_checks_pass(self):
        """Test all evidence constraints pass in sequence."""
        evidence_id = uuid4()
        case_id = uuid4()
        content = b"evidence content"
        content_hash = hashlib.sha256(content).hexdigest()

        evidence_ids = [evidence_id]
        chain_hashes = [("", content_hash)]

        # If all execute without raising, all invariants hold
        result1 = evidence_must_be_bound(evidence_id, case_id, bound_case_id=case_id)
        result2 = chain_must_be_intact(evidence_ids, chain_hashes=chain_hashes)
        result3 = hash_must_match(content, content_hash)
        result4 = cep_must_be_sealed("SEALED")

        assert result1 is True
        assert result2 is True
        assert result3 is True
        assert result4 is True

    def test_fails_at_first_violation(self):
        """Test composition fails at first violation."""
        with pytest.raises(EvidenceNotBoundError):
            evidence_must_be_bound(uuid4(), uuid4(), bound_case_id=None)
            # Remaining constraints never execute
            hash_must_match(b"test", hashlib.sha256(b"test").hexdigest())

    def test_realistic_evidence_validation_flow(self):
        """Test realistic evidence validation workflow."""
        # Create evidence chain
        evidence_items = []
        chain_hashes = []
        prev_hash = ""

        for i in range(3):
            evidence_id = uuid4()
            content = f"evidence item {i}".encode()
            content_hash = hashlib.sha256(content).hexdigest()

            evidence_items.append(
                {
                    "id": evidence_id,
                    "content": content,
                    "hash": content_hash,
                }
            )
            chain_hashes.append((prev_hash, content_hash))
            prev_hash = content_hash

        # Validate each item
        case_id = uuid4()
        for item in evidence_items:
            evidence_must_be_bound(item["id"], case_id, bound_case_id=case_id)
            hash_must_match(item["content"], item["hash"])

        # Validate chain
        chain_must_be_intact(
            [item["id"] for item in evidence_items],
            chain_hashes=chain_hashes,
        )

        # Validate CEP is sealed
        cep_must_be_sealed("SEALED")
        # All checks passed - evidence package is valid
