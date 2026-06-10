"""Tests for OPA Engine Pool and PolicyEngine.

Tests the thread-safe engine pool and policy evaluation facade.
"""

from __future__ import annotations

import pytest

pytest.importorskip("regorus")


import pytest

from canon.enforcement.types import AggregatedResult, EnforcementLevel, PolicyResult
from canon.utils.opa.engine import (
    EnginePool,
    EnginePoolConfig,
    PolicyEngine,
    ResolvedPolicy,
)

# =============================================================================
# EnforcementLevel Tests
# =============================================================================


class TestEnforcementLevel:
    """Tests for EnforcementLevel enum."""

    def test_hard_mandatory_value(self):
        """HARD_MANDATORY should have correct value."""
        assert EnforcementLevel.HARD_MANDATORY.value == "hard_mandatory"

    def test_soft_mandatory_value(self):
        """SOFT_MANDATORY should have correct value."""
        assert EnforcementLevel.SOFT_MANDATORY.value == "soft_mandatory"

    def test_advisory_value(self):
        """ADVISORY should have correct value."""
        assert EnforcementLevel.ADVISORY.value == "advisory"

    def test_hard_mandatory_blocks_via_policy_result(self):
        """HARD_MANDATORY failure should be blocking via PolicyResult."""
        result = PolicyResult(
            policy_id="test",
            allowed=False,
            enforcement=EnforcementLevel.HARD_MANDATORY,
        )
        assert result.is_blocking is True

    def test_soft_mandatory_blocks_via_policy_result(self):
        """SOFT_MANDATORY failure should be blocking via PolicyResult."""
        result = PolicyResult(
            policy_id="test",
            allowed=False,
            enforcement=EnforcementLevel.SOFT_MANDATORY,
        )
        assert result.is_blocking is True

    def test_advisory_does_not_block_via_policy_result(self):
        """ADVISORY failure should not be blocking via PolicyResult."""
        result = PolicyResult(
            policy_id="test",
            allowed=False,
            enforcement=EnforcementLevel.ADVISORY,
        )
        assert result.is_blocking is False


# =============================================================================
# PolicyResult Tests
# =============================================================================


class TestPolicyResult:
    """Tests for PolicyResult dataclass."""

    def test_create_allowed_result(self):
        """Should create allowed result."""
        result = PolicyResult(
            policy_id="test_policy",
            allowed=True,
        )
        assert result.allowed is True
        assert result.policy_id == "test_policy"

    def test_create_denied_result(self):
        """Should create denied result."""
        result = PolicyResult(
            policy_id="test_policy",
            allowed=False,
            violation_code="MISSING_CONSENT",
            violation_message="Consent not obtained",
        )
        assert result.allowed is False
        assert result.violation_code == "MISSING_CONSENT"

    def test_is_blocking_with_hard_mandatory(self):
        """Should be blocking when HARD_MANDATORY fails."""
        result = PolicyResult(
            policy_id="test",
            allowed=False,
            enforcement=EnforcementLevel.HARD_MANDATORY,
        )
        assert result.is_blocking is True

    def test_not_blocking_when_allowed(self):
        """Should not be blocking when allowed."""
        result = PolicyResult(
            policy_id="test",
            allowed=True,
            enforcement=EnforcementLevel.HARD_MANDATORY,
        )
        assert result.is_blocking is False

    def test_soft_mandatory_failure_is_blocking(self):
        """Should be blocking when SOFT_MANDATORY fails."""
        result = PolicyResult(
            policy_id="test",
            allowed=False,
            enforcement=EnforcementLevel.SOFT_MANDATORY,
        )
        # SOFT_MANDATORY failures are blocking (require override)
        assert result.is_blocking is True

    def test_advisory_failure_is_not_blocking(self):
        """Should not be blocking when ADVISORY fails."""
        result = PolicyResult(
            policy_id="test",
            allowed=False,
            enforcement=EnforcementLevel.ADVISORY,
        )
        # ADVISORY failures are not blocking (just warnings)
        assert result.is_blocking is False


# =============================================================================
# AggregatedResult Tests
# =============================================================================


class TestAggregatedResult:
    """Tests for AggregatedResult aggregation logic."""

    def test_all_passed_is_allowed(self):
        """Should allow when all policies pass."""
        results = [
            PolicyResult(policy_id="p1", allowed=True),
            PolicyResult(policy_id="p2", allowed=True),
        ]
        aggregated = AggregatedResult.from_results(results)
        assert aggregated.allowed is True
        assert aggregated.blocking_count == 0
        assert aggregated.advisory_count == 0

    def test_hard_mandatory_failure_blocks(self):
        """Should block when HARD_MANDATORY fails."""
        results = [
            PolicyResult(policy_id="p1", allowed=True),
            PolicyResult(
                policy_id="p2",
                allowed=False,
                enforcement=EnforcementLevel.HARD_MANDATORY,
            ),
        ]
        aggregated = AggregatedResult.from_results(results)
        assert aggregated.allowed is False
        blocking_ids = [r.policy_id for r in aggregated.get_blocking_results()]
        assert "p2" in blocking_ids

    def test_soft_mandatory_failure_blocks(self):
        """Should block when SOFT_MANDATORY fails (blocking_count > 0)."""
        results = [
            PolicyResult(policy_id="p1", allowed=True),
            PolicyResult(
                policy_id="p2",
                allowed=False,
                enforcement=EnforcementLevel.SOFT_MANDATORY,
            ),
        ]
        aggregated = AggregatedResult.from_results(results)
        assert aggregated.allowed is False
        assert aggregated.blocking_count > 0

    def test_advisory_failure_produces_warning(self):
        """Should produce warning when ADVISORY fails."""
        results = [
            PolicyResult(policy_id="p1", allowed=True),
            PolicyResult(
                policy_id="p2",
                allowed=False,
                enforcement=EnforcementLevel.ADVISORY,
                violation_message="Consider adding consent",
            ),
        ]
        aggregated = AggregatedResult.from_results(results)
        assert aggregated.allowed is True  # Not blocked
        advisory_results = aggregated.get_advisory_results()
        assert len(advisory_results) == 1
        assert advisory_results[0].violation_message == "Consider adding consent"

    def test_get_blocking_results(self):
        """Should return blocking results."""
        results = [
            PolicyResult(policy_id="p1", allowed=True),
            PolicyResult(
                policy_id="p2",
                allowed=False,
                enforcement=EnforcementLevel.HARD_MANDATORY,
            ),
        ]
        aggregated = AggregatedResult.from_results(results)
        blocking = aggregated.get_blocking_results()
        assert len(blocking) == 1
        assert blocking[0].policy_id == "p2"


# =============================================================================
# ResolvedPolicy Tests
# =============================================================================


class TestResolvedPolicy:
    """Tests for ResolvedPolicy dataclass."""

    def test_create_minimal(self):
        """Should create with minimal fields."""
        policy = ResolvedPolicy(
            policy_id="nyc_fc_waiting_period",
            rego_package="canon.nyc.fair_chance.waiting_period",
        )
        assert policy.policy_id == "nyc_fc_waiting_period"
        assert policy.enforcement == EnforcementLevel.HARD_MANDATORY  # default

    def test_create_with_legal_citation(self):
        """Should create with legal citation."""
        policy = ResolvedPolicy(
            policy_id="nyc_fc_waiting_period",
            rego_package="canon.nyc.fair_chance.waiting_period",
            legal_citation="NYC Admin Code §8-107(11-a)(2)(c)",
            regulation_url="https://codelibrary.amlegal.com/...",
        )
        assert policy.legal_citation == "NYC Admin Code §8-107(11-a)(2)(c)"

    def test_create_with_parameters(self):
        """Should create with parameters."""
        policy = ResolvedPolicy(
            policy_id="waiting_period",
            rego_package="canon.generic.waiting",
            parameters={"required_days": 5},
        )
        assert policy.parameters["required_days"] == 5


# =============================================================================
# EnginePool Tests
# =============================================================================


class TestEnginePool:
    """Tests for thread-safe EnginePool."""

    def test_create_with_defaults(self):
        """Should create pool with default config."""
        pool = EnginePool()
        assert pool.size == 4
        assert pool.policy_count == 0

    def test_create_with_size(self):
        """Should create pool with custom size."""
        pool = EnginePool(size=8)
        assert pool.size == 8

    def test_create_with_config(self):
        """Should create pool with config object."""
        config = EnginePoolConfig(size=2, checkout_timeout=10.0)
        pool = EnginePool(config=config)
        assert pool.size == 2

    def test_add_policy(self):
        """Should add policy to pool."""
        pool = EnginePool()
        pool.add_policy("test.rego", "package test\ndefault allow := true")
        assert pool.policy_count == 1

    def test_health_check_before_init(self):
        """Should be unhealthy before initialization."""
        pool = EnginePool()
        assert pool.health_check() is False

    def test_health_check_after_init(self):
        """Should be healthy after initialization."""
        pool = EnginePool()
        pool.initialize()
        assert pool.health_check() is True

    def test_checkout_initializes_pool(self):
        """Checkout should auto-initialize pool."""
        pool = EnginePool()
        pool.add_policy("test.rego", "package test\ndefault allow := true")

        with pool.checkout() as engine:
            engine.set_input({"action": "test"})
            result = engine.eval_rule("data.test.allow")
            assert result is True


# =============================================================================
# PolicyEngine Tests
# =============================================================================


class TestPolicyEngine:
    """Tests for PolicyEngine facade."""

    @pytest.fixture
    def pool_with_policy(self) -> EnginePool:
        """Create pool with test policy loaded."""
        pool = EnginePool()
        # Use string value for more predictable Rego behavior
        pool.add_policy(
            "test_allow.rego",
            """
package test.allow_policy

import rego.v1

default allow := false

allow if {
    input.consent_status == "granted"
}

violation := {
    "code": "MISSING_CONSENT",
    "message": "Consent not obtained"
} if {
    not allow
}
""",
        )
        return pool

    @pytest.fixture
    def engine(self, pool_with_policy: EnginePool) -> PolicyEngine:
        """Create engine with test pool."""
        return PolicyEngine(pool_with_policy)

    @pytest.mark.asyncio
    async def test_evaluate_single_allowed(self, engine: PolicyEngine):
        """Should evaluate single policy as allowed."""
        policy = ResolvedPolicy(
            policy_id="consent_check",
            rego_package="test.allow_policy",
        )
        result = await engine.evaluate_single(
            policy,
            {"consent_status": "granted"},
        )
        assert result.allowed is True
        assert result.policy_id == "consent_check"

    @pytest.mark.asyncio
    async def test_evaluate_single_denied(self, engine: PolicyEngine):
        """Should evaluate single policy as denied."""
        policy = ResolvedPolicy(
            policy_id="consent_check",
            rego_package="test.allow_policy",
        )
        result = await engine.evaluate_single(
            policy,
            {"consent_status": "denied"},
        )
        assert result.allowed is False
        assert result.violation_code == "MISSING_CONSENT"

    @pytest.mark.asyncio
    async def test_evaluate_multiple_policies(self, pool_with_policy: EnginePool):
        """Should evaluate multiple policies."""
        # Add second policy
        pool_with_policy.add_policy(
            "test_role.rego",
            """
package test.role_policy

import rego.v1

default allow := false

allow if {
    input.role == "admin"
}
""",
        )

        engine = PolicyEngine(pool_with_policy)

        policies = [
            ResolvedPolicy(
                policy_id="consent_check",
                rego_package="test.allow_policy",
            ),
            ResolvedPolicy(
                policy_id="role_check",
                rego_package="test.role_policy",
            ),
        ]

        result = await engine.evaluate_policies(
            policies,
            {"consent_status": "granted", "role": "admin"},
        )

        assert result.allowed is True
        assert len(result.results) == 2
        assert result.blocking_count == 0

    @pytest.mark.asyncio
    async def test_fail_closed_on_error(self, pool_with_policy: EnginePool):
        """Should deny on evaluation error (fail-closed)."""
        engine = PolicyEngine(pool_with_policy, fail_closed=True)

        policy = ResolvedPolicy(
            policy_id="nonexistent",
            rego_package="nonexistent.package",
        )

        result = await engine.evaluate_single(policy, {"test": True})

        assert result.allowed is False
        assert result.violation_code == "EVALUATION_ERROR"


# =============================================================================
# Integration Tests
# =============================================================================


class TestPolicyEngineIntegration:
    """Integration tests for complete policy evaluation flow."""

    @pytest.mark.asyncio
    async def test_full_evaluation_with_legal_citation(self):
        """Should include legal citation in results."""
        pool = EnginePool()
        pool.add_policy(
            "nyc_waiting.rego",
            """
package canon.nyc.fair_chance.waiting_period

import rego.v1

default allow := false

allow if {
    input.days_since_notice >= 5
}

violation := {
    "code": "WAITING_PERIOD_NOT_ELAPSED",
    "message": "Must wait 5 business days after pre-adverse notice"
} if {
    not allow
}
""",
        )

        engine = PolicyEngine(pool)
        policy = ResolvedPolicy(
            policy_id="nyc_fc_waiting_period",
            rego_package="canon.nyc.fair_chance.waiting_period",
            enforcement=EnforcementLevel.HARD_MANDATORY,
            legal_citation="NYC Admin Code §8-107(11-a)(2)(c)",
        )

        result = await engine.evaluate_single(
            policy,
            {"days_since_notice": 3},
        )

        assert result.allowed is False
        assert result.legal_citation == "NYC Admin Code §8-107(11-a)(2)(c)"
        assert result.violation_code == "WAITING_PERIOD_NOT_ELAPSED"
        assert result.is_blocking is True
