"""Tests for Entity creation and instantiation.

Tests cover:
- Entity creation with auto-generated UUID
- Entity creation with explicit UUID
- Optional field handling (None and value cases)

NOTE: This test file covers the kron-based Entity API where entities
use a content= parameter wrapping a ContentModel subclass.
See canon.entities.entity for the implementation.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from .conftest import SampleTenant, SampleTenantContent, SampleUser, SampleUserContent


class TestEntityCreation:
    """Tests for Entity instantiation and defaults."""

    def test_entity_creates_with_auto_id(self):
        """Entity should generate UUID on creation."""
        entity = SampleTenant(content=SampleTenantContent(name="Acme Corp", slug="acme"))
        assert isinstance(entity.id, UUID)
        assert entity.content.name == "Acme Corp"
        assert entity.content.slug == "acme"

    def test_entity_accepts_explicit_id(self):
        """Entity should accept provided UUID."""
        custom_id = uuid4()
        entity = SampleTenant(id=custom_id, content=SampleTenantContent(name="Test", slug="test"))
        assert entity.id == custom_id

    def test_entity_with_optional_field_none(self):
        """Entity should handle None for optional fields."""
        entity = SampleUser(
            content=SampleUserContent(
                email="test@example.com", tenant_id=uuid4(), display_name=None
            )
        )
        assert entity.content.display_name is None

    def test_entity_with_optional_field_value(self):
        """Entity should accept value for optional fields."""
        entity = SampleUser(
            content=SampleUserContent(
                email="test@example.com", tenant_id=uuid4(), display_name="John Doe"
            )
        )
        assert entity.content.display_name == "John Doe"
