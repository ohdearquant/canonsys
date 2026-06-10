# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""Merkle tree implementation for batch timestamping.

Merkle trees enable efficient batch operations:
- Timestamp N items with 1 TSA request (timestamp the root)
- Prove item inclusion without revealing other items
- O(log N) proof size vs O(N) for listing all items

Security Properties:
- Collision-resistant: Cannot forge inclusion proofs
- Privacy-preserving: Prove one item without revealing others
- Efficient: O(log N) proof size and verification time

Regulatory Foundation:
- RFC 3161: Merkle root can be timestamped as single hash
- NIST SP 800-102: Merkle trees for secure audit logs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from kron.utils import HashAlgorithm, compute_hash

__all__ = [
    "MerkleProof",
    "MerkleTree",
    "verify_proof",
]


@dataclass(frozen=True)
class MerkleProof:
    """Merkle inclusion proof for a single item.

    Allows proving an item was included in a timestamped batch
    without revealing other items in the batch.

    Attributes:
        leaf_hash: Hash of the item being proven
        proof_path: Steps from leaf to root [(sibling_hash, position), ...]
        root_hash: Expected Merkle root hash
        leaf_index: Original position in leaf list
        algorithm: Hash algorithm used
    """

    leaf_hash: str
    proof_path: tuple[tuple[str, Literal["left", "right"]], ...]
    root_hash: str
    leaf_index: int
    algorithm: HashAlgorithm = HashAlgorithm.SHA256

    def verify(self) -> bool:
        """Verify this proof against the root hash."""
        return verify_proof(self)

    def to_dict(self) -> dict:
        """Convert proof to dictionary for serialization."""
        return {
            "leaf_hash": self.leaf_hash,
            "proof_path": [{"sibling": s, "position": p} for s, p in self.proof_path],
            "root_hash": self.root_hash,
            "leaf_index": self.leaf_index,
            "algorithm": self.algorithm.value,
        }


def verify_proof(proof: MerkleProof) -> bool:
    """Verify a Merkle inclusion proof.

    Recomputes the root hash from the leaf using the proof path
    and compares to the expected root.

    Args:
        proof: Merkle proof to verify

    Returns:
        True if proof is valid (leaf was in tree with given root)
    """
    current = proof.leaf_hash

    for sibling_hash, position in proof.proof_path:
        if position == "left":
            # Sibling is on left, current is on right
            combined = bytes.fromhex(sibling_hash) + bytes.fromhex(current)
        else:
            # Current is on left, sibling is on right
            combined = bytes.fromhex(current) + bytes.fromhex(sibling_hash)

        current = compute_hash(combined, proof.algorithm)

    return current == proof.root_hash


class MerkleTree:
    """Merkle tree for batch timestamping.

    Builds a binary hash tree from leaf values, allowing efficient
    inclusion proofs. The root hash can be timestamped once via
    RFC 3161, then individual items can prove their inclusion.

    Example:
        tree = MerkleTree(["hash1", "hash2", "hash3"])
        root = tree.root  # Timestamp this with TSA
        proof = tree.get_proof("hash2")
        assert proof.verify()  # Proves hash2 was in batch
    """

    def __init__(
        self,
        hash_values: list[str],
        algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    ) -> None:
        """Initialize Merkle tree from hash values.

        Args:
            hash_values: List of hex-encoded hashes (leaf nodes)
            algorithm: Hash algorithm to use for internal nodes

        Raises:
            ValueError: If hash_values is empty
        """
        if not hash_values:
            raise ValueError("Cannot create MerkleTree from empty list")

        self._algorithm = algorithm
        self._leaves = tuple(hash_values)
        self._leaf_indices: dict[str, int] = {h: i for i, h in enumerate(hash_values)}
        self._tree = self._build_tree()

    @property
    def root(self) -> str:
        """Get Merkle root hash (timestamp this via RFC 3161 TSA)."""
        return self._tree[0][0]

    @property
    def leaves(self) -> tuple[str, ...]:
        """Get leaf hashes."""
        return self._leaves

    @property
    def leaf_count(self) -> int:
        """Get number of leaves."""
        return len(self._leaves)

    @property
    def depth(self) -> int:
        """Get tree depth (number of levels)."""
        return len(self._tree)

    @property
    def algorithm(self) -> HashAlgorithm:
        """Get hash algorithm used."""
        return self._algorithm

    def contains(self, hash_value: str) -> bool:
        """Check if hash is in the tree."""
        return hash_value in self._leaf_indices

    def get_proof(self, hash_value: str) -> MerkleProof:
        """Generate inclusion proof for a hash value.

        Args:
            hash_value: Hex-encoded hash to prove inclusion of

        Returns:
            MerkleProof for the hash value

        Raises:
            ValueError: If hash_value is not in tree
        """
        if hash_value not in self._leaf_indices:
            raise ValueError(f"Hash not found in tree: {hash_value}")

        proof_path: list[tuple[str, Literal["left", "right"]]] = []
        index = self._leaf_indices[hash_value]

        # Walk up tree from leaf to root
        for level in range(len(self._tree) - 1, 0, -1):
            layer = self._tree[level]
            is_right = index % 2 == 1

            if is_right:
                sibling_index = index - 1
                position: Literal["left", "right"] = "left"
            else:
                sibling_index = min(index + 1, len(layer) - 1)
                position = "right"

            sibling_hash = layer[sibling_index]
            proof_path.append((sibling_hash, position))
            index = index // 2

        return MerkleProof(
            leaf_hash=hash_value,
            proof_path=tuple(proof_path),
            root_hash=self.root,
            leaf_index=self._leaf_indices[hash_value],
            algorithm=self._algorithm,
        )

    def get_all_proofs(self) -> dict[str, MerkleProof]:
        """Generate inclusion proofs for all leaves."""
        return {leaf: self.get_proof(leaf) for leaf in self._leaves}

    def _build_tree(self) -> list[list[str]]:
        """Build complete Merkle tree."""
        current_level = list(self._leaves)
        levels: list[list[str]] = [current_level]

        while len(current_level) > 1:
            next_level: list[str] = []

            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                parent = self._hash_pair(left, right)
                next_level.append(parent)

            levels.insert(0, next_level)
            current_level = next_level

        return levels

    def _hash_pair(self, left: str, right: str) -> str:
        """Hash two child nodes together."""
        combined = bytes.fromhex(left) + bytes.fromhex(right)
        return compute_hash(combined, self._algorithm)

    def to_dict(self) -> dict:
        """Convert tree to dictionary for serialization."""
        return {
            "root": self.root,
            "leaf_count": self.leaf_count,
            "depth": self.depth,
            "algorithm": self._algorithm.value,
            "leaves": list(self._leaves),
        }
