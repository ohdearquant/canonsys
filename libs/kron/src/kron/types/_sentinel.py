"""Sentinel types for distinguishing missing vs unset values.

Provides two distinct sentinel states:
    - Undefined: Field/key entirely absent from namespace (never existed)
    - Unset: Key present but value not provided (explicit "no value")

This distinction enables precise handling in serialization, validation,
and API parameter processing where None has semantic meaning.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import (
    Any,
    ClassVar,
    Final,
    Literal,
    Self,
    TypeAlias,
    TypeGuard,
    TypeVar,
    Union,
)

__all__ = (
    "MaybeSentinel",
    "MaybeUndefined",
    "MaybeUnset",
    "SingletonType",
    "T",
    "Undefined",
    "UndefinedType",
    "Unset",
    "UnsetType",
    "is_sentinel",
    "is_undefined",
    "is_unset",
    "not_sentinel",
)

T = TypeVar("T")


class _SingletonMeta(type):
    """Metaclass ensuring single instance per subclass for identity checks."""

    _cache: ClassVar[dict[type, SingletonType]] = {}

    def __call__(cls, *a, **kw):
        if cls not in cls._cache:
            cls._cache[cls] = super().__call__(*a, **kw)
        return cls._cache[cls]


class SingletonType(metaclass=_SingletonMeta):
    """Base for singleton sentinels.

    Guarantees:
        - Single instance per subclass (safe `is` checks)
        - Falsy evaluation (bool returns False)
        - Identity preserved across copy/deepcopy/pickle
    """

    __slots__: tuple[str, ...] = ()

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        """Return self; singleton identity survives deepcopy."""
        return self

    def __copy__(self) -> Self:
        """Return self; singleton identity survives copy."""
        return self

    def __bool__(self) -> bool:
        """Subclasses must return False."""
        raise NotImplementedError

    def __repr__(self) -> str:
        """Subclasses must return sentinel name."""
        raise NotImplementedError


class UndefinedType(SingletonType):
    """Sentinel for field/key entirely absent from namespace."""

    __slots__ = ()

    def __bool__(self) -> Literal[False]:
        return False

    def __repr__(self) -> Literal["Undefined"]:
        return "Undefined"

    def __str__(self) -> Literal["Undefined"]:
        return "Undefined"

    def __reduce__(self) -> tuple[type[UndefinedType], tuple[()]]:
        """Preserve singleton across pickle."""
        return (UndefinedType, ())

    def __or__(self, other: type) -> Any:
        """Enable union syntax: str | Undefined."""
        other_type = type(other) if isinstance(other, SingletonType) else other
        return Union[type(self), other_type]

    def __ror__(self, other: type) -> Any:
        """Enable reverse union: Undefined | str."""
        other_type = type(other) if isinstance(other, SingletonType) else other
        return Union[other_type, type(self)]


class UnsetType(SingletonType):
    """Sentinel for key present but value explicitly not provided."""

    __slots__ = ()

    def __bool__(self) -> Literal[False]:
        return False

    def __repr__(self) -> Literal["Unset"]:
        return "Unset"

    def __str__(self) -> Literal["Unset"]:
        return "Unset"

    def __reduce__(self) -> tuple[type[UnsetType], tuple[()]]:
        """Preserve singleton across pickle."""
        return (UnsetType, ())

    def __or__(self, other: type) -> Any:
        """Enable union syntax: str | Unset."""
        other_type = type(other) if isinstance(other, SingletonType) else other
        return Union[type(self), other_type]

    def __ror__(self, other: type) -> Any:
        """Enable reverse union: Unset | str."""
        other_type = type(other) if isinstance(other, SingletonType) else other
        return Union[other_type, type(self)]


Undefined: Final[UndefinedType] = UndefinedType()
"""Singleton: key/field entirely absent from namespace."""

Unset: Final[UnsetType] = UnsetType()
"""Singleton: key present but value not provided."""

MaybeUndefined: TypeAlias = T | UndefinedType
"""Type alias: T or Undefined (for optional fields that may not exist)."""

MaybeUnset: TypeAlias = T | UnsetType
"""Type alias: T or Unset (for params with explicit 'not provided' state)."""

MaybeSentinel: TypeAlias = T | UndefinedType | UnsetType
"""Type alias: T or either sentinel (full optionality)."""

_EMPTY_TUPLE: tuple[Any, ...] = (tuple(), set(), frozenset(), dict(), list(), "")

AdditionalSentinels = Literal["none", "empty", "pydantic", "dataclass"]


def _is_builtin_sentinel(value: Any) -> bool:
    return isinstance(value, (UndefinedType, UnsetType))


def _is_pydantic_sentinel(value: Any) -> bool:
    from pydantic_core import PydanticUndefinedType

    return isinstance(value, PydanticUndefinedType)


def _is_none(value: Any) -> bool:
    return value is None


def _is_empty(value: Any) -> bool:
    return value in _EMPTY_TUPLE


def _is_dataclass_missing(value: Any) -> bool:
    from dataclasses import MISSING

    return value is MISSING


SENTINEL_HANDLERS: dict[str, Callable[[Any], bool]] = {
    "none": _is_none,
    "empty": _is_empty,
    "pydantic": _is_pydantic_sentinel,
    "dataclass": _is_dataclass_missing,
}

HANDLE_SEQUENCE: tuple[str, ...] = ("none", "empty", "pydantic", "dataclass")


def is_undefined(value: Any) -> bool:
    """Check if value is Undefined sentinel."""
    return isinstance(value, UndefinedType)


def is_unset(value: Any) -> bool:
    """Check if value is Unset sentinel."""
    return isinstance(value, UnsetType)


def is_sentinel(
    value: Any,
    additions: set[AdditionalSentinels] = frozenset(),
) -> bool:
    """Check if value is any sentinel type.

    Always checks Undefined and Unset. Additional sentinel categories
    can be opted into via the additions set.
    """
    if _is_builtin_sentinel(value):
        return True
    for key in HANDLE_SEQUENCE:
        if key in additions and SENTINEL_HANDLERS[key](value):
            return True
    return False


def not_sentinel(
    value: T | UndefinedType | UnsetType,
    additions: set[AdditionalSentinels] = frozenset(),
) -> TypeGuard[T]:
    """Type-narrowing guard: value is NOT a sentinel."""
    return not is_sentinel(value, additions)
