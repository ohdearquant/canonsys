from __future__ import annotations

import contextlib
import copy
import hashlib
from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Any

from ._json_dump import json_dumpb
from ._lazy_init import LazyInit

if TYPE_CHECKING:
    from hashlib import _Hash

__all__ = (
    "GENESIS_HASH",
    "MAX_HASH_INPUT_BYTES",
    "HashAlgorithm",
    "compute_chain_hash",
    "compute_hash",
    "hash_obj",
)

_lazy = LazyInit()
PydanticBaseModel = None


def _do_init() -> None:
    """Lazy-initialize Pydantic BaseModel reference."""
    global PydanticBaseModel
    from pydantic import BaseModel

    PydanticBaseModel = BaseModel


_PRIMITIVE_TYPES = (str, int, float, bool, type(None))
_TYPE_MARKER_DICT = 0
_TYPE_MARKER_LIST = 1
_TYPE_MARKER_TUPLE = 2
_TYPE_MARKER_SET = 3
_TYPE_MARKER_FROZENSET = 4
_TYPE_MARKER_PYDANTIC = 5


def _generate_hashable_representation(item: Any) -> Any:
    """Convert object to stable, order-independent hashable representation.

    Recursively transforms dicts/sets into sorted tuples with type markers
    to ensure consistent hashing regardless of insertion order.
    """
    if isinstance(item, _PRIMITIVE_TYPES):
        return item

    if PydanticBaseModel and isinstance(item, PydanticBaseModel):
        return (
            _TYPE_MARKER_PYDANTIC,
            _generate_hashable_representation(item.model_dump()),
        )

    if isinstance(item, dict):
        return (
            _TYPE_MARKER_DICT,
            tuple(
                (str(k), _generate_hashable_representation(v))
                for k, v in sorted(item.items(), key=lambda x: str(x[0]))
            ),
        )

    if isinstance(item, list):
        return (
            _TYPE_MARKER_LIST,
            tuple(_generate_hashable_representation(elem) for elem in item),
        )

    if isinstance(item, tuple):
        return (
            _TYPE_MARKER_TUPLE,
            tuple(_generate_hashable_representation(elem) for elem in item),
        )

    if isinstance(item, frozenset):
        try:
            sorted_elements = sorted(list(item))
        except TypeError:
            sorted_elements = sorted(list(item), key=lambda x: (str(type(x)), str(x)))
        return (
            _TYPE_MARKER_FROZENSET,
            tuple(_generate_hashable_representation(elem) for elem in sorted_elements),
        )

    if isinstance(item, set):
        try:
            sorted_elements = sorted(list(item))
        except TypeError:
            sorted_elements = sorted(list(item), key=lambda x: (str(type(x)), str(x)))
        return (
            _TYPE_MARKER_SET,
            tuple(_generate_hashable_representation(elem) for elem in sorted_elements),
        )

    with contextlib.suppress(Exception):
        return str(item)
    with contextlib.suppress(Exception):
        return repr(item)

    return f"<unhashable:{type(item).__name__}:{id(item)}>"


def hash_obj(data: Any, strict: bool = False) -> int:
    """Generate stable int hash for Python __hash__() protocol.

    Use for: set/dict membership, deduplication, __hash__ implementations.
    NOT for: cryptographic integrity, content verification (use compute_hash).

    Args:
        data: Any data structure (dicts, lists, Pydantic models, nested).
        strict: Deep-copy data before hashing to prevent mutation effects.

    Returns:
        Stable int hash suitable for hash-based collections.

    Raises:
        TypeError: If generated representation is not hashable.
    """
    _lazy.ensure(_do_init)

    data_to_process = data
    if strict:
        data_to_process = copy.deepcopy(data)

    hashable_repr = _generate_hashable_representation(data_to_process)

    try:
        return hash(hashable_repr)
    except TypeError as e:
        raise TypeError(
            f"The generated representation for the input data was not hashable. "
            f"Input type: {type(data).__name__}, Representation type: {type(hashable_repr).__name__}. "
            f"Original error: {e}"
        )


MAX_HASH_INPUT_BYTES = 10 * 1024 * 1024
"""Max hash input (10MB). SOC2 CC7.1 DoS prevention."""

GENESIS_HASH: str = "GENESIS"
"""Sentinel for first entry in hash chain."""


class HashAlgorithm(Enum):
    """NIST FIPS 180-4 compliant hash algorithms for cryptographic integrity."""

    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"

    def get_hasher(self) -> Callable[..., _Hash]:
        """Return hashlib constructor for this algorithm."""
        return {
            HashAlgorithm.SHA256: hashlib.sha256,
            HashAlgorithm.SHA384: hashlib.sha384,
            HashAlgorithm.SHA512: hashlib.sha512,
        }[self]

    @property
    def digest_size(self) -> int:
        """Digest size in bytes (32/48/64 for SHA256/384/512)."""
        return {
            HashAlgorithm.SHA256: 32,
            HashAlgorithm.SHA384: 48,
            HashAlgorithm.SHA512: 64,
        }[self]


def compute_hash(
    obj: dict | str | bytes | Any,
    algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    none_as_valid: bool = False,
) -> str:
    """Compute cryptographic hash for content integrity verification.

    Use for: content integrity, tamper detection, evidence chains.
    NOT for: __hash__ protocol, set/dict membership (use hash_obj).

    Args:
        obj: Data to hash (dict, str, bytes, or JSON-serializable).
        algorithm: Hash algorithm (default SHA-256).
        none_as_valid: Treat None as valid input (hashes as "null").

    Returns:
        Hex-encoded hash digest string.

    Raises:
        ValueError: If payload exceeds MAX_HASH_INPUT_BYTES (10MB).
    """
    payload: bytes
    if none_as_valid and obj is None:
        payload = b"null"
    elif isinstance(obj, bytes):
        payload = obj
    elif isinstance(obj, str):
        payload = obj.encode()
    else:
        payload = json_dumpb(obj, sort_keys=True, deterministic_sets=True)

    if len(payload) > MAX_HASH_INPUT_BYTES:
        raise ValueError(f"Payload {len(payload):,}B > {MAX_HASH_INPUT_BYTES:,}B limit")

    hasher = algorithm.get_hasher()
    return hasher(payload).hexdigest()


def compute_chain_hash(
    payload_hash: str,
    previous_hash: str | None,
    algorithm: HashAlgorithm = HashAlgorithm.SHA256,
) -> str:
    """Compute chain hash linking current entry to previous.

    Formula: HASH("{payload_hash}:{previous_hash or 'GENESIS'}")

    Args:
        payload_hash: Hash of current entry's payload.
        previous_hash: Hash of previous entry (None for genesis entry).
        algorithm: Hash algorithm to use.

    Returns:
        Hex-encoded chain hash for tamper-evident linking.
    """
    chain_input = f"{payload_hash}:{previous_hash or GENESIS_HASH}"
    return compute_hash(chain_input, algorithm)
