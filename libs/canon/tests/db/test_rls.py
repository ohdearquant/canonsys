"""Tests for RLS (Row-Level Security) SQL generation."""

from __future__ import annotations

from typing import ClassVar
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

from canon.db.migration.rls import (
    generate_composite_fks,
    generate_rls_policy,
    generate_tenant_function,
    generate_tenant_index,
    generate_tenant_scoped_unique_constraints,
    generate_tenant_unique_constraint,
    get_tenant_unique_fields,
    is_tenant_scoped,
)
from kron.types import FK

# -----------------------------------------------------------------------------
# Test Models
# -----------------------------------------------------------------------------


class MockTenantRLS(BaseModel):
    """Mock tenant for RLS testing."""

    _table_name: ClassVar[str] = "mock_tenants"
    _schema: ClassVar[str] = "public"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str


class TenantScopedModel(BaseModel):
    """Model with tenant_id - should have RLS."""

    _table_name: ClassVar[str] = "tenant_scoped"
    _schema: ClassVar[str] = "canon"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: FK[MockTenantRLS]
    name: str


class TenantScopedWithUnique(BaseModel):
    """Model with tenant-scoped unique constraint."""

    _table_name: ClassVar[str] = "tenant_unique"
    _schema: ClassVar[str] = "public"
    _primary_key: ClassVar[str] = "id"
    _unique_within_tenant: ClassVar[set[str]] = {"email", "username"}
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: FK[MockTenantRLS]
    email: str
    username: str


class NonTenantModel(BaseModel):
    """Model without tenant_id - no RLS needed."""

    _table_name: ClassVar[str] = "non_tenant"
    _schema: ClassVar[str] = "public"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str


class TenantScopedWithFK(BaseModel):
    """Model with FK to another tenant-scoped model."""

    _table_name: ClassVar[str] = "tenant_with_fk"
    _schema: ClassVar[str] = "public"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: FK[MockTenantRLS]
    parent_id: FK[TenantScopedModel] | None = None


# -----------------------------------------------------------------------------
# is_tenant_scoped Tests
# -----------------------------------------------------------------------------


class TestIsTenantScoped:
    """Tests for is_tenant_scoped function."""

    def test_tenant_scoped_returns_true(self) -> None:
        """Model with tenant_id should return True."""
        assert is_tenant_scoped(TenantScopedModel) is True

    def test_non_tenant_returns_false(self) -> None:
        """Model without tenant_id should return False."""
        assert is_tenant_scoped(NonTenantModel) is False

    def test_tenant_itself(self) -> None:
        """Tenant model itself doesn't have tenant_id."""
        assert is_tenant_scoped(MockTenantRLS) is False


# -----------------------------------------------------------------------------
# generate_tenant_function Tests
# -----------------------------------------------------------------------------


class TestGenerateTenantFunction:
    """Tests for generate_tenant_function."""

    def test_basic_function(self) -> None:
        """Basic function without role hardening."""
        sql = generate_tenant_function()
        assert "CREATE SCHEMA IF NOT EXISTS app" in sql
        assert "CREATE OR REPLACE FUNCTION app.tenant_id()" in sql
        assert "RETURNS uuid" in sql
        assert "STABLE" in sql
        assert "SECURITY DEFINER" in sql
        assert "current_setting('app.tenant_id', true)" in sql
        assert "RAISE EXCEPTION" in sql
        assert "insufficient_privilege" in sql

    def test_with_app_role_hardening(self) -> None:
        """Function with privilege hardening for app role."""
        sql = generate_tenant_function(app_role="canon_app")
        assert "REVOKE ALL ON SCHEMA app FROM canon_app" in sql
        assert "GRANT USAGE ON SCHEMA app TO canon_app" in sql
        assert "REVOKE ALL ON FUNCTION app.tenant_id() FROM PUBLIC" in sql
        assert "GRANT EXECUTE ON FUNCTION app.tenant_id() TO canon_app" in sql

    def test_fail_closed_behavior(self) -> None:
        """Function raises exception when tenant context not set."""
        sql = generate_tenant_function()
        # Verify fail-closed: exception on NULL or empty
        assert "IF v IS NULL OR v = '' THEN" in sql
        assert "RAISE EXCEPTION 'tenant context not set" in sql


# -----------------------------------------------------------------------------
# generate_tenant_index Tests
# -----------------------------------------------------------------------------


class TestGenerateTenantIndex:
    """Tests for generate_tenant_index."""

    def test_tenant_scoped_generates_index(self) -> None:
        """Tenant-scoped model gets tenant_id index."""
        sql = generate_tenant_index(TenantScopedModel)
        assert "CREATE INDEX IF NOT EXISTS ix_tenant_scoped_tenant_id" in sql
        assert 'ON "canon"."tenant_scoped"(tenant_id)' in sql

    def test_non_tenant_returns_empty(self) -> None:
        """Non-tenant model returns empty string."""
        sql = generate_tenant_index(NonTenantModel)
        assert sql == ""


# -----------------------------------------------------------------------------
# generate_tenant_unique_constraint Tests
# -----------------------------------------------------------------------------


class TestGenerateTenantUniqueConstraint:
    """Tests for generate_tenant_unique_constraint."""

    def test_tenant_scoped_generates_constraint(self) -> None:
        """Tenant-scoped model gets (tenant_id, id) unique constraint."""
        sql = generate_tenant_unique_constraint(TenantScopedModel)
        assert "ALTER TABLE" in sql
        assert "ADD CONSTRAINT uq_tenant_scoped_tenant_id" in sql
        assert "UNIQUE (tenant_id, id)" in sql

    def test_non_tenant_returns_empty(self) -> None:
        """Non-tenant model returns empty string."""
        sql = generate_tenant_unique_constraint(NonTenantModel)
        assert sql == ""


# -----------------------------------------------------------------------------
# generate_rls_policy Tests
# -----------------------------------------------------------------------------


class TestGenerateRLSPolicy:
    """Tests for generate_rls_policy."""

    def test_tenant_scoped_generates_policy(self) -> None:
        """Tenant-scoped model gets RLS policy."""
        sql = generate_rls_policy(TenantScopedModel)

        # Enable RLS
        assert 'ALTER TABLE "canon"."tenant_scoped" ENABLE ROW LEVEL SECURITY' in sql

        # Force RLS (removes owner bypass)
        assert 'ALTER TABLE "canon"."tenant_scoped" FORCE ROW LEVEL SECURITY' in sql

        # Policy creation
        assert "DROP POLICY IF EXISTS tenant_isolation_tenant_scoped" in sql
        assert 'CREATE POLICY tenant_isolation_tenant_scoped ON "canon"."tenant_scoped"' in sql
        assert "USING (tenant_id = app.tenant_id())" in sql
        assert "WITH CHECK (tenant_id = app.tenant_id())" in sql

    def test_non_tenant_returns_empty(self) -> None:
        """Non-tenant model returns empty string."""
        sql = generate_rls_policy(NonTenantModel)
        assert sql == ""

    def test_policy_name_uses_table_name(self) -> None:
        """Policy name is derived from table name."""
        sql = generate_rls_policy(TenantScopedModel)
        assert "tenant_isolation_tenant_scoped" in sql


# -----------------------------------------------------------------------------
# get_tenant_unique_fields Tests
# -----------------------------------------------------------------------------


class TestGetTenantUniqueFields:
    """Tests for get_tenant_unique_fields."""

    def test_model_with_unique_fields(self) -> None:
        """Model with _unique_within_tenant returns those fields."""
        fields = get_tenant_unique_fields(TenantScopedWithUnique)
        assert fields == {"email", "username"}

    def test_model_without_unique_fields(self) -> None:
        """Model without _unique_within_tenant returns empty set."""
        fields = get_tenant_unique_fields(TenantScopedModel)
        assert fields == set()


# -----------------------------------------------------------------------------
# generate_tenant_scoped_unique_constraints Tests
# -----------------------------------------------------------------------------


class TestGenerateTenantScopedUniqueConstraints:
    """Tests for generate_tenant_scoped_unique_constraints."""

    def test_generates_constraints_for_unique_fields(self) -> None:
        """Generates UNIQUE (tenant_id, field) for each field."""
        sql = generate_tenant_scoped_unique_constraints(TenantScopedWithUnique)
        # Both email and username should have constraints
        assert "uq_tenant_unique_tenant_email" in sql
        assert "uq_tenant_unique_tenant_username" in sql
        assert 'UNIQUE (tenant_id, "email")' in sql
        assert 'UNIQUE (tenant_id, "username")' in sql

    def test_non_tenant_returns_empty(self) -> None:
        """Non-tenant model returns empty string."""
        sql = generate_tenant_scoped_unique_constraints(NonTenantModel)
        assert sql == ""

    def test_model_without_unique_fields_returns_empty(self) -> None:
        """Tenant model without _unique_within_tenant returns empty."""
        sql = generate_tenant_scoped_unique_constraints(TenantScopedModel)
        assert sql == ""

    def test_invalid_field_raises_error(self) -> None:
        """Referencing non-existent field raises ValueError."""

        class BadUnique(BaseModel):
            _table_name: ClassVar[str] = "bad"
            _schema: ClassVar[str] = "public"
            _unique_within_tenant: ClassVar[set[str]] = {"nonexistent"}
            id: str = Field(default_factory=lambda: str(uuid4()))
            tenant_id: FK[MockTenantRLS]

        with pytest.raises(ValueError, match="non-existent field: nonexistent"):
            generate_tenant_scoped_unique_constraints(BadUnique)


# -----------------------------------------------------------------------------
# generate_composite_fks Tests
# -----------------------------------------------------------------------------


class TestGenerateCompositeFKs:
    """Tests for generate_composite_fks."""

    def test_non_tenant_returns_empty(self) -> None:
        """Non-tenant model returns empty string."""
        sql = generate_composite_fks(NonTenantModel)
        assert sql == ""

    def test_skips_tenant_id_field(self) -> None:
        """tenant_id itself is not treated as composite FK target."""
        sql = generate_composite_fks(TenantScopedModel)
        # Should not create FK for tenant_id pointing to tenant
        assert "fk_tenant_scoped_tenant_id" not in sql


# -----------------------------------------------------------------------------
# SQL Syntax Validation Tests
# -----------------------------------------------------------------------------


class TestRLSSQLSyntax:
    """Verify generated SQL is syntactically valid."""

    def test_tenant_function_semicolons(self) -> None:
        """Tenant function has proper semicolons."""
        sql = generate_tenant_function()
        # Should end with semicolon or $fn$;
        assert sql.strip().endswith(";")

    def test_index_proper_quoting(self) -> None:
        """Index uses proper identifier quoting."""
        sql = generate_tenant_index(TenantScopedModel)
        # Schema and table should be quoted
        assert '"canon"."tenant_scoped"' in sql

    def test_policy_proper_quoting(self) -> None:
        """Policy uses proper identifier quoting."""
        sql = generate_rls_policy(TenantScopedModel)
        assert '"canon"."tenant_scoped"' in sql

    def test_constraint_proper_quoting(self) -> None:
        """Constraint uses proper identifier quoting."""
        sql = generate_tenant_unique_constraint(TenantScopedModel)
        assert '"canon"."tenant_scoped"' in sql

    def test_unique_constraint_field_quoting(self) -> None:
        """Unique constraint quotes field names."""
        sql = generate_tenant_scoped_unique_constraints(TenantScopedWithUnique)
        assert '"email"' in sql
        assert '"username"' in sql
