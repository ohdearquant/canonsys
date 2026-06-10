"""Base types for kron: Enum, HashableModel, DataClass, Params, and ModelConfig.

Provides:
    - Enum: String-backed enum for JSON-friendly enumerations
    - ModelConfig: Configuration for sentinel handling and validation
    - Params: Immutable parameter container (frozen dataclass, custom __init__)
    - DataClass: Mutable dataclass base with to_dict() support
    - HashableModel: Pydantic BaseModel with hash and equality support
"""

from __future__ import annotations

import contextlib
from collections.abc import MutableMapping, MutableSequence, MutableSet
from dataclasses import MISSING as DATACLASS_MISSING, dataclass, field, fields
from enum import Enum as _Enum, StrEnum
from typing import Any, ClassVar, Literal, Self

from pydantic import BaseModel as _PydanticBaseModel

from ._sentinel import Undefined, Unset, is_sentinel, is_undefined

__all__ = (
    "DataClass",
    "Enum",
    "HashableModel",
    "Meta",
    "ModelConfig",
    "Params",
)


# =============================================================================
# Enum
# =============================================================================


class Enum(StrEnum):
    """String-backed enum with Allowable protocol.

    Members serialize directly to their string values. Python 3.11+.
    """

    @classmethod
    def allowed(cls) -> tuple[str, ...]:
        """Return tuple of all valid member values."""
        return tuple(e.value for e in cls)


# =============================================================================
# Hash utilities (inlined for self-containment)
# =============================================================================

_PRIMITIVE_TYPES = (str, int, float, bool, type(None))
_TYPE_MARKER_DICT = 0
_TYPE_MARKER_LIST = 1
_TYPE_MARKER_TUPLE = 2
_TYPE_MARKER_SET = 3
_TYPE_MARKER_FROZENSET = 4
_TYPE_MARKER_PYDANTIC = 5


def _generate_hashable_representation(item: Any) -> Any:
    """Convert object to stable, order-independent hashable representation."""
    if isinstance(item, _PRIMITIVE_TYPES):
        return item

    if isinstance(item, _PydanticBaseModel):
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


def _hash_obj(data: Any) -> int:
    """Generate stable int hash for Python __hash__() protocol.

    Use for: set/dict membership, deduplication, __hash__ implementations.
    """
    hashable_repr = _generate_hashable_representation(data)
    try:
        return hash(hashable_repr)
    except TypeError as e:
        raise TypeError(
            f"The generated representation for the input data was not hashable. "
            f"Input type: {type(data).__name__}, Representation type: {type(hashable_repr).__name__}. "
            f"Original error: {e}"
        )


# =============================================================================
# HashableModel
# =============================================================================


class HashableModel(_PydanticBaseModel):
    """Pydantic BaseModel with hash and equality support.

    Provides content-based hashing for use in sets/dicts.

    Usage:
        class ServiceConfig(HashableModel):
            provider: str
            name: str
    """

    def __hash__(self) -> int:
        """Hash based on model's dict representation."""
        return _hash_obj(self.model_dump())

    def __eq__(self, other: object) -> bool:
        """Equality via hash comparison."""
        if not isinstance(other, HashableModel):
            return NotImplemented
        return hash(self) == hash(other)


# =============================================================================
# Meta
# =============================================================================


@dataclass(slots=True, frozen=True)
class Meta:
    """Immutable key-value metadata container for Spec.

    Hashable for use in sets/dicts and as Spec metadata. Special handling
    for callables (hashed by id for identity semantics).

    Attributes:
        key: Metadata key identifier.
        value: Associated value (any type).

    Example:
        >>> meta = Meta("name", "username")
        >>> meta.key
        'name'
        >>> meta.value
        'username'
    """

    key: str
    value: Any

    def __hash__(self) -> int:
        """Hash by (key, value). Callables use id(), unhashables use str()."""
        if callable(self.value):
            return hash((self.key, id(self.value)))
        try:
            return hash((self.key, self.value))
        except TypeError:
            return hash((self.key, str(self.value)))

    def __eq__(self, other: object) -> bool:
        """Equality by key then value. Callables compared by id."""
        if not isinstance(other, Meta):
            return NotImplemented
        if self.key != other.key:
            return False
        if callable(self.value) and callable(other.value):
            return id(self.value) == id(other.value)
        return bool(self.value == other.value)


# =============================================================================
# ModelConfig
# =============================================================================


@dataclass(slots=True, frozen=True)
class ModelConfig:
    """Configuration for Params/DataClass behavior.

    Attributes:
        sentinel_additions: Additional sentinel categories beyond Undefined/Unset.
            Valid values: "none", "empty", "pydantic", "dataclass".
        strict: Require all fields have values (raise if sentinel).
        prefill_unset: Convert Undefined fields to Unset on validation.
        use_enum_values: Serialize enums as their values (not names).
    """

    sentinel_additions: frozenset[str] = field(default_factory=frozenset)
    strict: bool = False
    prefill_unset: bool = True
    use_enum_values: bool = False

    def is_sentinel(self, value: Any) -> bool:
        """Check if value is sentinel per this config's additions."""
        return is_sentinel(value, self.sentinel_additions)


# =============================================================================
# _SentinelMixin
# =============================================================================


class _SentinelMixin:
    """Shared sentinel-aware serialization logic for Params and DataClass.

    Provides: allowed(), _is_sentinel(), _normalize_value(), _validate(),
    to_dict(), with_updates(), __hash__().

    Subclasses must define:
        _config: ClassVar[ModelConfig]
        _allowed_keys: ClassVar[set[str]]
    """

    __slots__ = ()

    _config: ClassVar[ModelConfig]
    _allowed_keys: ClassVar[set[str]]

    @classmethod
    def allowed(cls) -> set[str]:
        """Return set of valid field names (excludes private/ClassVar)."""
        if cls._allowed_keys:
            return cls._allowed_keys
        cls._allowed_keys = set(f.name for f in fields(cls) if not f.name.startswith("_"))
        return cls._allowed_keys

    @classmethod
    def _is_sentinel(cls, value: Any) -> bool:
        """Check if value is sentinel per _config settings."""
        return is_sentinel(value, cls._config.sentinel_additions)

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """Normalize value for serialization (enum to value if configured)."""
        if cls._config.use_enum_values and isinstance(value, _Enum):
            return value.value
        return value

    def _validate(self) -> None:
        """Validate fields per _config. Raises ExceptionGroup if strict violations."""
        missing: list[Exception] = []
        for k in self.allowed():
            if self._config.strict and self._is_sentinel(getattr(self, k, Unset)):
                missing.append(ValueError(f"Missing required parameter: {k}"))
            if self._config.prefill_unset and is_undefined(getattr(self, k, Undefined)):
                object.__setattr__(self, k, Unset)
        if missing:
            raise ExceptionGroup("Missing required parameters", missing)

    def to_dict(
        self,
        mode: Literal["python", "json"] = "python",
        exclude: set[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Serialize to dict, excluding sentinel values."""
        data = {}
        exclude = exclude or set()
        for k in self.allowed():
            if k not in exclude:
                v = getattr(self, k, Undefined)
                if not self._is_sentinel(v):
                    data[k] = self._normalize_value(v)
        if mode == "json":
            from kron.utils import json_dump

            return json_dump(data, decode=True, as_loaded=True, **kwargs)

        return data

    def with_updates(
        self, copy_containers: Literal["shallow", "deep"] | None = None, **kwargs: Any
    ) -> Self:
        """Return new instance with updated fields.

        Args:
            copy_containers: "shallow", "deep", or None (share references).
            **kwargs: Field values to update.
        """
        dict_ = self.to_dict()

        def _out(d: dict):
            d.update(kwargs)
            return type(self)(**d)

        if copy_containers is None:
            return _out(dict_)

        match copy_containers:
            case "shallow":
                for k, v in dict_.items():
                    if k not in kwargs and isinstance(
                        v, (MutableSequence, MutableMapping, MutableSet)
                    ):
                        dict_[k] = v.copy() if hasattr(v, "copy") else list(v)
                return _out(dict_)

            case "deep":
                import copy

                for k, v in dict_.items():
                    if k not in kwargs and isinstance(
                        v, (MutableSequence, MutableMapping, MutableSet)
                    ):
                        dict_[k] = copy.deepcopy(v)
                return _out(dict_)

        raise ValueError(
            f"Invalid copy_containers: {copy_containers!r}. Must be 'shallow', 'deep', or None."
        )

    def is_sentinel_field(self, field_name: str) -> bool:
        """Check if field holds a sentinel value.

        Raises:
            ValueError: If field_name not in allowed().
        """
        if field_name not in self.allowed():
            raise ValueError(f"Invalid field name: {field_name}")
        value = getattr(self, field_name, Undefined)
        return self._is_sentinel(value)

    def __hash__(self) -> int:
        """Hash based on serialized dict contents."""
        return _hash_obj(self)


# =============================================================================
# Params
# =============================================================================


@dataclass(slots=True, frozen=True, init=False)
class Params(_SentinelMixin):
    """Immutable parameter container with sentinel-aware serialization.

    Frozen dataclass with custom __init__ for sentinel support.
    Subclass and override _config for custom behavior.

    Example:
        >>> @dataclass(slots=True, frozen=True, init=False)
        ... class RequestParams(Params):
        ...     timeout: int = Unset
        ...     retries: int = 3
    """

    _config: ClassVar[ModelConfig] = ModelConfig()
    _allowed_keys: ClassVar[set[str]] = set()

    def __init__(self, **kwargs: Any):
        """Initialize from kwargs with validation.

        Raises:
            ValueError: If kwargs contains invalid field names.
            ExceptionGroup: If strict mode and required fields missing.
        """
        for f in fields(self):
            if f.name.startswith("_"):
                continue
            if f.name not in kwargs:
                if f.default is not DATACLASS_MISSING:
                    object.__setattr__(self, f.name, f.default)
                elif f.default_factory is not DATACLASS_MISSING:
                    object.__setattr__(self, f.name, f.default_factory())

        for k, v in kwargs.items():
            if k in self.allowed():
                object.__setattr__(self, k, v)
            else:
                raise ValueError(f"Invalid parameter: {k}")

        self._validate()

    def default_kw(self) -> Any:
        """Return dict with kwargs/kw fields merged into top level."""
        dict_ = self.to_dict()
        kw_ = {}
        kw_.update(dict_.pop("kwargs", {}))
        kw_.update(dict_.pop("kw", {}))
        dict_.update(kw_)
        return dict_

    def __eq__(self, other: object) -> bool:
        """Equality via hash. Returns NotImplemented for incompatible types."""
        if not isinstance(other, Params):
            return NotImplemented
        return hash(self) == hash(other)


# =============================================================================
# DataClass
# =============================================================================


@dataclass(slots=True)
class DataClass:
    """Mutable dataclass with sentinel-aware serialization.

    Provides to_dict() for serialization, excluding sentinel values.
    Used as base for RequestContext and similar data-carrying classes.

    Usage:
        @dataclass(slots=True)
        class RequestContext(DataClass):
            name: str
            metadata: dict[str, Any] = field(default_factory=dict)
    """

    _allowed_keys: ClassVar[set[str]] = set()

    @classmethod
    def allowed(cls) -> set[str]:
        """Return set of valid field names (excludes private/ClassVar)."""
        if cls._allowed_keys:
            return cls._allowed_keys
        cls._allowed_keys = {f.name for f in fields(cls) if not f.name.startswith("_")}
        return cls._allowed_keys

    def to_dict(
        self,
        mode: Literal["python", "json"] = "python",
        exclude: set[str] | None = None,
    ) -> dict[str, Any]:
        """Serialize to dict, excluding sentinel values.

        Args:
            mode: "python" for native types, "json" for JSON-compatible.
            exclude: Field names to exclude from output.

        Returns:
            Dict of non-sentinel field values.
        """
        data = {}
        exclude = exclude or set()
        for k in self.allowed():
            if k not in exclude:
                v = getattr(self, k, Undefined)
                if not is_sentinel(v):
                    data[k] = v
        return data

    def __hash__(self) -> int:
        """Hash based on serialized dict contents."""
        return _hash_obj(self.to_dict())

    def __eq__(self, other: object) -> bool:
        """Equality via hash comparison."""
        if not isinstance(other, DataClass):
            return NotImplemented
        return hash(self) == hash(other)
