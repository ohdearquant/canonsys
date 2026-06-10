"""Tests for database role SQL generation."""

from __future__ import annotations

from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel, Field

from canon.db.migration.roles import (
    RoleConfig,
    generate_database_roles,
    generate_table_ownership,
)

# -----------------------------------------------------------------------------
# Test Models
# -----------------------------------------------------------------------------


class MockEntity(BaseModel):
    """Mock entity for ownership testing."""

    _table_name: ClassVar[str] = "mock_entities"
    _schema: ClassVar[str] = "public"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str


class CustomSchemaEntity(BaseModel):
    """Entity with custom schema."""

    _table_name: ClassVar[str] = "custom_table"
    _schema: ClassVar[str] = "canon"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))


# -----------------------------------------------------------------------------
# RoleConfig Tests
# -----------------------------------------------------------------------------


class TestRoleConfig:
    """Tests for RoleConfig dataclass."""

    def test_default_values(self) -> None:
        """RoleConfig has sensible defaults."""
        config = RoleConfig()
        assert config.owner == "canon_owner"
        assert config.app == "canon_app"
        assert config.support == "canon_support"
        assert config.analytics == "canon_analytics"
        assert config.password_owner is None
        assert config.password_app is None

    def test_custom_values(self) -> None:
        """RoleConfig accepts custom values."""
        config = RoleConfig(
            owner="custom_owner",
            app="custom_app",
            password_owner="secret123",
        )
        assert config.owner == "custom_owner"
        assert config.app == "custom_app"
        assert config.password_owner == "secret123"


# -----------------------------------------------------------------------------
# generate_database_roles Tests
# -----------------------------------------------------------------------------


class TestGenerateDatabaseRoles:
    """Tests for generate_database_roles."""

    def test_generates_four_roles(self) -> None:
        """Generates SQL for all four roles."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        # All four roles should be created
        assert "canon_owner" in sql
        assert "canon_app" in sql
        assert "canon_support" in sql
        assert "canon_analytics" in sql

    def test_owner_role_properties(self) -> None:
        """Owner role has correct properties."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        # Owner gets full control
        assert "GRANT ALL ON SCHEMA public TO canon_owner" in sql
        assert "GRANT ALL ON SCHEMA app TO canon_owner" in sql

    def test_app_role_security_restrictions(self) -> None:
        """App role has proper security restrictions."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        # Critical: App role must NOT be superuser and must NOT bypass RLS
        assert "NOSUPERUSER" in sql
        assert "NOBYPASSRLS" in sql
        assert "NOCREATEDB" in sql
        assert "NOCREATEROLE" in sql
        assert "NOINHERIT" in sql

    def test_app_role_gets_dml_privileges(self) -> None:
        """App role gets SELECT, INSERT, UPDATE, DELETE."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES" in sql
        assert "TO canon_app" in sql

    def test_analytics_role_read_only(self) -> None:
        """Analytics role only gets SELECT."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        # Analytics gets SELECT only
        assert "GRANT SELECT ON ALL TABLES IN SCHEMA public TO canon_analytics" in sql

    def test_password_inclusion_when_provided(self) -> None:
        """Passwords included when provided."""
        config = RoleConfig(
            password_owner="owner_pass",
            password_app="app_pass",
        )
        sql = generate_database_roles(config)

        assert "PASSWORD 'owner_pass'" in sql
        assert "PASSWORD 'app_pass'" in sql

    def test_no_password_when_not_provided(self) -> None:
        """No PASSWORD clause when not provided."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        # Should not have PASSWORD clause (would be empty quotes)
        assert "PASSWORD ''" not in sql

    def test_custom_schema(self) -> None:
        """Supports custom schema."""
        config = RoleConfig()
        sql = generate_database_roles(config, schema="canon")

        assert "GRANT ALL ON SCHEMA canon TO canon_owner" in sql
        assert "GRANT USAGE ON SCHEMA canon TO canon_app" in sql

    def test_idempotent_role_creation(self) -> None:
        """Role creation is idempotent (IF NOT EXISTS pattern)."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        # Uses DO $$ block with IF NOT EXISTS check
        assert "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname =" in sql

    def test_default_privileges_for_future_tables(self) -> None:
        """Sets default privileges for tables created later."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        assert "ALTER DEFAULT PRIVILEGES IN SCHEMA public" in sql
        assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO canon_app" in sql


# -----------------------------------------------------------------------------
# generate_table_ownership Tests
# -----------------------------------------------------------------------------


class TestGenerateTableOwnership:
    """Tests for generate_table_ownership."""

    def test_basic_ownership(self) -> None:
        """Generates ALTER TABLE OWNER TO."""
        sql = generate_table_ownership(MockEntity)
        assert 'ALTER TABLE "public"."mock_entities" OWNER TO canon_owner' in sql

    def test_custom_owner_role(self) -> None:
        """Supports custom owner role name."""
        sql = generate_table_ownership(MockEntity, owner_role="custom_owner")
        assert "OWNER TO custom_owner" in sql

    def test_custom_schema(self) -> None:
        """Uses entity's schema in ALTER TABLE."""
        sql = generate_table_ownership(CustomSchemaEntity)
        assert '"canon"."custom_table"' in sql

    def test_proper_quoting(self) -> None:
        """Schema and table are properly quoted."""
        sql = generate_table_ownership(MockEntity)
        assert '"public"' in sql
        assert '"mock_entities"' in sql


# -----------------------------------------------------------------------------
# SQL Syntax Validation Tests
# -----------------------------------------------------------------------------


class TestRolesSQLSyntax:
    """Verify generated SQL is syntactically valid."""

    def test_semicolon_termination(self) -> None:
        """Statements end with semicolons."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        # Should have multiple statement terminators
        assert sql.count(";") > 10  # Many statements

    def test_ownership_semicolon(self) -> None:
        """Ownership statement ends with semicolon."""
        sql = generate_table_ownership(MockEntity)
        assert sql.strip().endswith(";")

    def test_no_sql_keywords_in_identifiers(self) -> None:
        """Generated SQL doesn't have keywords where identifiers expected."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        # Should not have double keywords like "ROLE ROLE" or similar
        assert "ROLE ROLE" not in sql.upper()
        assert "TABLE TABLE" not in sql.upper()

    def test_do_block_syntax(self) -> None:
        """DO $$ blocks are properly terminated."""
        config = RoleConfig()
        sql = generate_database_roles(config)

        # Each DO $$ should have matching END $$
        do_count = sql.count("DO $$")
        end_count = sql.count("END $$")
        assert do_count == end_count
        assert do_count == 4  # One per role
