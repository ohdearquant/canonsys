"""Core utilities for canon.

Hash utilities:
    compute_hash, compute_chain_hash, HashAlgorithm, GENESIS_HASH, hash_obj

Time utilities:
    now_utc, coerce_created_at

Type utilities:
    to_uuid, load_type_from_string, register_type_prefix

JSON utilities:
    json_dump, json_dumpb

SQL validation:
    validate_identifier, sanitize_order_by

Concurrency:
    alcall, concurrency module
"""

from . import concurrency
from ._hash import (
    GENESIS_HASH,
    MAX_HASH_INPUT_BYTES,
    HashAlgorithm,
    compute_chain_hash,
    compute_hash,
    hash_obj,
)
from ._json_dump import json_dump, json_dumpb
from ._utils import (
    async_synchronized,
    coerce_created_at,
    extract_types,
    load_type_from_string,
    now_utc,
    register_type_prefix,
    synchronized,
    to_uuid,
)
from .sql import (
    MAX_IDENTIFIER_LENGTH,
    SAFE_IDENTIFIER_PATTERN,
    sanitize_order_by,
    validate_identifier,
)

__all__ = (
    # Hash
    "GENESIS_HASH",
    "MAX_HASH_INPUT_BYTES",
    "HashAlgorithm",
    "compute_chain_hash",
    "compute_hash",
    "hash_obj",
    # JSON
    "json_dump",
    "json_dumpb",
    # Time
    "coerce_created_at",
    "now_utc",
    # Type utilities
    "async_synchronized",
    "extract_types",
    "load_type_from_string",
    "register_type_prefix",
    "synchronized",
    "to_uuid",
    # SQL
    "MAX_IDENTIFIER_LENGTH",
    "SAFE_IDENTIFIER_PATTERN",
    "sanitize_order_by",
    "validate_identifier",
    # Concurrency
    "concurrency",
    "alcall",
)

# Re-export alcall at top level for convenience
from .concurrency import alcall
