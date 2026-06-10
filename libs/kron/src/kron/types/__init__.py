"""Kron types absorbed from krons for canon self-containment.

Provides:
    - FK, FKMeta, Vector, VectorMeta: Database field type annotations
    - extract_kron_db_meta: Unified metadata extraction
    - Enum, HashableModel: Base types for models
    - is_sentinel, Unset, Undefined: Sentinel handling
    - ID: Semantic UUID typing
"""

from ._sentinel import (
    MaybeSentinel,
    MaybeUndefined,
    MaybeUnset,
    SingletonType,
    T,
    Undefined,
    UndefinedType,
    Unset,
    UnsetType,
    is_sentinel,
    is_undefined,
    is_unset,
    not_sentinel,
)
from .base import DataClass, Enum, HashableModel, Meta, ModelConfig, Params
from .db_types import FK, FKMeta, Vector, VectorMeta, extract_kron_db_meta
from .enums import DataClassification, DecisionClass, PhraseActionType
from .identity import ID

__all__ = (
    "FK",
    "ID",
    "DataClass",
    "DataClassification",
    "DecisionClass",
    "Enum",
    "FKMeta",
    "HashableModel",
    "MaybeSentinel",
    "MaybeUndefined",
    "MaybeUnset",
    "Meta",
    "ModelConfig",
    "Params",
    "PhraseActionType",
    "SingletonType",
    "T",
    "Undefined",
    "UndefinedType",
    "Unset",
    "UnsetType",
    "Vector",
    "VectorMeta",
    "extract_kron_db_meta",
    "is_sentinel",
    "is_undefined",
    "is_unset",
    "not_sentinel",
)
