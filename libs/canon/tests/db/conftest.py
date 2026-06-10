"""Shared fixtures for db tests."""

from __future__ import annotations

from enum import Enum
from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel, Field

from kron.types import FK, Vector


class SampleEnum(Enum):
    """Sample enum for testing SQL type mapping."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class SampleNestedModel(BaseModel):
    """Nested Pydantic model for JSONB testing."""

    name: str
    value: int


class MockTenant(BaseModel):
    """Mock tenant model for FK testing."""

    _table_name: ClassVar[str] = "mock_tenants"
    _schema: ClassVar[str] = "public"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str


class MockUser(BaseModel):
    """Mock user model with FK reference for testing."""

    _table_name: ClassVar[str] = "mock_users"
    _schema: ClassVar[str] = "public"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str
    tenant_id: FK[MockTenant]
    display_name: str | None = None


class MockProject(BaseModel):
    """Mock project with vector embedding and optional FK for testing."""

    _table_name: ClassVar[str] = "mock_projects"
    _schema: ClassVar[str] = "public"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str | None = None
    owner_id: FK[MockUser] | None = None
    embedding: Vector[1536] | None = None


class MockSelfRef(BaseModel):
    """Model with self-referential FK for testing dependency sorting."""

    _table_name: ClassVar[str] = "mock_self_refs"
    _schema: ClassVar[str] = "public"
    _primary_key: ClassVar[str] = "id"
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    parent_id: FK["MockSelfRef"] | None = None
