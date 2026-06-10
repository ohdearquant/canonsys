"""Shared fixtures for core/ tests.

Provides sample Entity classes plus registry management.

Immutability is handled via register_entity(..., immutable=True).
"""

from __future__ import annotations

from uuid import UUID

import pytest

from canon.entities.entity import (
    ContentModel,
    Entity,
    register_entity,
    reset_entity_registry,
)
from kron.core.node import PERSISTABLE_NODE_REGISTRY

# =============================================================================
# Sample Content Models
# =============================================================================


class SampleTenantContent(ContentModel):
    """Content for sample tenant entity."""

    name: str
    slug: str


class SampleUserContent(ContentModel):
    """Content for sample user entity."""

    email: str
    tenant_id: UUID  # FK reference stored as UUID
    display_name: str | None = None


class SampleProjectContent(ContentModel):
    """Content for sample project entity."""

    name: str
    owner_id: UUID | None = None  # FK reference stored as UUID


class SampleImmutableContent(ContentModel):
    """Content for sample immutable entity."""

    content: str
    category: str


class SampleImmutableWithLinksContent(ContentModel):
    """Content for immutable entity with allowed link fields."""

    content: str
    superseded_by_id: UUID | None = None
    linked_to_id: UUID | None = None


# =============================================================================
# Sample Entity Classes (using register_entity decorator)
# =============================================================================


@register_entity("sample_tenants")
class SampleTenant(Entity):
    """Sample tenant entity for testing."""

    content: SampleTenantContent


@register_entity("sample_users")
class SampleUser(Entity):
    """Sample user entity with FK reference for testing."""

    content: SampleUserContent


@register_entity("sample_projects")
class SampleProject(Entity):
    """Sample project entity for testing."""

    content: SampleProjectContent


# =============================================================================
# Sample Immutable Entity Classes (using register_entity with immutable=True)
# =============================================================================


@register_entity("sample_immutables", immutable=True)
class SampleImmutable(Entity):
    """Sample immutable entity for testing."""

    content: SampleImmutableContent


@register_entity("sample_immutable_links", immutable=True)
class SampleImmutableWithLinks(Entity):
    """Sample immutable entity with link fields for testing."""

    content: SampleImmutableWithLinksContent


# =============================================================================
# Registry Management Fixtures
# =============================================================================


@pytest.fixture
def registry_snapshot():
    """Save and restore entity registry state.

    Use this fixture when a test defines new Entity classes that
    might pollute the registry for other tests.

    Usage:
        def test_something(registry_snapshot):
            class TempEntity(Entity, table="temp_table"):
                name: str
            # Test runs...
            # Registry automatically restored after test
    """
    original = PERSISTABLE_NODE_REGISTRY.copy()
    yield original
    PERSISTABLE_NODE_REGISTRY.clear()
    PERSISTABLE_NODE_REGISTRY.update(original)


@pytest.fixture
def clean_registry():
    """Provide a clean registry for isolated tests.

    Clears registry before test and restores after.

    Usage:
        def test_registry_operations(clean_registry):
            # Registry is empty at start
            assert get_entity_registry() == {}
    """
    original = PERSISTABLE_NODE_REGISTRY.copy()
    reset_entity_registry()
    yield
    PERSISTABLE_NODE_REGISTRY.clear()
    PERSISTABLE_NODE_REGISTRY.update(original)


# =============================================================================
# Entity Instance Fixtures
# =============================================================================


@pytest.fixture
def sample_tenant():
    """Create a sample tenant entity."""
    return SampleTenant(content=SampleTenantContent(name="Acme Corp", slug="acme"))


@pytest.fixture
def sample_user(sample_tenant):
    """Create a sample user entity with FK to tenant."""
    return SampleUser(
        content=SampleUserContent(
            email="user@example.com",
            tenant_id=sample_tenant.id,
            display_name="Test User",
        )
    )


@pytest.fixture
def sample_project(sample_user):
    """Create a sample project entity with optional FK to user."""
    return SampleProject(content=SampleProjectContent(name="Test Project", owner_id=sample_user.id))


@pytest.fixture
def sample_immutable():
    """Create a sample immutable entity."""
    return SampleImmutable(content=SampleImmutableContent(content="Test content", category="test"))


@pytest.fixture
def sample_immutable_with_links():
    """Create a sample immutable entity with link fields."""
    return SampleImmutableWithLinks(
        content=SampleImmutableWithLinksContent(content="Linkable content")
    )
