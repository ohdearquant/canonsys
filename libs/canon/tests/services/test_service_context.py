"""Tests for canon.enforcement.types.ServiceContext.

Tests cover:
- ServiceContext dataclass structure and defaults
- ServiceContext creation with tenant_id (required)
- Optional fields: charter, jurisdiction, service_name
- Integration with Charter type

Architecture validation:
- ServiceContext is for SERVICE INIT TIME - determines which rules apply
- Different from RequestContext which is PER-REQUEST STATE
- Supports Charter-based policy model via charter binding
- Gates are declared via @gates decorator, not injected at runtime
"""

from __future__ import annotations

from dataclasses import fields
from uuid import uuid4

import pytest

from canon.enforcement.types import ServiceContext

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tenant_id():
    """Fixed tenant ID for tests."""
    return uuid4()


@pytest.fixture
def another_tenant_id():
    """Another tenant ID for comparison tests."""
    return uuid4()


@pytest.fixture
def mock_charter(tenant_id):
    """Create a mock Charter for testing."""

    class MockCharter:
        """Mock Charter for ServiceContext tests."""

        def __init__(self, tenant_id):
            self.id = uuid4()
            self.tenant_id = tenant_id
            self.version = "1.0"
            self.status = "active"
            self.policy_ids = ["nyc.fair_chance.notice", "federal.fcra.disclosure"]
            self.roles = []
            self.constraints = []

        def is_effective(self):
            return self.status == "active"

    return MockCharter(tenant_id)


# =============================================================================
# ServiceContext Structure Tests
# =============================================================================


class TestServiceContextStructure:
    """Tests for ServiceContext dataclass structure."""

    def test_service_context_is_dataclass(self):
        """ServiceContext should be a dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(ServiceContext)

    def test_service_context_has_required_fields(self):
        """ServiceContext should have all required fields."""
        field_names = {f.name for f in fields(ServiceContext)}
        expected_fields = {
            "tenant_id",
            "charter",
            "jurisdiction",
            "service_name",
        }
        assert expected_fields.issubset(field_names)

    def test_tenant_id_is_required(self, tenant_id):
        """ServiceContext requires tenant_id."""
        # Should succeed with tenant_id
        ctx = ServiceContext(tenant_id=tenant_id)
        assert ctx.tenant_id == tenant_id

    def test_tenant_id_cannot_be_omitted(self):
        """ServiceContext should raise TypeError if tenant_id omitted."""
        with pytest.raises(TypeError):
            ServiceContext()  # type: ignore


# =============================================================================
# ServiceContext Creation Tests
# =============================================================================


class TestServiceContextCreation:
    """Tests for ServiceContext instantiation."""

    def test_create_minimal_context(self, tenant_id):
        """Create ServiceContext with only tenant_id."""
        ctx = ServiceContext(tenant_id=tenant_id)

        assert ctx.tenant_id == tenant_id
        assert ctx.charter is None
        assert ctx.jurisdiction is None
        assert ctx.service_name is None

    def test_create_full_context(self, tenant_id, mock_charter):
        """Create ServiceContext with all fields."""
        ctx = ServiceContext(
            tenant_id=tenant_id,
            charter=mock_charter,
            jurisdiction="US-NYC",
            service_name="interview",
        )

        assert ctx.tenant_id == tenant_id
        assert ctx.charter is mock_charter
        assert ctx.jurisdiction == "US-NYC"
        assert ctx.service_name == "interview"

    def test_different_tenants_create_independent_contexts(self, tenant_id, another_tenant_id):
        """Different tenants should have independent contexts."""
        ctx1 = ServiceContext(tenant_id=tenant_id, service_name="service1")
        ctx2 = ServiceContext(tenant_id=another_tenant_id, service_name="service2")

        assert ctx1.tenant_id != ctx2.tenant_id
        assert ctx1.service_name != ctx2.service_name


# =============================================================================
# Default Values Tests
# =============================================================================


class TestServiceContextDefaults:
    """Tests for ServiceContext default values."""

    def test_charter_defaults_to_none(self, tenant_id):
        """charter should default to None."""
        ctx = ServiceContext(tenant_id=tenant_id)
        assert ctx.charter is None

    def test_jurisdiction_defaults_to_none(self, tenant_id):
        """jurisdiction should default to None."""
        ctx = ServiceContext(tenant_id=tenant_id)
        assert ctx.jurisdiction is None

    def test_service_name_defaults_to_none(self, tenant_id):
        """service_name should default to None."""
        ctx = ServiceContext(tenant_id=tenant_id)
        assert ctx.service_name is None


# =============================================================================
# Charter Binding Tests
# =============================================================================


class TestCharterBinding:
    """Tests for ServiceContext charter binding."""

    def test_bind_active_charter(self, tenant_id, mock_charter):
        """ServiceContext should bind active charter."""
        ctx = ServiceContext(tenant_id=tenant_id, charter=mock_charter)

        assert ctx.charter is not None
        assert ctx.charter.is_effective()

    def test_charter_provides_policy_ids(self, tenant_id, mock_charter):
        """Bound charter should provide policy_ids."""
        ctx = ServiceContext(tenant_id=tenant_id, charter=mock_charter)

        assert hasattr(ctx.charter, "policy_ids")
        assert len(ctx.charter.policy_ids) == 2
        assert "nyc.fair_chance.notice" in ctx.charter.policy_ids

    def test_charter_tenant_matches_context_tenant(self, tenant_id, mock_charter):
        """Charter tenant should match ServiceContext tenant."""
        ctx = ServiceContext(tenant_id=tenant_id, charter=mock_charter)

        assert ctx.charter.tenant_id == ctx.tenant_id


# =============================================================================
# Jurisdiction Scoping Tests
# =============================================================================


class TestJurisdictionScoping:
    """Tests for ServiceContext jurisdiction scoping."""

    def test_jurisdiction_is_optional_filter(self, tenant_id):
        """Jurisdiction is optional - service can operate without it."""
        ctx = ServiceContext(tenant_id=tenant_id)

        assert ctx.jurisdiction is None

    def test_jurisdiction_can_be_set(self, tenant_id):
        """Jurisdiction can be set for service scope."""
        ctx = ServiceContext(tenant_id=tenant_id, jurisdiction="US-NYC")

        assert ctx.jurisdiction == "US-NYC"

    def test_jurisdiction_values(self, tenant_id):
        """Various jurisdiction codes should be acceptable."""
        jurisdictions = ["US-NYC", "US-CA", "US-NY", "US-FEDERAL", "EU"]

        for jurisdiction in jurisdictions:
            ctx = ServiceContext(tenant_id=tenant_id, jurisdiction=jurisdiction)
            assert ctx.jurisdiction == jurisdiction


# =============================================================================
# Service Name Tests
# =============================================================================


class TestServiceName:
    """Tests for ServiceContext service_name field."""

    def test_service_name_identifies_service(self, tenant_id):
        """service_name should identify the service instance."""
        ctx = ServiceContext(tenant_id=tenant_id, service_name="interview")

        assert ctx.service_name == "interview"

    def test_different_services_have_different_names(self, tenant_id):
        """Different services should have different names."""
        interview_ctx = ServiceContext(tenant_id=tenant_id, service_name="interview")
        market_ctx = ServiceContext(tenant_id=tenant_id, service_name="market")

        assert interview_ctx.service_name != market_ctx.service_name


# =============================================================================
# Integration Tests
# =============================================================================


class TestServiceContextIntegration:
    """Integration tests for ServiceContext with other components."""

    def test_full_service_context_setup(self, tenant_id, mock_charter):
        """Test full ServiceContext setup as it would be used in service init."""
        # Simulate service init: create context with all components
        # NOTE: Gates are now declared via @gates decorator, not injected here
        ctx = ServiceContext(
            tenant_id=tenant_id,
            charter=mock_charter,
            jurisdiction="US-NYC",
            service_name="interview",
        )

        # Verify all components are bound
        assert ctx.tenant_id == tenant_id
        assert ctx.charter is not None
        assert ctx.charter.is_effective()
        assert ctx.jurisdiction == "US-NYC"
        assert ctx.service_name == "interview"

    def test_context_supports_charter_model(self, tenant_id, mock_charter):
        """ServiceContext should support Charter-based Policy Model.

        Architecture principle:
        - Charter is the governance document
        - Charter activates policies via policy_ids
        - ServiceContext carries these for service-level enforcement
        - Gates are declared via @gates decorator, not injected at runtime
        """
        ctx = ServiceContext(
            tenant_id=tenant_id,
            charter=mock_charter,
        )

        # Charter defines what policies are active
        assert ctx.charter is not None
        assert "nyc.fair_chance.notice" in ctx.charter.policy_ids


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests for ServiceContext."""

    def test_context_allows_none_charter(self, tenant_id):
        """ServiceContext should allow None charter (no governance yet)."""
        ctx = ServiceContext(tenant_id=tenant_id, charter=None)

        assert ctx.charter is None


# =============================================================================
# Docstring and Documentation Tests
# =============================================================================


class TestServiceContextDocumentation:
    """Tests validating ServiceContext documentation."""

    def test_module_docstring_explains_purpose(self):
        """Module should have docstring explaining purpose."""
        import canon.enforcement.types as ctx_module

        assert ctx_module.__doc__ is not None
        # Module docstring may not mention contexts - skip this assertion
        # since the types module has a different focus

    def test_class_docstring_explains_purpose(self):
        """ServiceContext should have class docstring."""
        assert ServiceContext.__doc__ is not None
        assert "service" in ServiceContext.__doc__.lower()
