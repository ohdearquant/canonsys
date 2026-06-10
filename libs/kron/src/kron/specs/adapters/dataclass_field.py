"""DataClass SpecAdapter: Spec <-> dataclass fields.

Supports bidirectional transformation for Python dataclasses:
    - Frozen: Immutable, slots=True
    - Mutable: Standard dataclass with slots=True
    - Field validators via __field_validators__ mechanism
"""

from __future__ import annotations

from dataclasses import MISSING as DATACLASS_MISSING, dataclass, field as dc_field, fields
from typing import TYPE_CHECKING, Any

from kron.types import Unset, UnsetType, is_sentinel

from ..protocol import SpecAdapter
from ..spec import Spec
from ._utils import resolve_annotation_to_base_types

if TYPE_CHECKING:
    from ..operable import Operable


__all__ = ("DataClassSpecAdapter",)


def _field_to_spec(field_name: str, field_obj: Any, annotation: Any) -> Spec:
    """Convert dataclass field to Spec, preserving defaults and type modifiers."""

    base_metas = resolve_annotation_to_base_types(annotation)
    spec = Spec(name=field_name, **base_metas)

    # Handle defaults
    if field_obj.default is not DATACLASS_MISSING:
        spec = spec.with_default(field_obj.default)
    elif field_obj.default_factory is not DATACLASS_MISSING:
        spec = spec.with_default(field_obj.default_factory)

    return spec


def _make_validator_method(validators: dict[str, list[Any]], is_frozen: bool) -> Any:
    """Create _validate method that runs field validators. Uses object.__setattr__ for frozen classes."""

    def _validate_with_field_validators(self) -> None:
        """Validate instance including field validators."""
        field_validators = getattr(type(self), "__field_validators__", {})
        errors: list[Exception] = []

        for fname, validator_list in field_validators.items():
            value = getattr(self, fname, None)
            for validator in validator_list:
                try:
                    result = validator(value)
                    if result is not None and result is not value:
                        if is_frozen:
                            object.__setattr__(self, fname, result)
                        else:
                            setattr(self, fname, result)
                except Exception as e:
                    errors.append(ValueError(f"Validation failed for '{fname}': {e}"))

        if errors:
            raise ExceptionGroup(f"Field validation failed for {type(self).__name__}", errors)

    return _validate_with_field_validators


class DataClassSpecAdapter(SpecAdapter[dict[str, Any]]):
    """DataClass adapter: Spec -> dataclass fields, Operable -> dataclass.

    Supports both frozen and mutable targets with optional field validators.

    Usage:
        op = Operable([
            Spec(str, name="name", validator=validate_name),
            Spec(int, name="age", default=0),
        ])
        Person = DataClassSpecAdapter.compose_structure(op, "Person", frozen=True)
        p = Person(name="Alice", age=30)
    """

    @classmethod
    def create_field(cls, spec: Spec) -> dict[str, Any]:
        """Convert Spec to dataclass field kwargs (default or default_factory)."""
        field_kwargs: dict[str, Any] = {}

        default_val = spec.get("default")
        default_factory = spec.get("default_factory")

        if not is_sentinel(default_factory, {"none"}):
            field_kwargs["default_factory"] = default_factory
        elif not is_sentinel(default_val, {"none"}):
            field_kwargs["default"] = default_val
        elif spec.is_nullable:
            field_kwargs["default"] = None

        return field_kwargs

    @classmethod
    def create_field_validator(cls, spec: Spec) -> dict[str, list[Any]] | None:
        """Extract validators from Spec. Returns {field_name: [validators]} or None."""
        validator = spec.get("validator")
        if is_sentinel(validator):
            return None

        field_name = spec.name or "field"
        validators = validator if isinstance(validator, list) else [validator]

        return {field_name: validators}

    @classmethod
    def compose_structure(
        cls,
        op: Operable,
        name: str,
        /,
        *,
        include: set[str] | UnsetType = Unset,
        exclude: set[str] | UnsetType = Unset,
        frozen: bool = True,
        base_type: type | None = None,
        doc: str | None = None,
        **kwargs: Any,
    ) -> type:
        """Generate dataclass from Operable.

        Args:
            op: Operable containing Specs
            name: Class name
            include/exclude: Field name filters
            frozen: True for frozen dataclass, False for mutable
            base_type: Custom base class
            doc: Optional docstring

        Returns:
            Dynamically created dataclass with validators wired in
        """
        use_specs = op.get_specs(include=include, exclude=exclude)

        base = base_type if base_type is not None else object

        annotations: dict[str, type] = {}
        class_attrs: dict[str, Any] = {}
        validators: dict[str, list[Any]] = {}

        required_specs = []
        optional_specs = []

        for spec in use_specs:
            if not spec.name:
                continue
            field_kwargs = cls.create_field(spec)
            if "default" in field_kwargs or "default_factory" in field_kwargs:
                optional_specs.append((spec, field_kwargs))
            else:
                required_specs.append((spec, field_kwargs))

        for spec, field_kwargs in required_specs + optional_specs:
            field_name = spec.name
            annotations[field_name] = spec.annotation

            if "default_factory" in field_kwargs:
                class_attrs[field_name] = dc_field(default_factory=field_kwargs["default_factory"])
            elif "default" in field_kwargs:
                class_attrs[field_name] = field_kwargs["default"]

            if v := cls.create_field_validator(spec):
                validators.update(v)

        class_dict: dict[str, Any] = {
            "__annotations__": annotations,
            "__module__": op.name or "__dynamic__",
            **class_attrs,
        }

        if doc:
            class_dict["__doc__"] = doc

        if validators:
            class_dict["__field_validators__"] = validators
            class_dict["_validate"] = _make_validator_method(validators, frozen)

        new_cls = type(name, (base,), class_dict)

        if frozen:
            new_cls = dataclass(frozen=True, slots=True)(new_cls)
        else:
            new_cls = dataclass(slots=True)(new_cls)

        return new_cls

    @classmethod
    def validate_instance(cls, structure: type, data: dict, /) -> Any:
        """Create dataclass instance from dict data."""
        return structure(**data)

    @classmethod
    def dump_instance(cls, instance: Any, **kwargs) -> dict[str, Any]:
        """Dump dataclass instance to dict."""
        from dataclasses import asdict

        return asdict(instance)

    @classmethod
    def extract_specs(cls, structure: type) -> tuple[Spec, ...]:
        """Extract Specs from dataclass, preserving defaults and type modifiers.

        Raises:
            TypeError: If structure is not a dataclass
        """
        from dataclasses import is_dataclass

        if not is_dataclass(structure):
            raise TypeError(f"structure must be a dataclass, got {type(structure)}")

        specs: list[Spec] = []
        for f in fields(structure):
            if f.name.startswith("_"):
                continue

            annotation = structure.__annotations__.get(f.name, Any)
            spec = _field_to_spec(f.name, f, annotation)
            specs.append(spec)

        return tuple(specs)
