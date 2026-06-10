"""Spec: Framework-agnostic field specification for type-safe data modeling.

Spec is the fundamental building block for defining typed fields that can be
translated to any target framework (Pydantic, SQL, dataclass, etc.) via adapters.
"""

from __future__ import annotations

import contextlib
import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Self

from kron.types import (
    Enum,
    MaybeUndefined,
    Meta,
    Undefined,
    is_sentinel,
    is_undefined,
    not_sentinel,
)
from kron.utils.concurrency import is_coro_func

# Global cache for annotated types with bounded size
_MAX_CACHE_SIZE = int(os.environ.get("KRON_FIELD_CACHE_SIZE", "10000"))
_annotated_cache: OrderedDict[tuple[type, tuple[Meta, ...]], type] = OrderedDict()
_cache_lock = threading.RLock()  # Thread-safe access to cache


__all__ = ("CommonMeta", "Spec")


class CommonMeta(Enum):
    """Standard metadata keys for Spec field configuration.

    Keys:
        NAME: Field identifier for serialization/composition
        NULLABLE: Allows None values (becomes T | None)
        LISTABLE: Wraps type in list[T]
        VALIDATOR: Callable(s) for value validation
        DEFAULT: Static default value
        DEFAULT_FACTORY: Callable producing default (mutually exclusive with DEFAULT)
        FROZEN: Marks field as immutable after creation
        AS_FK: Foreign key target (str model name or type). When set,
            annotated() includes FKMeta in the Annotated type.

    Used by Spec to define field semantics in a framework-agnostic way.
    Adapters translate these to framework-specific constructs.
    """

    NAME = "name"
    NULLABLE = "nullable"
    LISTABLE = "listable"
    VALIDATOR = "validator"
    DEFAULT = "default"
    DEFAULT_FACTORY = "default_factory"
    FROZEN = "frozen"
    AS_FK = "as_fk"

    @classmethod
    def _validate_common_metas(cls, **kw):
        """Validate metadata constraints. Raises ExceptionGroup for multiple errors."""
        errors: list[Exception] = []

        if kw.get("default") and kw.get("default_factory"):
            errors.append(ValueError("Cannot provide both 'default' and 'default_factory'"))
        if (_df := kw.get("default_factory")) and not callable(_df):
            errors.append(ValueError("'default_factory' must be callable"))
        if _val := kw.get("validator"):
            _val = [_val] if not isinstance(_val, list) else _val
            if not all(callable(v) for v in _val):
                errors.append(ValueError("Validators must be a list of functions or a function"))

        if errors:
            raise ExceptionGroup("Metadata validation failed", errors)

    @classmethod
    def prepare(
        cls, *args: Meta, metadata: tuple[Meta, ...] | None = None, **kw: Any
    ) -> tuple[Meta, ...]:
        """Prepare metadata tuple from args/kw. Validates no duplicates, constraints."""
        seen_keys = set()
        metas = []

        if metadata:
            for meta in metadata:
                if meta.key in seen_keys:
                    raise ValueError(f"Duplicate metadata key: {meta.key}")
                seen_keys.add(meta.key)
                metas.append(meta)

        if args:
            # Flatten args - handle nested tuples/lists
            def flatten(items):
                result = []
                for item in items:
                    if isinstance(item, (list, tuple)):
                        result.extend(flatten(item))
                    elif item is not None:
                        result.append(item)
                return result

            _args = flatten(args)
            for meta in _args:
                if meta.key in seen_keys:
                    raise ValueError(f"Duplicate metadata key: {meta.key}")
                seen_keys.add(meta.key)
                metas.append(meta)

        for k, v in kw.items():
            if k in seen_keys:
                raise ValueError(f"Duplicate metadata key: {k}")
            seen_keys.add(k)
            metas.append(Meta(k, v))

        meta_dict = {m.key: m.value for m in metas}
        cls._validate_common_metas(**meta_dict)

        return tuple(metas)


@dataclass(frozen=True, slots=True, init=False)
class Spec:
    """Framework-agnostic field specification for type-safe data modeling.

    Spec is the fundamental building block for defining typed fields that can be
    translated to any target framework (Pydantic, SQL, dataclass, etc.) via adapters.

    Design:
        - Immutable: frozen dataclass ensures hashability and cacheability
        - Composable: chain methods (as_nullable, with_default) for derived specs
        - Adapter-agnostic: metadata interpreted by SpecAdapter implementations

    Attributes:
        base_type: The Python type (int, str, custom class, generic like list[str])
        metadata: Tuple of Meta(key, value) pairs defining field semantics

    Usage:
        # Basic field
        name_spec = Spec(str, name="username")

        # With modifiers
        tags_spec = Spec(str, name="tags").as_listable().as_nullable()

        # With validation
        age_spec = Spec(int, name="age", validator=lambda x: x >= 0)

        # Convert to framework type
        annotated_type = spec.annotated()  # -> Annotated[str, Meta(...)]

    Adapter Integration:
        Specs are collected in Operable, then composed via adapter:
        >>> op = Operable([name_spec, age_spec], adapter="pydantic")
        >>> Model = op.compose_structure("User")  # -> Pydantic BaseModel

    See Also:
        CommonMeta: Standard metadata keys
        Operable: Spec collection with adapter interface
    """

    base_type: type
    metadata: tuple[Meta, ...]

    def __init__(
        self,
        base_type: type | None = None,
        *args,
        metadata: tuple[Meta, ...] | None = None,
        **kw,
    ) -> None:
        """Initialize Spec with type and metadata.

        Args:
            base_type: Python type or type annotation (int, str, list[T], etc.)
            *args: Meta objects to include in metadata
            metadata: Pre-built metadata tuple (merged with args/kw)
            **kw: Key-value pairs converted to Meta objects

        Raises:
            ValueError: If base_type is not a valid type, name is invalid,
                or conflicting defaults provided
        """
        metas = CommonMeta.prepare(*args, metadata=metadata, **kw)

        meta_dict = {m.key: m.value for m in metas}
        if "name" in meta_dict:
            name_value = meta_dict["name"]
            if not isinstance(name_value, str) or not name_value:
                raise ValueError("Spec name must be a non-empty string")

        if not_sentinel(base_type, {"none"}):
            import types

            is_valid_type = (
                isinstance(base_type, type)
                or hasattr(base_type, "__origin__")
                or isinstance(base_type, types.UnionType)
            )
            if not is_valid_type:
                raise ValueError(f"base_type must be a type or type annotation, got {base_type}")

        if kw.get("default_factory") and is_coro_func(kw["default_factory"]):
            import warnings

            warnings.warn(
                "Async default factories are not yet fully supported by all adapters. "
                "Consider using sync factories for compatibility.",
                UserWarning,
                stacklevel=2,
            )

        object.__setattr__(self, "base_type", base_type)
        object.__setattr__(self, "metadata", metas)

    def __getitem__(self, key: str) -> Any:
        """Get metadata value by key.

        Raises:
            KeyError: If key not found in metadata
        """
        for meta in self.metadata:
            if meta.key == key:
                return meta.value
        raise KeyError(f"Metadata key '{key}' undefined in Spec.")

    def get(self, key: str, default: Any = Undefined) -> Any:
        """Get metadata value by key, returning default if not found."""
        with contextlib.suppress(KeyError):
            return self[key]
        return default

    @property
    def name(self) -> MaybeUndefined[str]:
        """Get the field name from metadata."""
        return self.get(CommonMeta.NAME.value)

    @property
    def is_nullable(self) -> bool:
        """Check if field is nullable."""
        return self.get(CommonMeta.NULLABLE.value) is True

    @property
    def is_listable(self) -> bool:
        """Check if field is listable."""
        return self.get(CommonMeta.LISTABLE.value) is True

    @property
    def default(self) -> MaybeUndefined[Any]:
        """Get default value or factory."""
        return self.get(
            CommonMeta.DEFAULT.value,
            self.get(CommonMeta.DEFAULT_FACTORY.value),
        )

    @property
    def has_default_factory(self) -> bool:
        """Check if this spec has a default factory."""
        return _is_factory(self.get(CommonMeta.DEFAULT_FACTORY.value))[0]

    @property
    def has_async_default_factory(self) -> bool:
        """Check if this spec has an async default factory."""
        return _is_factory(self.get(CommonMeta.DEFAULT_FACTORY.value))[1]

    @property
    def is_frozen(self) -> bool:
        """Check if this spec is marked as frozen (immutable)."""
        return self.get(CommonMeta.FROZEN.value) is True

    @property
    def is_fk(self) -> bool:
        """Check if this spec is marked as a foreign key."""
        val = self.get(CommonMeta.AS_FK.value)
        return not is_undefined(val) and val is not False

    @property
    def fk_target(self) -> MaybeUndefined[str | type]:
        """Get the FK target model reference (str name or type).

        Resolution order:
            1. Explicit target (str or type) from as_fk(target)
            2. base_type itself if Observable (has UUID id)
            3. Undefined otherwise
        """
        val = self.get(CommonMeta.AS_FK.value)
        if is_undefined(val) or val is False:
            return Undefined
        if val is not True:
            return val
        # as_fk=True: resolve from base_type if Observable
        if isinstance(self.base_type, type) and _is_observable(self.base_type):
            return self.base_type
        return Undefined

    def as_fk(self, target: str | type | None = None) -> Self:
        """Return new Spec marked as a foreign key.

        Args:
            target: Referenced model (str name or type). When provided,
                annotated() will include FKMeta(target) in the Annotated type.
                If None and base_type is Observable, target resolves to base_type.

        Example:
            >>> Spec(UUID, name="user_id").as_fk("User")
            >>> Spec(Person, name="person_id").as_fk()  # target = Person
        """
        return self.with_updates(as_fk=target if target is not None else True)

    def as_frozen(self) -> Self:
        """Return new Spec with frozen=True metadata."""
        return self.with_updates(frozen=True)

    def create_default_value(self) -> Any:
        """Create default value (sync). Raises ValueError if no default or async factory."""
        if is_undefined(self.default):
            raise ValueError("No default value or factory defined in Spec.")
        if self.has_async_default_factory:
            raise ValueError(
                "Default factory is asynchronous; cannot create default synchronously. "
                "Use 'await spec.acreate_default_value()' instead."
            )
        if self.has_default_factory:
            return self.default()  # type: ignore[operator]
        return self.default

    async def acreate_default_value(self) -> Any:
        """Create default value (async). Handles both sync/async factories."""
        if self.has_async_default_factory:
            return await self.default()  # type: ignore[operator]
        return self.create_default_value()

    def with_updates(self, **kw) -> Self:
        """Create new Spec with updated/added metadata keys. Sentinel values are excluded."""
        _filtered = [meta for meta in self.metadata if meta.key not in kw]
        for k, v in kw.items():
            if not_sentinel(v):
                _filtered.append(Meta(k, v))
        _metas = tuple(_filtered)
        return type(self)(self.base_type, metadata=_metas)

    def as_nullable(self) -> Self:
        """Return new Spec with nullable=True (allows None values)."""
        return self.with_updates(nullable=True)

    def as_listable(self) -> Self:
        """Return new Spec with listable=True (wraps type in list[T])."""
        return self.with_updates(listable=True)

    def as_optional(self) -> Self:
        """Return new Spec that is nullable with default=None."""
        return self.as_nullable().with_default(None)

    def with_default(self, default: Any) -> Self:
        """Return new Spec with default. Callables become default_factory."""
        if callable(default):
            return self.with_updates(default_factory=default)
        return self.with_updates(default=default)

    @classmethod
    def from_model(
        cls,
        model: type,
        name: str | None = None,
        *,
        nullable: bool = False,
        listable: bool = False,
        default: Any = Undefined,
    ) -> Self:
        """Create Spec from a model class (e.g., Pydantic BaseModel).

        Args:
            model: The model class to use as base_type
            name: Field name (defaults to lowercase class name)
            nullable: Whether field is nullable
            listable: Whether field is a list
            default: Default value (Undefined means no default)

        Returns:
            Spec configured for the model type

        Example:
            >>> Spec.from_model(ProgressReport)  # name="progressreport"
            >>> Spec.from_model(CodeBlock, name="blocks", listable=True, nullable=True)
        """
        field_name = name if name is not None else model.__name__.lower()
        spec = cls(base_type=model, name=field_name)

        if listable:
            spec = spec.as_listable()
        if nullable:
            spec = spec.as_nullable()
        if not_sentinel(default):
            spec = spec.with_default(default)

        return spec

    def with_validator(self, validator: Callable[..., Any] | list[Callable[..., Any]]) -> Self:
        """Return new Spec with validator function(s) attached."""
        return self.with_updates(validator=validator)

    @property
    def annotation(self) -> type[Any]:
        """Type annotation with fk/listable/nullable modifiers applied.

        When FK target resolves, produces FK[target] = Annotated[UUID, FKMeta(target)].
        Order: FK[target] -> list[T] -> T | None

        Note on type:ignore comments:
            This property performs dynamic type construction at runtime (e.g., list[t_],
            t_ | None where t_ is a variable). Python's static type system cannot track
            types constructed dynamically. These ignores are unavoidable for a Spec system
            that builds Annotated types programmatically. See PEP 593 (Annotated) and
            mypy issue #7778 for discussion of this limitation.
        """
        if is_sentinel(self.base_type, {"none"}):
            return Any
        # Dynamic type construction: mypy cannot track types built at runtime
        t_ = self.base_type  # type: ignore[valid-type]
        fk = self.fk_target
        if not is_undefined(fk):
            from uuid import UUID

            from kron.types import FKMeta

            t_ = Annotated[UUID, FKMeta(fk)]  # type: ignore[valid-type, arg-type, assignment]
        if self.is_listable:
            t_ = list[t_]  # type: ignore[valid-type]
        if self.is_nullable:
            t_ = t_ | None  # type: ignore[assignment]
        return t_  # type: ignore[return-value]

    def annotated(self) -> type[Any]:
        """Create Annotated[base_type, metadata...] with thread-safe LRU cache.

        Returns:
            Annotated type with metadata attached, suitable for Pydantic/dataclass fields.
            Nullable specs produce T | None annotation.
            FK specs produce Annotated[UUID, ..., FKMeta(target)] when target resolves.

        Note on type:ignore comments:
            This method performs dynamic type construction at runtime, building
            Annotated[T, ...] types programmatically. Python's static type system
            cannot track types constructed dynamically - this is a fundamental
            limitation when building a Spec-based type system. The ignores are
            categorized as:
            - [arg-type]: FKMeta receives resolved_fk which may be str|type|Undefined
            - [assignment]: Dynamic union construction (T | None) and cache storage
            - [attr-defined]: Annotated.__class_getitem__ access for Py 3.11-3.12
            - [misc]: Fallback operator.getitem access for Py 3.13+
            - [return-value]: Returning dynamically constructed type
        """
        cache_key = (self.base_type, self.metadata)

        with _cache_lock:
            if cache_key in _annotated_cache:
                _annotated_cache.move_to_end(cache_key)
                return _annotated_cache[cache_key]

            actual_type = Any if is_sentinel(self.base_type, {"none"}) else self.base_type
            current_metadata = self.metadata

            # Resolve FK target (explicit or Observable base_type)
            extra_annotations: list[Any] = []
            resolved_fk = self.fk_target
            if not is_undefined(resolved_fk):
                from uuid import UUID

                from kron.types import FKMeta

                actual_type = UUID  # FK fields are UUID references
                extra_annotations.append(FKMeta(resolved_fk))  # type: ignore[arg-type]

            if any(m.key == "nullable" and m.value for m in current_metadata):
                actual_type = actual_type | None  # type: ignore[assignment]

            if current_metadata or extra_annotations:
                args = [actual_type, *list(current_metadata), *extra_annotations]
                # Python 3.11-3.12 vs 3.13+ compatibility: access __class_getitem__ directly
                try:
                    result = Annotated.__class_getitem__(tuple(args))  # type: ignore[attr-defined]
                except AttributeError:
                    import operator

                    result = operator.getitem(Annotated, tuple(args))  # type: ignore[misc]
            else:
                result = actual_type  # type: ignore[misc]

            _annotated_cache[cache_key] = result  # type: ignore[assignment]

            while len(_annotated_cache) > _MAX_CACHE_SIZE:
                _annotated_cache.popitem(last=False)

        return result  # type: ignore[return-value]

    def metadict(
        self, exclude: set[str] | None = None, exclude_common: bool = False
    ) -> dict[str, Any]:
        """Convert metadata to dict, optionally excluding keys or CommonMeta keys."""
        if exclude is None:
            exclude = set()
        if exclude_common:
            exclude = exclude | set(CommonMeta.allowed())
        return {meta.key: meta.value for meta in self.metadata if meta.key not in exclude}

    def __hash__(self) -> int:
        """Hash based on base_type and metadata."""
        return hash((self.base_type, self.metadata))


def _is_observable(cls: type) -> bool:
    """Check if a type satisfies the Observable protocol (has UUID id property).

    Uses structural check rather than issubclass() for Python 3.11 compatibility
    with runtime_checkable protocols that have property members.
    """
    id_attr = getattr(cls, "id", None)
    return isinstance(id_attr, property) or (
        hasattr(cls, "__annotations__") and "id" in getattr(cls, "__annotations__", {})
    )


def _is_factory(obj: Any) -> tuple[bool, bool]:
    """Check if object is a factory function.

    Args:
        obj: Object to check

    Returns:
        Tuple of (is_factory, is_async)
    """
    if not callable(obj):
        return (False, False)
    if is_coro_func(obj):
        return (True, True)
    return (True, False)
