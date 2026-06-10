"""JSON serialization utilities built on orjson.

Provides flexible serialization with:
- Configurable type handling (Decimal, Enum, datetime, sets)
- Safe fallback mode for logging non-serializable objects
- Caching of default handlers for performance
"""

from __future__ import annotations

import contextlib
import datetime as dt
import decimal
import re
from collections.abc import Callable, Mapping
from enum import Enum
from functools import lru_cache
from pathlib import Path
from textwrap import shorten
from typing import Any
from uuid import UUID

import orjson

__all__ = (
    "get_orjson_default",
    "json_dump",
    "json_dumpb",
    "make_options",
)

# Types with native orjson support (skip in custom order)
_NATIVE = (dt.datetime, dt.date, dt.time, UUID)
_ADDR_PAT = re.compile(r" at 0x[0-9A-Fa-f]+")
_SERIALIZATION_METHODS = ("model_dump", "to_dict", "dict")


def get_orjson_default(
    *,
    order: list[type] | None = None,
    additional: Mapping[type, Callable[[Any], Any]] | None = None,
    extend_default: bool = True,
    deterministic_sets: bool = False,
    decimal_as_float: bool = False,
    enum_as_name: bool = False,
    passthrough_datetime: bool = False,
    safe_fallback: bool = False,
    fallback_clip: int = 2048,
) -> Callable[[Any], Any]:
    """Build a `default=` callable for orjson.dumps with type-based dispatch.

    Args:
        order: Custom type priority order (checked before defaults).
        additional: Extra type->serializer mappings.
        extend_default: Merge order with defaults (True) or replace (False).
        deterministic_sets: Sort sets for reproducible output (slower).
        decimal_as_float: Decimal->float (lossy but compact).
        enum_as_name: Enum->name instead of value.
        passthrough_datetime: Use custom datetime serialization.
        safe_fallback: Never raise; clip repr for unknown types (for logging).
        fallback_clip: Max chars for safe_fallback repr.

    Returns:
        Callable suitable for orjson.dumps(default=...).
    """
    ser = _default_serializers(
        deterministic_sets=deterministic_sets,
        decimal_as_float=decimal_as_float,
        enum_as_name=enum_as_name,
        passthrough_datetime=passthrough_datetime,
    )
    if additional:
        ser.update(additional)

    base_order: list[type] = [Path, decimal.Decimal, set, frozenset]
    if enum_as_name:
        base_order.insert(0, Enum)
    if passthrough_datetime:
        base_order.insert(0, dt.datetime)

    if order:
        order_ = (
            (base_order + [t for t in order if t not in base_order])
            if extend_default
            else list(order)
        )
    else:
        order_ = base_order.copy()

    if not passthrough_datetime:  # Skip types on orjson's native fast path
        order_ = [t for t in order_ if t not in _NATIVE]

    order_tuple = tuple(order_)
    cache: dict[type, Callable[[Any], Any]] = {}

    def default(obj: Any) -> Any:
        typ = obj.__class__
        func = cache.get(typ)
        if func is None:
            for T in order_tuple:
                if issubclass(typ, T):
                    f = ser.get(T)
                    if f:
                        cache[typ] = f
                        func = f
                        break
            else:
                methods = _SERIALIZATION_METHODS
                for m in methods:
                    md = getattr(obj, m, None)
                    if callable(md):
                        with contextlib.suppress(Exception):
                            return md()

                # Handle UUID-like types (e.g. asyncpg.pgproto.pgproto.UUID)
                # that orjson doesn't natively support
                if typ.__name__ == "UUID":
                    cache[typ] = str
                    return str(obj)

                if safe_fallback:
                    if isinstance(obj, Exception):
                        return {"type": obj.__class__.__name__, "message": str(obj)}

                    return shorten(
                        repr(obj),
                        width=fallback_clip,
                        placeholder=f"...(+{len(repr(obj)) - fallback_clip} chars)",
                    )
                raise TypeError(f"Type is not JSON serializable: {typ.__name__}")
        return func(obj)

    return default


def make_options(
    *,
    pretty: bool = False,
    sort_keys: bool = False,
    naive_utc: bool = False,
    utc_z: bool = False,
    append_newline: bool = False,
    passthrough_datetime: bool = False,
    allow_non_str_keys: bool = False,
) -> int:
    """Compose orjson option bit flags.

    Args:
        pretty: Indent with 2 spaces (OPT_INDENT_2).
        sort_keys: Alphabetical key ordering (OPT_SORT_KEYS).
        naive_utc: Treat naive datetime as UTC (OPT_NAIVE_UTC).
        utc_z: Use 'Z' suffix for UTC times (OPT_UTC_Z).
        append_newline: Add trailing newline (OPT_APPEND_NEWLINE).
        passthrough_datetime: Custom datetime handling (OPT_PASSTHROUGH_DATETIME).
        allow_non_str_keys: Allow int/UUID keys (OPT_NON_STR_KEYS).

    Returns:
        Combined option flags for orjson.dumps(option=...).
    """
    opt = 0
    if append_newline:
        opt |= orjson.OPT_APPEND_NEWLINE
    if pretty:
        opt |= orjson.OPT_INDENT_2
    if sort_keys:
        opt |= orjson.OPT_SORT_KEYS
    if naive_utc:
        opt |= orjson.OPT_NAIVE_UTC
    if utc_z:
        opt |= orjson.OPT_UTC_Z
    if passthrough_datetime:
        opt |= orjson.OPT_PASSTHROUGH_DATETIME
    if allow_non_str_keys:
        opt |= orjson.OPT_NON_STR_KEYS
    return opt


def json_dumpb(
    obj: Any,
    *,
    pretty: bool = False,
    sort_keys: bool = False,
    naive_utc: bool = False,
    utc_z: bool = False,
    append_newline: bool = False,
    allow_non_str_keys: bool = False,
    deterministic_sets: bool = False,
    decimal_as_float: bool = False,
    enum_as_name: bool = False,
    passthrough_datetime: bool = False,
    safe_fallback: bool = False,
    fallback_clip: int = 2048,
    default: Callable[[Any], Any] | None = None,
    options: int | None = None,
) -> bytes:
    """Serialize to bytes (fast path for hot code).

    Args:
        obj: Object to serialize.
        pretty: Indent output.
        sort_keys: Alphabetical key order.
        naive_utc: Naive datetime as UTC.
        utc_z: Use 'Z' for UTC.
        append_newline: Trailing newline.
        allow_non_str_keys: Allow non-string dict keys.
        deterministic_sets: Sort sets.
        decimal_as_float: Decimal as float.
        enum_as_name: Enum as name.
        passthrough_datetime: Custom datetime handling.
        safe_fallback: Never raise (for logging only).
        fallback_clip: Max repr chars in safe mode.
        default: Custom default callable (overrides above).
        options: Pre-composed option flags (overrides above).

    Returns:
        JSON as bytes.
    """
    if default is None:
        default = _cached_default(
            deterministic_sets=deterministic_sets,
            decimal_as_float=decimal_as_float,
            enum_as_name=enum_as_name,
            passthrough_datetime=passthrough_datetime,
            safe_fallback=safe_fallback,
            fallback_clip=fallback_clip,
        )
    opt = (
        options
        if options is not None
        else make_options(
            pretty=pretty,
            sort_keys=sort_keys,
            naive_utc=naive_utc,
            utc_z=utc_z,
            append_newline=append_newline,
            passthrough_datetime=passthrough_datetime,
            allow_non_str_keys=allow_non_str_keys,
        )
    )
    return orjson.dumps(obj, default=default, option=opt)


def json_dump(
    obj: Any,
    *,
    sort_keys: bool = False,
    deterministic_sets: bool = False,
    decode: bool = False,
    as_loaded: bool = False,
    **kwargs: Any,
) -> str | bytes | Any:
    """Serialize to JSON with flexible output format.

    Args:
        obj: Object to serialize.
        sort_keys: Alphabetical key order.
        deterministic_sets: Sort sets.
        decode: Return str instead of bytes.
        as_loaded: Parse output back to dict/list (requires decode=True).
        **kwargs: Passed to json_dumpb.

    Returns:
        bytes (default), str (decode=True), or dict/list (as_loaded=True).

    Raises:
        ValueError: If as_loaded=True without decode=True.
    """
    if not decode and as_loaded:
        raise ValueError("as_loaded=True requires decode=True")

    bytes_ = json_dumpb(
        obj,
        sort_keys=sort_keys,
        deterministic_sets=deterministic_sets,
        **kwargs,
    )

    if not decode:
        return bytes_
    return orjson.loads(bytes_) if as_loaded else bytes_.decode("utf-8")


@lru_cache(maxsize=128)
def _cached_default(
    deterministic_sets: bool,
    decimal_as_float: bool,
    enum_as_name: bool,
    passthrough_datetime: bool,
    safe_fallback: bool,
    fallback_clip: int,
) -> Callable[[Any], Any]:
    """Cache default handlers to avoid repeated construction."""
    return get_orjson_default(
        deterministic_sets=deterministic_sets,
        decimal_as_float=decimal_as_float,
        enum_as_name=enum_as_name,
        passthrough_datetime=passthrough_datetime,
        safe_fallback=safe_fallback,
        fallback_clip=fallback_clip,
    )


def _default_serializers(
    deterministic_sets: bool,
    decimal_as_float: bool,
    enum_as_name: bool,
    passthrough_datetime: bool,
) -> dict[type, Callable[[Any], Any]]:
    """Build type->serializer mapping based on configuration."""

    def normalize_for_sorting(x: Any) -> str:
        """Strip memory addresses from repr for stable sorting."""
        return _ADDR_PAT.sub(" at 0x?", str(x))

    def stable_sorted_iterable(o: Any) -> list[Any]:
        """Sort mixed-type iterables by (class_name, normalized_repr)."""
        return sorted(o, key=lambda x: (x.__class__.__name__, normalize_for_sorting(x)))

    ser: dict[type, Callable[[Any], Any]] = {
        Path: str,
        decimal.Decimal: (float if decimal_as_float else str),
        set: (stable_sorted_iterable if deterministic_sets else list),
        frozenset: (stable_sorted_iterable if deterministic_sets else list),
    }
    if enum_as_name:
        ser[Enum] = lambda e: e.name

    if passthrough_datetime:
        ser[dt.datetime] = lambda o: o.isoformat()
    return ser
