"""Tests for Spec - framework-agnostic field specification."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import BaseModel

from kron.specs.operable import Operable
from kron.specs.spec import CommonMeta, Spec
from kron.types import Undefined


class TestSpecCreation:
    """Test Spec initialization."""

    def test_basic_spec(self):
        """Spec should accept base_type and name."""
        spec = Spec(str, name="username")

        assert spec.base_type is str
        assert spec.name == "username"

    def test_spec_with_metadata(self):
        """Spec should store metadata tuple."""
        spec = Spec(int, name="count", nullable=True)

        assert spec.is_nullable is True
        assert spec.get("nullable") is True

    def test_spec_without_name_has_undefined_name(self):
        """Spec without name should return Undefined."""
        spec = Spec(str)

        assert spec.name is Undefined

    def test_spec_empty_name_raises(self):
        """Spec with empty name should raise ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            Spec(str, name="")

    def test_spec_invalid_type_raises(self):
        """Spec with non-type base_type should raise ValueError."""
        with pytest.raises(ValueError, match="must be a type"):
            Spec(42, name="invalid")


class TestSpecModifiers:
    """Test Spec modifier methods."""

    def test_as_nullable(self):
        """as_nullable() should return new Spec with nullable=True."""
        spec = Spec(str, name="field")
        nullable_spec = spec.as_nullable()

        assert spec.is_nullable is False
        assert nullable_spec.is_nullable is True

    def test_as_listable(self):
        """as_listable() should return new Spec with listable=True."""
        spec = Spec(str, name="tags")
        list_spec = spec.as_listable()

        assert spec.is_listable is False
        assert list_spec.is_listable is True

    def test_as_optional(self):
        """as_optional() should be nullable with default=None."""
        spec = Spec(str, name="field")
        optional_spec = spec.as_optional()

        assert optional_spec.is_nullable is True
        assert optional_spec.default is None

    def test_with_default_static(self):
        """with_default() should set static default."""
        spec = Spec(int, name="count")
        defaulted = spec.with_default(42)

        assert defaulted.default == 42
        assert defaulted.has_default_factory is False

    def test_with_default_factory(self):
        """with_default() with callable should set default_factory."""
        spec = Spec(list, name="items")
        defaulted = spec.with_default(list)

        assert defaulted.has_default_factory is True

    def test_with_validator(self):
        """with_validator() should attach validator function."""
        validator = lambda x: x >= 0
        spec = Spec(int, name="positive").with_validator(validator)

        assert spec.get("validator") is validator

    def test_as_frozen(self):
        """as_frozen() should mark field as immutable."""
        spec = Spec(str, name="id").as_frozen()

        assert spec.is_frozen is True

    def test_as_fk(self):
        """as_fk() should mark field as foreign key."""
        spec = Spec(UUID, name="user_id").as_fk("User")

        assert spec.is_fk is True
        assert spec.fk_target == "User"


class TestSpecChaining:
    """Test Spec method chaining."""

    def test_chain_multiple_modifiers(self):
        """Multiple modifiers should chain correctly."""
        spec = Spec(str, name="tags").as_listable().as_nullable().with_default([])

        assert spec.is_listable is True
        assert spec.is_nullable is True
        assert spec.default == []

    def test_with_updates_preserves_existing(self):
        """with_updates() should preserve unmodified metadata."""
        spec = Spec(str, name="field", nullable=True)
        updated = spec.with_updates(frozen=True)

        assert updated.name == "field"
        assert updated.is_nullable is True
        assert updated.is_frozen is True


class TestSpecAnnotation:
    """Test Spec type annotation generation."""

    def test_annotation_basic(self):
        """annotation should return base_type for simple spec."""
        spec = Spec(str, name="field")

        assert spec.annotation is str

    def test_annotation_nullable(self):
        """annotation should return T | None for nullable spec."""
        spec = Spec(str, name="field").as_nullable()
        ann = spec.annotation

        # Check it's a union type with None
        assert hasattr(ann, "__args__") or "None" in str(ann)

    def test_annotation_listable(self):
        """annotation should return list[T] for listable spec."""
        spec = Spec(str, name="tags").as_listable()
        ann = spec.annotation

        assert "list" in str(ann).lower()

    def test_annotated_caches_result(self):
        """annotated() should be cached."""
        spec = Spec(str, name="field")

        result1 = spec.annotated()
        result2 = spec.annotated()

        assert result1 is result2


class TestSpecDefaults:
    """Test Spec default value handling."""

    def test_create_default_value_static(self):
        """create_default_value() should return static default."""
        spec = Spec(int, name="count", default=42)

        assert spec.create_default_value() == 42

    def test_create_default_value_factory(self):
        """create_default_value() should call factory."""
        spec = Spec(list, name="items", default_factory=list)

        result = spec.create_default_value()

        assert result == []
        assert result is not spec.create_default_value()  # new instance each time

    def test_create_default_raises_if_undefined(self):
        """create_default_value() should raise if no default."""
        spec = Spec(str, name="required")

        with pytest.raises(ValueError, match="No default"):
            spec.create_default_value()


class TestSpecFromModel:
    """Test Spec.from_model factory."""

    def test_from_model_basic(self):
        """from_model should create Spec from model class."""

        class UserModel(BaseModel):
            pass

        spec = Spec.from_model(UserModel)

        assert spec.base_type is UserModel
        assert spec.name == "usermodel"

    def test_from_model_with_name(self):
        """from_model should accept custom name."""

        class UserModel(BaseModel):
            pass

        spec = Spec.from_model(UserModel, name="user")

        assert spec.name == "user"

    def test_from_model_with_modifiers(self):
        """from_model should accept listable and nullable."""

        class ItemModel(BaseModel):
            pass

        spec = Spec.from_model(ItemModel, name="items", listable=True, nullable=True)

        assert spec.is_listable is True
        assert spec.is_nullable is True


class TestSpecMetadata:
    """Test Spec metadata access."""

    def test_getitem_returns_value(self):
        """spec[key] should return metadata value."""
        spec = Spec(str, name="field", nullable=True)

        assert spec["name"] == "field"
        assert spec["nullable"] is True

    def test_getitem_raises_keyerror(self):
        """spec[key] should raise KeyError if not found."""
        spec = Spec(str, name="field")

        with pytest.raises(KeyError):
            _ = spec["nonexistent"]

    def test_get_with_default(self):
        """get() should return default if not found."""
        spec = Spec(str, name="field")

        assert spec.get("nonexistent", "default") == "default"

    def test_metadict(self):
        """metadict() should return dict of metadata."""
        spec = Spec(str, name="field", nullable=True, frozen=True)

        meta_dict = spec.metadict()

        assert meta_dict["name"] == "field"
        assert meta_dict["nullable"] is True
        assert meta_dict["frozen"] is True

    def test_metadict_exclude(self):
        """metadict(exclude) should exclude specified keys."""
        spec = Spec(str, name="field", nullable=True)

        meta_dict = spec.metadict(exclude={"name"})

        assert "name" not in meta_dict
        assert "nullable" in meta_dict


class TestCommonMeta:
    """Test CommonMeta enum and validation."""

    def test_allowed_returns_values(self):
        """allowed() should return tuple of valid values."""
        allowed = CommonMeta.allowed()

        assert "name" in allowed
        assert "nullable" in allowed
        assert "default" in allowed

    def test_default_and_factory_mutually_exclusive(self):
        """Cannot provide both default and default_factory."""
        with pytest.raises(ExceptionGroup):
            CommonMeta.prepare(default=42, default_factory=list)

    def test_factory_must_be_callable(self):
        """default_factory must be callable."""
        with pytest.raises(ExceptionGroup):
            CommonMeta.prepare(default_factory=42)

    def test_validator_must_be_callable(self):
        """validator must be callable."""
        with pytest.raises(ExceptionGroup):
            CommonMeta.prepare(validator=42)


class TestOperable:
    """Test Operable Spec collection."""

    def test_operable_creation(self):
        """Operable should accept list of Specs."""
        specs = [Spec(str, name="title"), Spec(int, name="count")]
        op = Operable(specs)

        assert len(op.__op_fields__) == 2

    def test_operable_duplicate_names_raises(self):
        """Operable should reject duplicate field names."""
        specs = [Spec(str, name="field"), Spec(int, name="field")]

        with pytest.raises(ValueError, match="Duplicate field names"):
            Operable(specs)

    def test_operable_non_spec_raises(self):
        """Operable should reject non-Spec items."""
        with pytest.raises(TypeError, match="must be Spec objects"):
            Operable(["not a spec"])

    def test_operable_allowed(self):
        """allowed() should return field names."""
        specs = [Spec(str, name="title"), Spec(int, name="count")]
        op = Operable(specs)

        assert op.allowed() == frozenset({"title", "count"})

    def test_operable_get(self):
        """get() should return Spec by name."""
        title_spec = Spec(str, name="title")
        op = Operable([title_spec, Spec(int, name="count")])

        result = op.get("title")

        assert result is title_spec

    def test_operable_extend(self):
        """extend() should create new Operable with additional specs."""
        op = Operable([Spec(str, name="title")])
        extended = op.extend([Spec(int, name="count")])

        assert op.allowed() == frozenset({"title"})
        assert extended.allowed() == frozenset({"title", "count"})

    def test_operable_extend_overrides(self):
        """extend() should override existing specs by name."""
        op = Operable([Spec(str, name="field")])
        extended = op.extend([Spec(int, name="field")])

        field_spec = extended.get("field")
        assert field_spec.base_type is int

    def test_operable_compose_structure(self):
        """compose_structure should create Pydantic model."""
        specs = [
            Spec(str, name="title"),
            Spec(int, name="count", default=0),
        ]
        op = Operable(specs, adapter="pydantic")

        Model = op.compose_structure("TestModel")

        assert issubclass(Model, BaseModel)
        instance = Model(title="Test")
        assert instance.title == "Test"
        assert instance.count == 0
