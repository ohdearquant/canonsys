"""Tests for PolicyIndex and PolicyIndexEntry.

Tests cover:
- PolicyIndexEntry: Policy metadata, effective dating, jurisdiction matching
- PolicyIndex: Adding, retrieving, and querying policies
- Issue #11: PolicyIndex key fix (policy_id string, not UUID)
- Issue #30: Context-aware specificity sorting

See test_resolver.py for PolicyResolver tests.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from canon.enforcement.types import EnforcementLevel
from canon.utils.opa.engine import ResolvedPolicy
from canon.utils.opa.resolver import (
    PolicyIndex,
    PolicyIndexEntry,
    PolicyResolver,
    ResolutionContext,
)
from kron.utils import now_utc

# =============================================================================
# PolicyIndexEntry Tests
# =============================================================================


class TestPolicyIndexEntry:
    """Tests for PolicyIndexEntry."""

    def test_is_effective_within_range(self, sample_policy_entry):
        """Policy should be effective within its date range."""
        now = now_utc()
        entry = sample_policy_entry(
            effective_from=now - timedelta(days=30),
            effective_until=now + timedelta(days=30),
        )

        assert entry.is_effective(now) is True

    def test_is_effective_before_start(self, sample_policy_entry):
        """Policy should not be effective before effective_from."""
        now = now_utc()
        entry = sample_policy_entry(
            effective_from=now + timedelta(days=1),
        )

        assert entry.is_effective(now) is False

    def test_is_effective_after_end(self, sample_policy_entry):
        """Policy should not be effective after effective_until."""
        now = now_utc()
        entry = sample_policy_entry(
            effective_from=now - timedelta(days=30),
            effective_until=now - timedelta(days=1),
        )

        assert entry.is_effective(now) is False

    def test_is_effective_no_dates(self, sample_policy_entry):
        """Policy with no dates should always be effective."""
        entry = sample_policy_entry(
            effective_from=None,
            effective_until=None,
        )

        assert entry.is_effective(now_utc()) is True

    def test_applies_to_jurisdiction_exact_match(self, sample_policy_entry):
        """Policy should apply with exact jurisdiction match."""
        entry = sample_policy_entry(jurisdictions=("US-NYC", "US-CA"))

        assert entry.applies_to_jurisdiction(["US-NYC"]) is True
        assert entry.applies_to_jurisdiction(["US-CA"]) is True
        assert entry.applies_to_jurisdiction(["US-TX"]) is False

    def test_applies_to_jurisdiction_any_match(self, sample_policy_entry):
        """Policy should apply if any jurisdiction matches."""
        entry = sample_policy_entry(jurisdictions=("US-NYC",))

        assert entry.applies_to_jurisdiction(["US-CA", "US-NYC"]) is True

    def test_applies_to_jurisdiction_empty_allows_all(self, sample_policy_entry):
        """Empty jurisdictions should match any jurisdiction."""
        entry = sample_policy_entry(jurisdictions=())

        assert entry.applies_to_jurisdiction(["US-NYC"]) is True
        assert entry.applies_to_jurisdiction(["EU-DE"]) is True

    def test_applies_to_action_match(self, sample_policy_entry):
        """Policy should apply with matching action."""
        entry = sample_policy_entry(actions=("adverse_action", "terminate"))

        assert entry.applies_to_action("adverse_action") is True
        assert entry.applies_to_action("terminate") is True
        assert entry.applies_to_action("hire") is False

    def test_applies_to_action_empty_allows_all(self, sample_policy_entry):
        """Empty actions should match any action."""
        entry = sample_policy_entry(actions=())

        assert entry.applies_to_action("any_action") is True

    def test_to_resolved_policy(self, sample_policy_entry):
        """to_resolved_policy should create correct ResolvedPolicy."""
        entry = sample_policy_entry(
            policy_id="test_policy",
            rego_package="canon.test.policy",
            enforcement=EnforcementLevel.SOFT_MANDATORY,
            legal_citation="Test Citation",
            parameters={"key": "value"},
        )

        resolved = entry.to_resolved_policy()

        assert isinstance(resolved, ResolvedPolicy)
        assert resolved.policy_id == "test_policy"
        assert resolved.rego_package == "canon.test.policy"
        assert resolved.enforcement == EnforcementLevel.SOFT_MANDATORY
        assert resolved.legal_citation == "Test Citation"
        assert resolved.parameters == {"key": "value"}


# =============================================================================
# PolicyIndex Tests
# =============================================================================


class TestPolicyIndex:
    """Tests for PolicyIndex."""

    def test_add_and_get(self, sample_policy_entry):
        """Should add and retrieve entries by ID."""
        index = PolicyIndex()
        entry = sample_policy_entry(policy_id="test_policy")

        index.add(entry)
        result = index.get("test_policy")

        assert result is entry

    def test_get_nonexistent_returns_none(self):
        """Should return None for nonexistent policy."""
        index = PolicyIndex()

        assert index.get("nonexistent") is None

    def test_all_entries(self, sample_policy_entry):
        """Should return all entries."""
        index = PolicyIndex()
        entry1 = sample_policy_entry(policy_id="policy1")
        entry2 = sample_policy_entry(policy_id="policy2")

        index.add(entry1)
        index.add(entry2)

        entries = index.all_entries()

        assert len(entries) == 2
        assert entry1 in entries
        assert entry2 in entries

    def test_entries_for_jurisdiction(self, sample_policy_entry):
        """Should return entries indexed by jurisdiction."""
        index = PolicyIndex()
        nyc_entry = sample_policy_entry(policy_id="nyc_policy", jurisdictions=("US-NYC",))
        ca_entry = sample_policy_entry(policy_id="ca_policy", jurisdictions=("US-CA",))

        index.add(nyc_entry)
        index.add(ca_entry)

        nyc_policies = index.entries_for_jurisdiction("US-NYC")
        ca_policies = index.entries_for_jurisdiction("US-CA")

        assert len(nyc_policies) == 1
        assert nyc_policies[0] is nyc_entry
        assert len(ca_policies) == 1
        assert ca_policies[0] is ca_entry

    def test_entries_for_action(self, sample_policy_entry):
        """Should return entries indexed by action."""
        index = PolicyIndex()
        adverse_entry = sample_policy_entry(policy_id="adverse_policy", actions=("adverse_action",))
        hire_entry = sample_policy_entry(policy_id="hire_policy", actions=("hire",))

        index.add(adverse_entry)
        index.add(hire_entry)

        adverse_policies = index.entries_for_action("adverse_action")
        hire_policies = index.entries_for_action("hire")

        assert len(adverse_policies) == 1
        assert adverse_policies[0] is adverse_entry
        assert len(hire_policies) == 1
        assert hire_policies[0] is hire_entry


# =============================================================================
# Issue #11: PolicyIndex Key Fix Tests
# =============================================================================


class TestPolicyIndexFromDefinitions:
    """Tests for PolicyIndex.from_definitions using policy_id (string) key.

    Fixes issue #11: PolicyIndex should use policy_id string, not id UUID.
    """

    def test_uses_policy_id_for_lookup(self):
        """PolicyIndex should use policy_id string for adapter lookup."""
        # Create mock PolicyDefinition with both id (UUID) and policy_id (string)
        defn = MagicMock()
        defn.id = uuid4()  # UUID - should NOT be used for lookup
        defn.policy_id = "nyc.fair_chance.waiting_period"  # String - should be used

        # Create adapter keyed by policy_id string (not UUID)
        adapter = MagicMock()
        adapter.rego_package = "canon.nyc.fair_chance"
        adapter.prerequisites = []
        adapter.excludes = []
        adapter.parameters = {}

        adapters = {"nyc.fair_chance.waiting_period": adapter}

        index = PolicyIndex.from_definitions([defn], adapters)

        # Should find the policy because we use policy_id for lookup
        assert index.get("nyc.fair_chance.waiting_period") is not None

    def test_uuid_key_not_found(self):
        """PolicyIndex should not find entry when adapter keyed by UUID."""
        defn = MagicMock()
        defn.id = uuid4()
        defn.policy_id = "test.policy"

        adapter = MagicMock()
        adapter.rego_package = "canon.test"
        adapter.prerequisites = []
        adapter.excludes = []
        adapter.parameters = {}

        # Wrongly keyed by UUID - should not be found
        adapters = {str(defn.id): adapter}

        index = PolicyIndex.from_definitions([defn], adapters)

        # Should NOT find the policy because adapter is keyed by UUID, not policy_id
        assert index.get("test.policy") is None

    def test_policy_id_in_entry(self):
        """Entry policy_id should be the string, not UUID."""
        defn = MagicMock()
        defn.id = uuid4()
        defn.policy_id = "fcra.adverse_action"

        adapter = MagicMock()
        adapter.rego_package = "canon.fcra"
        adapter.prerequisites = []
        adapter.excludes = []
        adapter.parameters = {}

        adapters = {"fcra.adverse_action": adapter}

        index = PolicyIndex.from_definitions([defn], adapters)
        entry = index.get("fcra.adverse_action")

        assert entry is not None
        assert entry.policy_id == "fcra.adverse_action"
        assert entry.policy_id != str(defn.id)


# =============================================================================
# Issue #30: Context-Aware Specificity Sort Tests
# =============================================================================


class TestSpecificitySort:
    """Tests for context-aware specificity sorting in _resolve_precedence.

    Fixes issue #30: Policies should be sorted by match specificity
    against the resolution context, not by naive prefix length.

    Specificity criteria:
    1. Jurisdiction depth: US-NYC > US-NY > US
    2. Action specificity: exact match > wildcard
    3. Recency: newer effective_from > older (tiebreaker)
    """

    @pytest.fixture
    def local_tenant_id(self):
        return uuid4()

    def test_jurisdiction_depth_sorting(self, local_tenant_id):
        """More specific jurisdiction wins: US-NYC > US-NY > US."""
        index = PolicyIndex()

        # Federal policy (least specific)
        index.add(
            PolicyIndexEntry(
                policy_id="federal_policy",
                rego_package="canon.federal",
                jurisdictions=("US",),
                actions=("adverse_action",),
            )
        )

        # State policy (medium specific)
        index.add(
            PolicyIndexEntry(
                policy_id="state_policy",
                rego_package="canon.state",
                jurisdictions=("US-NY",),
                actions=("adverse_action",),
            )
        )

        # City policy (most specific)
        index.add(
            PolicyIndexEntry(
                policy_id="city_policy",
                rego_package="canon.city",
                jurisdictions=("US-NYC",),
                actions=("adverse_action",),
            )
        )

        resolver = PolicyResolver(index)

        # Context in NYC - should get city > state > federal order
        ctx = ResolutionContext(
            tenant_id=local_tenant_id,
            action="adverse_action",
            jurisdictions=("US-NYC", "US-NY", "US"),
        )

        policies = resolver.resolve(ctx)
        policy_ids = [p.policy_id for p in policies]

        # Most specific first
        assert policy_ids.index("city_policy") < policy_ids.index("state_policy")
        assert policy_ids.index("state_policy") < policy_ids.index("federal_policy")

    def test_action_specificity_sorting(self, local_tenant_id):
        """Explicit action match beats wildcard (no actions)."""
        index = PolicyIndex()

        # Wildcard policy (applies to all actions)
        index.add(
            PolicyIndexEntry(
                policy_id="wildcard_policy",
                rego_package="canon.wildcard",
                jurisdictions=("US-NYC",),
                actions=(),  # No actions = applies to all
            )
        )

        # Specific policy (explicit action)
        index.add(
            PolicyIndexEntry(
                policy_id="specific_policy",
                rego_package="canon.specific",
                jurisdictions=("US-NYC",),
                actions=("adverse_action",),  # Explicit action
            )
        )

        resolver = PolicyResolver(index)

        ctx = ResolutionContext(
            tenant_id=local_tenant_id,
            action="adverse_action",
            jurisdictions=("US-NYC",),
        )

        policies = resolver.resolve(ctx)
        policy_ids = [p.policy_id for p in policies]

        # Specific action match comes first
        assert policy_ids.index("specific_policy") < policy_ids.index("wildcard_policy")

    def test_recency_tiebreaker(self, local_tenant_id):
        """When jurisdiction and action match equally, newer wins."""
        now = now_utc()
        older = now - timedelta(days=365)

        index = PolicyIndex()

        # Older policy
        index.add(
            PolicyIndexEntry(
                policy_id="older_policy",
                rego_package="canon.older",
                jurisdictions=("US-NYC",),
                actions=("adverse_action",),
                effective_from=older,
            )
        )

        # Newer policy
        index.add(
            PolicyIndexEntry(
                policy_id="newer_policy",
                rego_package="canon.newer",
                jurisdictions=("US-NYC",),
                actions=("adverse_action",),
                effective_from=now,
            )
        )

        resolver = PolicyResolver(index)

        ctx = ResolutionContext(
            tenant_id=local_tenant_id,
            action="adverse_action",
            jurisdictions=("US-NYC",),
        )

        policies = resolver.resolve(ctx)
        policy_ids = [p.policy_id for p in policies]

        # Newer comes first (higher recency)
        assert policy_ids.index("newer_policy") < policy_ids.index("older_policy")

    def test_priority_beats_specificity(self, local_tenant_id):
        """Explicit priority still beats specificity."""
        index = PolicyIndex()

        # Low priority but high specificity
        index.add(
            PolicyIndexEntry(
                policy_id="specific_low_pri",
                rego_package="canon.specific",
                jurisdictions=("US-NYC",),
                actions=("adverse_action",),
                priority=0,  # Default/low priority
            )
        )

        # High priority but lower specificity
        index.add(
            PolicyIndexEntry(
                policy_id="general_high_pri",
                rego_package="canon.general",
                jurisdictions=("US",),
                actions=("adverse_action",),
                priority=100,  # High priority
            )
        )

        resolver = PolicyResolver(index)

        ctx = ResolutionContext(
            tenant_id=local_tenant_id,
            action="adverse_action",
            jurisdictions=("US-NYC", "US"),
        )

        policies = resolver.resolve(ctx)
        policy_ids = [p.policy_id for p in policies]

        # Higher priority wins despite lower specificity
        assert policy_ids.index("general_high_pri") < policy_ids.index("specific_low_pri")

    def test_no_jurisdiction_is_least_specific(self, local_tenant_id):
        """Policy with no jurisdiction restriction is least specific."""
        index = PolicyIndex()

        # Universal policy (no jurisdiction restriction)
        index.add(
            PolicyIndexEntry(
                policy_id="universal_policy",
                rego_package="canon.universal",
                jurisdictions=(),  # Applies everywhere
                actions=("adverse_action",),
            )
        )

        # Specific policy
        index.add(
            PolicyIndexEntry(
                policy_id="local_policy",
                rego_package="canon.local",
                jurisdictions=("US",),
                actions=("adverse_action",),
            )
        )

        resolver = PolicyResolver(index)

        ctx = ResolutionContext(
            tenant_id=local_tenant_id,
            action="adverse_action",
            jurisdictions=("US",),
        )

        policies = resolver.resolve(ctx)
        policy_ids = [p.policy_id for p in policies]

        # Local (with jurisdiction) comes before universal (no jurisdiction)
        assert policy_ids.index("local_policy") < policy_ids.index("universal_policy")
