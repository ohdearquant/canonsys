"""Core utility functions."""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import wraps
from types import UnionType
from typing import Any, ParamSpec, TypeVar, Union, get_args, get_origin
from uuid import UUID

__all__ = (
    "async_synchronized",
    "coerce_created_at",
    "extract_types",
    "load_type_from_string",
    "now_utc",
    "register_type_prefix",
    "synchronized",
    "to_uuid",
)

P = ParamSpec("P")
R = TypeVar("R")


def now_utc() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(UTC)


def to_uuid(value: Any) -> UUID:
    """Convert value to UUID instance.

    Args:
        value: UUID, UUID string, or Observable with .id attribute.

    Returns:
        UUID instance.

    Raises:
        ValueError: If value cannot be converted to UUID.
    """
    # Import lazily to avoid circular imports
    from kron.protocols import Observable

    if isinstance(value, Observable):
        return value.id
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        return UUID(value)
    raise ValueError("Cannot get ID from item.")


def coerce_created_at(v: Any) -> datetime:
    """Coerce value to UTC-aware datetime.

    Args:
        v: datetime, Unix timestamp (int/float), or ISO string.

    Returns:
        UTC-aware datetime instance.

    Raises:
        ValueError: If value cannot be parsed as datetime.
    """
    if isinstance(v, datetime):
        return v.replace(tzinfo=UTC) if v.tzinfo is None else v

    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, tz=UTC)

    if isinstance(v, str):
        with contextlib.suppress(ValueError):
            return datetime.fromtimestamp(float(v), tz=UTC)
        with contextlib.suppress(ValueError):
            return datetime.fromisoformat(v)
        raise ValueError(f"String '{v}' is neither timestamp nor ISO format")

    raise ValueError(f"Expected datetime/timestamp/string, got {type(v).__name__}")


# Type loading security
_TYPE_CACHE: dict[str, type] = {}
_DEFAULT_ALLOWED_PREFIXES: frozenset[str] = frozenset({"canon.", "kron.", "krons."})
_ALLOWED_MODULE_PREFIXES: set[str] = set(_DEFAULT_ALLOWED_PREFIXES)


def register_type_prefix(prefix: str) -> None:
    """Register module prefix for dynamic type loading allowlist.

    Security: Only register prefixes for modules you control.

    Args:
        prefix: Module prefix to allow (e.g., "myapp.models.").
                Must end with "." to prevent prefix attacks.

    Raises:
        ValueError: If prefix doesn't end with ".".
    """
    if not prefix.endswith("."):
        raise ValueError(f"Prefix must end with '.': {prefix}")
    _ALLOWED_MODULE_PREFIXES.add(prefix)


def load_type_from_string(type_str: str) -> type:
    """Load type from fully qualified path (e.g., 'canon.entities.Node').

    Security: Only allowlisted module prefixes can be loaded.

    Args:
        type_str: Fully qualified type path.

    Returns:
        The loaded type class.

    Raises:
        ValueError: If path invalid, not allowlisted, or type not found.
    """
    if type_str in _TYPE_CACHE:
        return _TYPE_CACHE[type_str]

    if not isinstance(type_str, str):
        raise ValueError(f"Expected string, got {type(type_str)}")

    if "." not in type_str:
        raise ValueError(f"Invalid type path (no module): {type_str}")

    if not any(type_str.startswith(prefix) for prefix in _ALLOWED_MODULE_PREFIXES):
        raise ValueError(
            f"Module '{type_str}' not in allowed prefixes: {sorted(_ALLOWED_MODULE_PREFIXES)}"
        )

    try:
        module_path, class_name = type_str.rsplit(".", 1)
        import importlib

        module = importlib.import_module(module_path)
        if module is None:
            raise ImportError(f"Module '{module_path}' not found")

        type_class = getattr(module, class_name)
        if not isinstance(type_class, type):
            raise ValueError(f"'{type_str}' is not a type")

        _TYPE_CACHE[type_str] = type_class
        return type_class

    except (ValueError, ImportError, AttributeError) as e:
        raise ValueError(f"Failed to load type '{type_str}': {e}") from e


def extract_types(item_type: Any) -> set[type]:
    """Extract concrete types from type annotations.

    Handles Union, list, set, and single types recursively.

    Args:
        item_type: Type annotation (Union[X, Y], list[type], set[type], or type).

    Returns:
        Set of concrete types extracted from the annotation.
    """

    def is_union(t: Any) -> bool:
        origin = get_origin(t)
        return origin is Union or isinstance(t, UnionType)

    extracted: set[type] = set()

    if isinstance(item_type, set):
        for t in item_type:
            if is_union(t):
                extracted.update(get_args(t))
            else:
                extracted.add(t)
        return extracted

    if isinstance(item_type, list):
        for t in item_type:
            if is_union(t):
                extracted.update(get_args(t))
            else:
                extracted.add(t)
        return extracted

    if is_union(item_type):
        return set(get_args(item_type))

    return {item_type}


def synchronized(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator for thread-safe method execution.

    Requires decorated method's instance to have self._lock (threading.Lock).
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        self = args[0]
        with self._lock:
            return func(*args, **kwargs)

    return wrapper


def async_synchronized(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Decorator for async-safe method execution.

    Requires decorated method's instance to have self._async_lock (anyio.Lock).
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        self = args[0]
        async with self._async_lock:  # type: ignore[attr-defined]
            return await func(*args, **kwargs)

    return wrapper
