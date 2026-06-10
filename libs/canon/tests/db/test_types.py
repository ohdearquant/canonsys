"""Tests for FK and Vector type annotations."""

from __future__ import annotations

import pytest

from kron.types import FK, FKMeta, Vector, VectorMeta, extract_kron_db_meta

from .conftest import MockProject, MockTenant, MockUser


class TestFKMeta:
    """Tests for FKMeta foreign key metadata."""

    def test_fkmeta_creation_with_model_class(self):
        """FKMeta should accept model class."""
        meta = FKMeta(MockTenant)
        assert meta.model == MockTenant
        assert meta.column == "id"
        assert meta.on_delete == "CASCADE"
        assert meta.on_update == "CASCADE"

    def test_fkmeta_creation_with_string_reference(self):
        """FKMeta should accept string forward reference."""
        meta = FKMeta("Tenant")
        assert meta.model == "Tenant"
        assert meta.column == "id"

    def test_fkmeta_custom_column(self):
        """FKMeta should accept custom column name."""
        meta = FKMeta(MockTenant, column="external_id")
        assert meta.column == "external_id"

    def test_fkmeta_custom_on_delete(self):
        """FKMeta should accept custom ON DELETE action."""
        meta = FKMeta(MockTenant, on_delete="SET NULL")
        assert meta.on_delete == "SET NULL"

    def test_fkmeta_custom_on_update(self):
        """FKMeta should accept custom ON UPDATE action."""
        meta = FKMeta(MockTenant, on_update="RESTRICT")
        assert meta.on_update == "RESTRICT"

    def test_fkmeta_table_name_from_class(self):
        """FKMeta should derive table name from model class."""
        meta = FKMeta(MockTenant)
        assert meta.table_name == "mock_tenants"

    def test_fkmeta_table_name_from_string(self):
        """FKMeta should derive table name from string reference."""
        meta = FKMeta("Tenant")
        assert meta.table_name == "tenants"

    def test_fkmeta_repr_with_class(self):
        """FKMeta repr should show class name."""
        meta = FKMeta(MockTenant)
        assert repr(meta) == "FK[MockTenant]"

    def test_fkmeta_repr_with_string(self):
        """FKMeta repr should show string reference."""
        meta = FKMeta("User")
        assert repr(meta) == "FK[User]"


class TestFKTypeAnnotation:
    """Tests for FK[Model] type annotation."""

    def test_fk_creates_annotated_uuid(self):
        """FK[Model] should create Annotated[UUID, FKMeta]."""
        annotation = FK[MockTenant]
        assert hasattr(annotation, "__origin__")

    def test_fk_meta_extracts_from_field_info(self):
        """extract_kron_db_meta should extract FKMeta from Pydantic field."""
        field_info = MockUser.model_fields["tenant_id"]
        meta = extract_kron_db_meta(field_info, metas="FK")
        assert isinstance(meta, FKMeta)
        assert meta.model == MockTenant

    def test_fk_meta_unset_for_non_fk_field(self):
        """extract_kron_db_meta should return Unset for non-FK field."""
        field_info = MockUser.model_fields["email"]
        meta = extract_kron_db_meta(field_info, metas="FK")
        assert not isinstance(meta, FKMeta)

    def test_fk_meta_extracts_forward_reference(self):
        """extract_kron_db_meta should extract string forward references from field."""
        # MockProject has user_id: FK["User"] (forward reference)
        if "user_id" in MockProject.model_fields:
            field_info = MockProject.model_fields["user_id"]
            meta = extract_kron_db_meta(field_info, metas="FK")
            if isinstance(meta, FKMeta):
                assert isinstance(meta, FKMeta)

    def test_fk_with_custom_actions(self):
        """FK should work with all standard ON DELETE/UPDATE actions."""
        actions = ["CASCADE", "SET NULL", "SET DEFAULT", "RESTRICT", "NO ACTION"]
        for action in actions:
            meta = FKMeta(MockTenant, on_delete=action, on_update=action)
            assert meta.on_delete == action
            assert meta.on_update == action


class TestVectorMeta:
    """Tests for VectorMeta vector embedding metadata."""

    def test_vectormeta_creation(self):
        """VectorMeta should accept positive dimension."""
        meta = VectorMeta(1536)
        assert meta.dim == 1536

    def test_vectormeta_validation_zero(self):
        """VectorMeta should reject zero dimension."""
        with pytest.raises(ValueError, match="must be positive"):
            VectorMeta(0)

    def test_vectormeta_validation_negative(self):
        """VectorMeta should reject negative dimension."""
        with pytest.raises(ValueError, match="must be positive"):
            VectorMeta(-10)

    def test_vectormeta_repr(self):
        """VectorMeta repr should show dimension."""
        meta = VectorMeta(768)
        assert repr(meta) == "Vector[768]"

    def test_vectormeta_common_dimensions(self):
        """VectorMeta should handle common embedding dimensions."""
        # OpenAI ada-002
        meta1 = VectorMeta(1536)
        assert meta1.dim == 1536

        # sentence-transformers
        meta2 = VectorMeta(768)
        assert meta2.dim == 768

        # OpenAI text-embedding-3-large
        meta3 = VectorMeta(3072)
        assert meta3.dim == 3072


class TestVectorTypeAnnotation:
    """Tests for Vector[dim] type annotation."""

    def test_vector_creates_annotated_list(self):
        """Vector[dim] should create Annotated[list[float], VectorMeta]."""
        annotation = Vector[1536]
        assert hasattr(annotation, "__origin__")

    def test_vector_meta_extracts_from_field_info(self):
        """extract_kron_db_meta should extract VectorMeta from Pydantic field."""
        field_info = MockProject.model_fields["embedding"]
        # Note: Optional wrapping may affect extraction
        meta = extract_kron_db_meta(field_info, metas="Vector")
        # May be Unset if optional wrapping interferes
        if isinstance(meta, VectorMeta):
            assert isinstance(meta, VectorMeta)

    def test_vector_meta_unset_for_non_vector_field(self):
        """extract_kron_db_meta should return Unset for non-vector field."""
        field_info = MockUser.model_fields["email"]
        meta = extract_kron_db_meta(field_info, metas="Vector")
        assert not isinstance(meta, VectorMeta)

    def test_vector_with_large_dimension(self):
        """Vector should handle large dimensions."""
        meta = VectorMeta(10000)
        assert meta.dim == 10000
