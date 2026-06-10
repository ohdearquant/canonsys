"""Operable: Ordered Spec collection for framework-agnostic schema definition.

Operable collects Spec objects into a semantic namespace with unique field names,
then delegates structure composition to framework-specific adapters (Pydantic, SQL, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from kron.types import MaybeUnset, Unset, UnsetType, is_unset, not_sentinel

from .adapters.factory import AdapterType, get_adapter
from .protocol import SpecAdapter
from .spec import Spec

if TYPE_CHECKING:
    from pydantic import BaseModel

__all__ = ("Operable",)

DEFAULT_ADAPTER: AdapterType = "pydantic"


@dataclass(frozen=True, slots=True)
class Operable:
    """Ordered Spec collection for framework-agnostic schema definition.

    Operable collects Spec objects into a semantic namespace with unique field names,
    then delegates structure composition to framework-specific adapters (Pydantic, SQL, etc.).

    Design:
        - Immutable: frozen dataclass, specs cannot change after creation
        - Ordered: field order preserved for serialization consistency
        - Adapter-agnostic: same Operable works with any supported framework
        - Composable: extend() for schema inheritance/override patterns

    Attributes:
        __op_fields__: Ordered tuple of Spec objects
        __adapter_name__: Adapter identifier ("pydantic", "sql", "dataclass")
        name: Optional schema name (used as default model name)

    Usage:
        # Define specs and compose into model
        specs = [Spec(str, name="title"), Spec(int, name="count")]
        op = Operable(specs, adapter="pydantic")
        Model = op.compose_structure("Record")

        # Extend existing schema
        extended = op.extend([Spec(float, name="score")])

        # Extract specs from existing model
        op = Operable.from_structure(ExistingModel, "pydantic")

    Adapter Interface:
        All framework operations go through op.adapter:
        - op.adapter.compose_structure(op, name) -> framework model class
        - op.adapter.validate_instance(Model, data) -> validated instance
        - op.adapter.extract_specs(Model) -> tuple of Specs

    See Also:
        Spec: Individual field specification
        get_adapter: Factory for adapter classes
    """

    __op_fields__: tuple[Spec, ...]
    __adapter_name__: str
    name: MaybeUnset[str | None] = Unset

    def __init__(
        self,
        specs: tuple[Spec, ...] | list[Spec] = tuple(),
        *,
        name: MaybeUnset[str | None] = Unset,
        adapter: AdapterType = DEFAULT_ADAPTER,
    ):
        """Initialize Operable with Spec collection and adapter.

        Args:
            specs: Tuple or list of Spec objects (order preserved)
            name: Schema name (defaults model name in compose_structure)
            adapter: Framework adapter ("pydantic", "sql", "dataclass")

        Raises:
            TypeError: If specs contains non-Spec objects
            ValueError: If duplicate field names detected
        """
        if isinstance(specs, list):
            specs = tuple(specs)

        for i, item in enumerate(specs):
            if not isinstance(item, Spec):
                raise TypeError(
                    f"All specs must be Spec objects, got {type(item).__name__} at index {i}"
                )

        names = [s.name for s in specs if s.name is not None]
        if len(names) != len(set(names)):
            from collections import Counter

            duplicates = [name for name, count in Counter(names).items() if count > 1]
            raise ValueError(
                f"Duplicate field names found: {duplicates}. Each spec must have a unique name."
            )

        object.__setattr__(self, "__op_fields__", specs)
        object.__setattr__(self, "__adapter_name__", adapter)
        object.__setattr__(self, "name", name)

    @property
    def adapter(self) -> type[SpecAdapter]:
        """Get adapter class for this Operable."""
        return get_adapter(self.__adapter_name__)

    def allowed(self) -> frozenset[str]:
        """Return set of valid field names from all specs."""
        return frozenset({i.name for i in self.__op_fields__})

    def check_allowed(self, *args, as_boolean: bool = False):
        """Validate field names exist in this Operable.

        Args:
            *args: Field names to check
            as_boolean: If True, return bool instead of raising

        Returns:
            True if all names valid, False if as_boolean=True and invalid

        Raises:
            ValueError: If any name invalid and as_boolean=False
        """
        if not set(args).issubset(self.allowed()):
            if as_boolean:
                return False
            raise ValueError(
                f"Some specified fields are not allowed: {set(args).difference(self.allowed())}"
            )
        return True

    def get(self, key: str, /, default=Unset) -> MaybeUnset[Spec]:
        """Get Spec by field name, returning default if not found."""
        if not self.check_allowed(key, as_boolean=True):
            return default
        for i in self.__op_fields__:
            if i.name == key:
                return i
        return default

    def extend(
        self,
        specs: list[Spec] | tuple[Spec, ...],
        *,
        name: MaybeUnset[str | None] = Unset,
        adapter: AdapterType | None = None,
    ) -> Operable:
        """Create new Operable with additional specs (overrides existing by name).

        Args:
            specs: Additional Spec objects to append/override
            name: Override name (defaults to self.name)
            adapter: Override adapter (defaults to self.__adapter_name__)

        Returns:
            New Operable with combined specs. If a spec in `specs` has the
            same name as an existing spec, the new spec replaces the old one.

        Example:
            extended = AUDIT_SPECS.extend([
                spec_embedding(1536),
                spec_content(JobContent),  # Overrides SPEC_CONTENT_JSONB
            ])
            Model = extended.compose_structure("Job", include={...}, base_type=Node)
        """
        new_names = {s.name for s in specs if s.name}
        combined = [s for s in self.__op_fields__ if s.name not in new_names]
        combined.extend(specs)

        return Operable(
            combined,
            name=name or self.name,
            adapter=adapter or self.__adapter_name__,
        )

    def get_specs(
        self,
        *,
        include: set[str] | UnsetType = Unset,
        exclude: set[str] | UnsetType = Unset,
    ) -> tuple[Spec, ...]:
        """Get filtered specs by include/exclude field names.

        Args:
            include: Only return specs with these names (mutually exclusive with exclude)
            exclude: Exclude specs with these names (mutually exclusive with include)

        Returns:
            Filtered tuple of Spec objects

        Raises:
            ValueError: If both include and exclude specified, or invalid names
        """
        if not_sentinel(include) and not_sentinel(exclude):
            raise ValueError("Cannot specify both include and exclude")

        if not_sentinel(include):
            if self.check_allowed(*include, as_boolean=True) is False:
                raise ValueError(
                    "Some specified fields are not allowed: "
                    f"{set(include).difference(self.allowed())}"
                )
            return tuple(self.get(i) for i in include if not is_unset(self.get(i)))  # type: ignore[misc]

        if not_sentinel(exclude):
            _discards = {self.get(i) for i in exclude if not is_unset(self.get(i))}
            return tuple(s for s in self.__op_fields__ if s not in _discards)

        return self.__op_fields__

    def compose_structure(
        self,
        name: str | UnsetType = Unset,
        *,
        include: set[str] | UnsetType = Unset,
        exclude: set[str] | UnsetType = Unset,
        **kw,
    ):
        """Compose a typed structure from specs via adapter.

        Args:
            name: Structure name (default: self.name or "DynamicStructure")
            include: Only include these field names
            exclude: Exclude these field names
            **kw: Additional adapter-specific kwargs

        Returns:
            Framework structure (e.g., Pydantic BaseModel, SQL DDL)
        """
        # Determine structure name: explicit > operable.name > fallback
        if is_unset(name):
            structure_name = self.name or "DynamicStructure"
        else:
            structure_name = name
        return self.adapter.compose_structure(
            self,
            structure_name,
            include=include,
            exclude=exclude,
            **kw,
        )

    @classmethod
    def from_structure(
        cls,
        structure: type[BaseModel],
        *,
        adapter: AdapterType = DEFAULT_ADAPTER,
        name: MaybeUnset[str | None] = Unset,
    ) -> Self:
        """Create Operable by extracting specs from a structure.

        Disassembles a structure and returns an Operable with Specs
        representing top-level fields.

        Args:
            structure: Structure class to extract specs from (e.g., Pydantic BaseModel)
            name: Optional operable name (defaults to structure class name)
            adapter: Adapter type for the operable

        Returns:
            Operable with Specs for each top-level field

        Example:
            >>> class MyModel(BaseModel):
            ...     name: str
            ...     age: int = 0
            ...     tags: list[str] | None = None
            >>> op = Operable.from_structure(MyModel, "pydantic")
            >>> op.allowed()  # {'name', 'age', 'tags'}
        """
        specs = get_adapter(adapter).extract_specs(structure)
        return cls(
            specs=specs,
            name=name or structure.__name__,
            adapter=adapter,
        )

    def validate_instance(self, structure: Any, data: dict, /) -> Any:
        """Validate data instance against this Operable's structure.

        Args:
            instance: Data instance to validate (e.g., dict, dataclass)

        Returns:
            Validated instance (may be transformed by adapter)

        Raises:
            ValidationError: If validation fails
        """
        specs = self.adapter.extract_specs(structure)
        if not {s.name for s in specs}.issubset(self.allowed()):
            raise ValueError("Structure contains fields not defined in this Operable")

        return self.adapter.validate_instance(structure, data)

    def dump_instance(self, instance: Any) -> dict:
        """Dump data instance to dict via this Operable's structure.

        Args:
            instance: Data instance to dump (e.g., Pydantic model, dataclass)

        Returns:
            Dict representation of the instance
        """
        return self.adapter.dump_instance(instance, self)

    def __hash__(self) -> int:
        """Hash based on fields, adapter name, and name."""
        return hash((self.__op_fields__, self.__adapter_name__, self.name))
