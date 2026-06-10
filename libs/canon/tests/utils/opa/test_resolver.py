"""Tests for PolicyResolver - policy resolution for request contexts.

The PolicyResolver determines which policies apply to a given context using
a 7-stage pipeline:
1. Context Extraction - tenant, jurisdiction, action, subject
2. Charter Lookup - get tenant's governance document
3. Policy Filtering - filter by jurisdiction and action
4. Effective Dating - filter by effective_from/until
5. Precedence Resolution - specific > general, newer > older
6. Dependency Check - prerequisites, mutual exclusions
7. Batch Preparation - ordered list for OPA evaluation

See test_resolver_index.py for PolicyIndex and PolicyIndexEntry tests.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from canon.utils.opa.engine import ResolvedPolicy
from canon.utils.opa.resolver import PolicyIndex, PolicyResolver, ResolutionContext
from kron.utils import now_utc

# =============================================================================
# ResolutionContext Tests
# =============================================================================


class TestResolutionContext:
    """Tests for ResolutionContext dataclass."""

    def test_creates_with_required_fields(self, sample_tenant_id):
        """ResolutionContext should create with minimal required fields."""
        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="adverse_action",
        )

        assert ctx.tenant_id == sample_tenant_id
        assert ctx.action == "adverse_action"

    def test_creates_with_all_fields(self, sample_tenant_id):
        """ResolutionContext should create with all fields."""
        subject_id = uuid4()
        timestamp = now_utc()

        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="adverse_action",
            jurisdictions=("US-NYC", "US-NY", "US"),
            subject_id=subject_id,
            timestamp=timestamp,
            metadata={"key": "value"},
        )

        assert ctx.tenant_id == sample_tenant_id
        assert ctx.action == "adverse_action"
        assert ctx.jurisdictions == ("US-NYC", "US-NY", "US")
        assert ctx.subject_id == subject_id
        assert ctx.timestamp == timestamp
        assert ctx.metadata == {"key": "value"}

    def test_is_frozen(self, sample_tenant_id):
        """ResolutionContext should be immutable."""
        ctx = ResolutionContext(tenant_id=sample_tenant_id, action="test")

        with pytest.raises(AttributeError):
            ctx.action = "modified"

    def test_uses_slots(self, sample_tenant_id):
        """ResolutionContext should use __slots__ for memory efficiency."""
        ctx = ResolutionContext(tenant_id=sample_tenant_id, action="test")

        assert hasattr(ctx, "__slots__") or not hasattr(ctx, "__dict__")


# =============================================================================
# PolicyResolver Tests
# =============================================================================


class TestPolicyResolver:
    """Tests for PolicyResolver.resolve()."""

    def test_resolve_filters_by_jurisdiction(self, sample_tenant_id, sample_index):
        """resolve should filter policies by jurisdiction."""
        resolver = PolicyResolver(sample_index)

        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="adverse_action",
            jurisdictions=("US-NYC",),
        )

        policies = resolver.resolve(ctx)

        # Should get NYC policies, not federal
        policy_ids = [p.policy_id for p in policies]
        assert "nyc_fair_chance_waiting" in policy_ids
        assert "fcra_disclosure" not in policy_ids

    def test_resolve_filters_by_action(self, sample_tenant_id, sample_index):
        """resolve should filter policies by action."""
        resolver = PolicyResolver(sample_index)

        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="use_aedt",
            jurisdictions=("US-NYC",),
        )

        policies = resolver.resolve(ctx)

        policy_ids = [p.policy_id for p in policies]
        assert "nyc_ll144_bias_audit" in policy_ids
        assert "nyc_fair_chance_waiting" not in policy_ids

    def test_resolve_filters_by_effective_date(self, sample_tenant_id, sample_policy_entry):
        """resolve should filter by effective dating."""
        index = PolicyIndex()
        now = now_utc()

        # Active policy
        active = sample_policy_entry(
            policy_id="active_policy",
            jurisdictions=("US-NYC",),
            actions=("test",),
            effective_from=now - timedelta(days=30),
        )

        # Future policy
        future = sample_policy_entry(
            policy_id="future_policy",
            jurisdictions=("US-NYC",),
            actions=("test",),
            effective_from=now + timedelta(days=30),
        )

        # Expired policy
        expired = sample_policy_entry(
            policy_id="expired_policy",
            jurisdictions=("US-NYC",),
            actions=("test",),
            effective_from=now - timedelta(days=60),
            effective_until=now - timedelta(days=30),
        )

        index.add(active)
        index.add(future)
        index.add(expired)

        resolver = PolicyResolver(index)
        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="test",
            jurisdictions=("US-NYC",),
            timestamp=now,
        )

        policies = resolver.resolve(ctx)

        policy_ids = [p.policy_id for p in policies]
        assert "active_policy" in policy_ids
        assert "future_policy" not in policy_ids
        assert "expired_policy" not in policy_ids

    def test_resolve_returns_resolved_policy(self, sample_tenant_id, sample_index):
        """resolve should return ResolvedPolicy objects."""
        resolver = PolicyResolver(sample_index)

        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="adverse_action",
            jurisdictions=("US-NYC",),
        )

        policies = resolver.resolve(ctx)

        assert len(policies) > 0
        assert all(isinstance(p, ResolvedPolicy) for p in policies)

    def test_resolve_empty_when_no_matches(self, sample_tenant_id, sample_index):
        """resolve should return empty list when no policies match."""
        resolver = PolicyResolver(sample_index)

        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="nonexistent_action",
            jurisdictions=("EU-DE",),  # No EU policies
        )

        policies = resolver.resolve(ctx)

        assert policies == []


# =============================================================================
# PolicyResolver with Charter Tests
# =============================================================================


class TestPolicyResolverWithCharter:
    """Tests for PolicyResolver with Charter integration."""

    def test_charter_filters_policies(self, sample_tenant_id, sample_index, sample_charter):
        """Charter should filter to only enabled policies."""
        resolver = PolicyResolver(sample_index, sample_charter)

        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="background_check",
            jurisdictions=("US",),  # Matches FCRA
        )

        policies = resolver.resolve(ctx)

        # FCRA is not in constitution.policy_ids
        policy_ids = [p.policy_id for p in policies]
        assert "fcra_disclosure" not in policy_ids

    def test_charter_allows_enabled_policies(self, sample_tenant_id, sample_index, sample_charter):
        """Charter should allow policies in policy_ids."""
        resolver = PolicyResolver(sample_index, sample_charter)

        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="adverse_action",
            jurisdictions=("US-NYC",),
        )

        policies = resolver.resolve(ctx)

        policy_ids = [p.policy_id for p in policies]
        assert "nyc_fair_chance_waiting" in policy_ids

    def test_no_charter_returns_all_policies(self, sample_tenant_id, sample_index):
        """Without charter, all matching policies should apply."""
        resolver = PolicyResolver(sample_index, charter=None)

        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="background_check",
            jurisdictions=("US",),
        )

        policies = resolver.resolve(ctx)

        policy_ids = [p.policy_id for p in policies]
        assert "fcra_disclosure" in policy_ids


# =============================================================================
# Precedence Resolution Tests
# =============================================================================


class TestPrecedenceResolution:
    """Tests for precedence and dependency resolution."""

    def test_higher_priority_first(self, sample_tenant_id, sample_policy_entry):
        """Higher priority policies should come first."""
        index = PolicyIndex()

        low_priority = sample_policy_entry(
            policy_id="low_priority",
            priority=0,
            jurisdictions=("US-NYC",),
            actions=("test",),
        )
        high_priority = sample_policy_entry(
            policy_id="high_priority",
            priority=10,
            jurisdictions=("US-NYC",),
            actions=("test",),
        )

        index.add(low_priority)
        index.add(high_priority)

        resolver = PolicyResolver(index)
        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="test",
            jurisdictions=("US-NYC",),
        )

        policies = resolver.resolve(ctx)

        assert policies[0].policy_id == "high_priority"
        assert policies[1].policy_id == "low_priority"

    def test_excludes_removes_conflicting(self, sample_tenant_id, sample_policy_entry):
        """Policies with excludes should remove conflicting policies."""
        index = PolicyIndex()

        primary = sample_policy_entry(
            policy_id="primary",
            priority=10,  # Higher priority
            jurisdictions=("US-NYC",),
            actions=("test",),
            excludes=("conflicting",),
        )
        conflicting = sample_policy_entry(
            policy_id="conflicting",
            priority=0,
            jurisdictions=("US-NYC",),
            actions=("test",),
        )

        index.add(primary)
        index.add(conflicting)

        resolver = PolicyResolver(index)
        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="test",
            jurisdictions=("US-NYC",),
        )

        policies = resolver.resolve(ctx)

        policy_ids = [p.policy_id for p in policies]
        assert "primary" in policy_ids
        assert "conflicting" not in policy_ids

    def test_prerequisites_ordered_correctly(self, sample_tenant_id, sample_policy_entry):
        """Policies with prerequisites should come after their dependencies."""
        index = PolicyIndex()

        dependent = sample_policy_entry(
            policy_id="dependent",
            jurisdictions=("US-NYC",),
            actions=("test",),
            prerequisites=("prerequisite",),
        )
        prerequisite = sample_policy_entry(
            policy_id="prerequisite",
            jurisdictions=("US-NYC",),
            actions=("test",),
        )

        index.add(dependent)
        index.add(prerequisite)

        resolver = PolicyResolver(index)
        ctx = ResolutionContext(
            tenant_id=sample_tenant_id,
            action="test",
            jurisdictions=("US-NYC",),
        )

        policies = resolver.resolve(ctx)

        policy_ids = [p.policy_id for p in policies]
        prereq_idx = policy_ids.index("prerequisite")
        dep_idx = policy_ids.index("dependent")
        assert prereq_idx < dep_idx


# =============================================================================
# Module Exports
# =============================================================================


class TestModuleExports:
    """Tests for module exports."""

    def test_exports_from_resolver_module(self):
        """All resolver types should be exported from opa.resolver module."""
        from canon.utils.opa.resolver import (
            PolicyIndex,
            PolicyIndexEntry,
            PolicyResolver,
            ResolutionContext,
        )

        assert PolicyResolver is not None
        assert PolicyIndex is not None
        assert PolicyIndexEntry is not None
        assert ResolutionContext is not None
