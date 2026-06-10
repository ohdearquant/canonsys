"""Tests for OPA client, configuration, and integration.

Tests cover:
- OPAConfig: Configuration dataclass
- OPAClient: Client for embedded/remote OPA evaluation
- get_opa_client(): Global singleton factory
- Integration and edge cases

See test_client_input.py for OPAInput and OPAResult tests.
"""

from __future__ import annotations

import pytest

pytest.importorskip("regorus")


from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from canon.exceptions import DataFetchError
from canon.utils.opa.client import (
    EmbeddedOPAClient,
    OPAClientBase,
    OPAConfig,
    OPAInput,
    OPAResult,
    RemoteOPAClient,
    get_opa_client,
    reset_opa_client,
)
from canon.utils.opa.orchestrator import (
    DataOrchestrator,
    DataSourceSpec,
    DataSourceType,
)
from canon.utils.opa.resolver import (
    PolicyIndex,
    PolicyIndexEntry,
    PolicyResolver,
    ResolutionContext,
)
from kron.utils import now_utc

# =============================================================================
# OPACONFIG TESTS
# =============================================================================


class TestOPAConfigCreation:
    """Tests for OPAConfig dataclass."""

    def test_creates_with_defaults(self):
        """OPAConfig should create with default values."""
        config = OPAConfig()

        assert config.mode == "embedded"
        assert config.bundle_path is None
        assert config.opa_url == "http://localhost:8181"
        assert config.timeout == 5.0
        assert config.fail_closed is True

    def test_creates_with_remote_mode(self):
        """OPAConfig should create with remote mode settings."""
        config = OPAConfig(
            mode="remote",
            opa_url="http://opa:8181",
            timeout=10.0,
        )

        assert config.mode == "remote"
        assert config.opa_url == "http://opa:8181"
        assert config.timeout == 10.0

    def test_is_frozen(self):
        """OPAConfig should be immutable."""
        config = OPAConfig()

        with pytest.raises(FrozenInstanceError):
            config.mode = "remote"


# =============================================================================
# EMBEDDED OPA CLIENT TESTS
# =============================================================================


class TestEmbeddedOPAClientInstantiation:
    """Tests for EmbeddedOPAClient instantiation."""

    def test_creates_with_defaults(self):
        """EmbeddedOPAClient should create with default config."""
        client = EmbeddedOPAClient()

        assert isinstance(client, OPAClientBase)

    def test_creates_with_bundle_path(self):
        """EmbeddedOPAClient should accept bundle path."""
        client = EmbeddedOPAClient(bundle_path="/path/to/bundle")

        assert client is not None


# Simple Rego policy for testing
TEST_REGO_ALLOW = """
package test.allow_policy

import rego.v1

default allow := true
"""

TEST_REGO_DENY = """
package test.deny_policy

import rego.v1

default allow := false

deny_reasons contains "test denial" if {
    true
}
"""


class TestEmbeddedOPAClientEvaluate:
    """Tests for EmbeddedOPAClient.evaluate() method."""

    @pytest.mark.asyncio
    async def test_evaluate_returns_opa_result(self):
        """evaluate() should return OPAResult instance."""
        client = EmbeddedOPAClient()
        client.load_rego("test.allow_policy", TEST_REGO_ALLOW)
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        result = await client.evaluate(
            package="test.allow_policy",
            input=opa_input,
        )

        assert isinstance(result, OPAResult)

    @pytest.mark.asyncio
    async def test_evaluate_populates_package(self):
        """evaluate() should populate package in result."""
        client = EmbeddedOPAClient()
        client.load_rego("test.allow_policy", TEST_REGO_ALLOW)
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        result = await client.evaluate(
            package="test.allow_policy",
            input=opa_input,
        )

        assert result.package == "test.allow_policy"

    @pytest.mark.asyncio
    async def test_evaluate_populates_input_hash(self):
        """evaluate() should compute and populate input_hash."""
        client = EmbeddedOPAClient()
        client.load_rego("test.allow_policy", TEST_REGO_ALLOW)
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        result = await client.evaluate(
            package="test.allow_policy",
            input=opa_input,
        )

        assert result.input_hash is not None
        # Hash should be a valid SHA-256 hex string (64 characters)
        assert len(result.input_hash) == 64
        assert all(c in "0123456789abcdef" for c in result.input_hash)

    @pytest.mark.asyncio
    async def test_evaluate_populates_evaluated_at(self):
        """evaluate() should populate evaluated_at timestamp."""
        client = EmbeddedOPAClient()
        client.load_rego("test.allow_policy", TEST_REGO_ALLOW)
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        before = now_utc()
        result = await client.evaluate(
            package="test.allow_policy",
            input=opa_input,
        )
        after = now_utc()

        assert result.evaluated_at is not None
        assert before <= result.evaluated_at <= after

    @pytest.mark.asyncio
    async def test_evaluate_allow_policy(self):
        """evaluate() should return allow=True for allow policy."""
        client = EmbeddedOPAClient()
        client.load_rego("test.allow_policy", TEST_REGO_ALLOW)
        opa_input = OPAInput(
            action_type="test",
            tenant_id="tenant",
        )

        result = await client.evaluate(
            package="test.allow_policy",
            input=opa_input,
        )

        assert result.allow is True

    @pytest.mark.asyncio
    async def test_evaluate_deny_policy(self):
        """evaluate() should return allow=False for deny policy."""
        client = EmbeddedOPAClient()
        client.load_rego("test.deny_policy", TEST_REGO_DENY)
        opa_input = OPAInput(
            action_type="test",
            tenant_id="tenant",
        )

        result = await client.evaluate(
            package="test.deny_policy",
            input=opa_input,
        )

        assert result.allow is False


class TestOPAClientLoadRego:
    """Tests for OPAClient.load_rego() caching method."""

    def test_load_rego_caches_content(self):
        """load_rego() should cache Rego content by package name."""
        client = EmbeddedOPAClient()
        rego_content = """
        package canon.statutory.test

        default allow = false
        allow { input.consent == true }
        """

        client.load_rego("canon.statutory.test", rego_content)

        # Cache key is {package}.rego for consistency with bundle loading
        assert "canon.statutory.test.rego" in client._rego_cache
        assert client._rego_cache["canon.statutory.test.rego"] == rego_content

    def test_load_rego_overwrites_existing(self):
        """load_rego() should overwrite existing cached content."""
        client = EmbeddedOPAClient()
        package = "test.package"
        cache_key = f"{package}.rego"

        client.load_rego(package, "original content")
        client.load_rego(package, "updated content")

        assert client._rego_cache[cache_key] == "updated content"

    def test_load_rego_multiple_packages(self):
        """load_rego() should cache multiple packages independently."""
        client = EmbeddedOPAClient()

        client.load_rego("package.one", "content one")
        client.load_rego("package.two", "content two")
        client.load_rego("package.three", "content three")

        # Cache keys are {package}.rego for consistency with bundle loading
        assert len(client._rego_cache) == 3
        assert client._rego_cache["package.one.rego"] == "content one"
        assert client._rego_cache["package.two.rego"] == "content two"
        assert client._rego_cache["package.three.rego"] == "content three"


# =============================================================================
# GET_OPA_CLIENT TESTS
# =============================================================================


class TestGetOPAClient:
    """Tests for get_opa_client() global singleton factory."""

    def test_returns_opa_client_base(self):
        """get_opa_client() should return an OPAClientBase instance."""
        # Reset global state
        reset_opa_client()

        client = get_opa_client()

        assert isinstance(client, OPAClientBase)

    def test_returns_same_instance(self):
        """get_opa_client() should return the same instance on repeated calls."""
        # Reset global state
        reset_opa_client()

        client1 = get_opa_client()
        client2 = get_opa_client()

        assert client1 is client2

    def test_creates_embedded_client_by_default(self):
        """get_opa_client() should create an EmbeddedOPAClient by default."""
        # Reset global state
        reset_opa_client()

        client = get_opa_client()

        assert isinstance(client, EmbeddedOPAClient)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestOPAIntegration:
    """Integration tests verifying OPA types work together correctly."""

    @pytest.mark.asyncio
    async def test_full_evaluation_flow(self):
        """Full evaluation flow: OPAInput -> EmbeddedOPAClient.evaluate() -> OPAResult."""
        client = EmbeddedOPAClient()
        # Load a test policy - package name must match what's declared in Rego
        client.load_rego("test.allow_policy", TEST_REGO_ALLOW)

        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="acme-corp",
            jurisdiction="US-NYC",
            subject_id="candidate-123",
            data={
                "position_type": "full_time",
                "consent_obtained": True,
            },
        )

        result = await client.evaluate(
            package="test.allow_policy",
            input=opa_input,
        )

        # Verify full flow
        assert isinstance(result, OPAResult)
        assert result.package == "test.allow_policy"
        assert result.input_hash is not None
        assert result.evaluated_at is not None

    @pytest.mark.asyncio
    async def test_input_hash_is_deterministic(self):
        """Input hash should be deterministic for same input with fixed timestamp."""
        client = EmbeddedOPAClient()
        client.load_rego("test.allow_policy", TEST_REGO_ALLOW)

        # Provide explicit evaluated_at to make to_dict() deterministic
        # Without this, each to_dict() call generates a new timestamp
        opa_input = OPAInput(
            action_type="test_action",
            tenant_id="tenant-abc",
            jurisdiction="US-CA",
            evaluated_at="2024-01-15T10:00:00Z",
        )

        result1 = await client.evaluate(package="test.allow_policy", input=opa_input)
        result2 = await client.evaluate(package="test.allow_policy", input=opa_input)

        assert result1.input_hash == result2.input_hash

    @pytest.mark.asyncio
    async def test_different_inputs_different_hashes(self):
        """Different inputs should produce different hashes."""
        client = EmbeddedOPAClient()
        client.load_rego("test.allow_policy", TEST_REGO_ALLOW)

        input1 = OPAInput(
            action_type="action_a",
            tenant_id="tenant-1",
        )
        input2 = OPAInput(
            action_type="action_b",
            tenant_id="tenant-1",
        )

        result1 = await client.evaluate(package="test.allow_policy", input=input1)
        result2 = await client.evaluate(package="test.allow_policy", input=input2)

        assert result1.input_hash != result2.input_hash


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestOPAEdgeCases:
    """Edge case and boundary condition tests."""

    def test_opainput_empty_strings(self):
        """OPAInput should accept empty strings (validation is business logic)."""
        opa_input = OPAInput(
            action_type="",
            tenant_id="",
        )

        assert opa_input.action_type == ""
        assert opa_input.tenant_id == ""

    def test_opainput_special_characters_in_fields(self):
        """OPAInput should handle special characters in fields."""
        opa_input = OPAInput(
            action_type="us-nyc.fair_chance.adverse_action",
            tenant_id="tenant/with/slashes",
            jurisdiction="US-NYC",
            subject_id="person@domain.com",
        )

        result = opa_input.to_dict()
        assert result["action_type"] == "us-nyc.fair_chance.adverse_action"
        assert result["tenant_id"] == "tenant/with/slashes"

    def test_opainput_nested_data(self):
        """OPAInput should handle deeply nested data dict."""
        nested_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep",
                    }
                }
            }
        }
        opa_input = OPAInput(
            action_type="test",
            tenant_id="tenant",
            data=nested_data,
        )

        result = opa_input.to_dict()
        assert result["level1"]["level2"]["level3"]["value"] == "deep"

    def test_opainput_large_data(self):
        """OPAInput should handle large data dictionaries."""
        large_data = {f"field_{i}": f"value_{i}" for i in range(100)}
        opa_input = OPAInput(
            action_type="test",
            tenant_id="tenant",
            data=large_data,
        )

        result = opa_input.to_dict()
        assert len([k for k in result.keys() if k.startswith("field_")]) == 100

    def test_oparesult_many_deny_reasons(self):
        """OPAResult should handle many deny reasons."""
        reasons = tuple(f"reason_{i}" for i in range(50))
        result = OPAResult(
            allow=False,
            deny_reasons=reasons,
        )

        assert len(result.deny_reasons) == 50

    def test_oparesult_long_deny_reason(self):
        """OPAResult should handle long deny reason strings."""
        long_reason = "A" * 10000
        result = OPAResult(
            allow=False,
            deny_reasons=(long_reason,),
        )

        assert len(result.deny_reasons[0]) == 10000

    def test_opaclient_rego_package_with_dots(self):
        """OPAClient should handle Rego packages with multiple dots."""
        client = EmbeddedOPAClient()
        package = "canon.statutory.us.nyc.fair_chance.ll144"

        client.load_rego(package, "package content")

        # Cache key is {package}.rego for consistency with bundle loading
        assert f"{package}.rego" in client._rego_cache

    @pytest.mark.asyncio
    async def test_evaluate_with_empty_data(self):
        """evaluate() should work with empty data dict."""
        client = EmbeddedOPAClient()
        client.load_rego("test.allow_policy", TEST_REGO_ALLOW)
        opa_input = OPAInput(
            action_type="test",
            tenant_id="tenant",
            data={},
        )

        result = await client.evaluate(package="test.allow_policy", input=opa_input)

        assert isinstance(result, OPAResult)


# =============================================================================
# MODULE EXPORTS TEST
# =============================================================================


class TestModuleExports:
    """Tests for module __all__ exports."""

    def test_all_exports_correct(self):
        """Module should export expected classes in __all__."""
        from canon.utils.opa import client as opa_client

        assert hasattr(opa_client, "__all__")
        assert "OPAInput" in opa_client.__all__
        assert "OPAResult" in opa_client.__all__
        assert "OPAClientBase" in opa_client.__all__
        assert "EmbeddedOPAClient" in opa_client.__all__
        assert "RemoteOPAClient" in opa_client.__all__
        assert "get_opa_client" in opa_client.__all__

    def test_all_exports_importable(self):
        """All exported classes should be importable from module."""
        from canon.utils.opa.client import (
            EmbeddedOPAClient,
            OPAClientBase,
            OPAInput,
            OPAResult,
            get_opa_client,
        )

        assert OPAInput is not None
        assert OPAResult is not None
        assert OPAClientBase is not None
        assert EmbeddedOPAClient is not None
        assert RemoteOPAClient is not None
        assert get_opa_client is not None


# =============================================================================
# Phase 0 OPA Fixes (B2.1, B2.3, B1.1, B1.8)
# =============================================================================


class TestOPAInputReservedKeys:
    """B1.8 fix: Reserved keys must win over data keys."""

    def test_reserved_keys_win_over_data_keys(self):
        """Reserved keys should override any keys in data dict."""
        input = OPAInput(
            action_type="real_action",
            tenant_id="real_tenant",
            jurisdiction="US-NYC",
            data={
                "action_type": "injected_action",  # Attempted override
                "tenant_id": "injected_tenant",  # Attempted override
                "extra_field": "allowed",  # Additional data OK
            },
        )
        result = input.to_dict()

        # Reserved keys must win
        assert result["action_type"] == "real_action"
        assert result["tenant_id"] == "real_tenant"
        assert result["jurisdiction"] == "US-NYC"

        # Additional data should be preserved
        assert result["extra_field"] == "allowed"

    def test_data_keys_preserved_when_no_conflict(self):
        """Data keys should be preserved when they don't conflict."""
        input = OPAInput(
            action_type="test_action",
            tenant_id="test_tenant",
            data={
                "custom_field": "custom_value",
                "nested": {"key": "value"},
            },
        )
        result = input.to_dict()

        assert result["custom_field"] == "custom_value"
        assert result["nested"] == {"key": "value"}


class TestConstitutionDisabledFlag:
    """B2.1 fix: Disabled flag must filter immediately."""

    def test_disabled_entries_filtered_immediately(self):
        """Disabled entries should be filtered out, not just marked."""
        # Create index with one policy
        index = PolicyIndex()
        entry = PolicyIndexEntry(
            policy_id="test_policy",
            rego_package="canon.test",
            jurisdictions=("US",),
            actions=("test_action",),
        )
        index.add(entry)

        # Create a mock Constitution with disabled constraint
        class MockConstitution:
            policy_ids = ["test_policy"]
            constraints = [{"policy_id": "test_policy", "disabled": True}]

            def is_effective(self, at):
                return True

        resolver = PolicyResolver(index, charter=MockConstitution())

        ctx = ResolutionContext(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            action="test_action",
            jurisdictions=("US",),
        )

        result = resolver.resolve(ctx)

        # Disabled policy should be filtered out
        assert len(result) == 0

    def test_enabled_entries_preserved(self):
        """Non-disabled entries should be preserved."""
        index = PolicyIndex()
        entry = PolicyIndexEntry(
            policy_id="test_policy",
            rego_package="canon.test",
            jurisdictions=("US",),
            actions=("test_action",),
        )
        index.add(entry)

        # Constitution without disabled flag
        class MockConstitution:
            policy_ids = ["test_policy"]
            constraints = [{"policy_id": "test_policy", "enforcement": "soft_mandatory"}]

            def is_effective(self, at):
                return True

        resolver = PolicyResolver(index, charter=MockConstitution())

        ctx = ResolutionContext(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            action="test_action",
            jurisdictions=("US",),
        )

        result = resolver.resolve(ctx)

        # Policy should be preserved
        assert len(result) == 1
        assert result[0].policy_id == "test_policy"


class TestRequiredDataSourceNone:
    """B2.3 fix: Required data sources returning None must fail closed."""

    @pytest.mark.asyncio
    async def test_required_source_none_raises_error(self):
        """Required source returning None should raise DataFetchError."""

        # Mock evidence store that returns None
        class NoneEvidenceStore:
            async def get_latest(self, evidence_type, selector, project=None):
                return None  # Simulate missing evidence

        orchestrator = DataOrchestrator(evidence_store=NoneEvidenceStore())

        spec = DataSourceSpec(
            id="required_evidence",
            type=DataSourceType.EVIDENCE,
            required=True,  # This is required
            into="evidence.test",
            spec={"evidence_type": "test_type", "selector": {}},
        )

        with pytest.raises(DataFetchError) as exc_info:
            await orchestrator.build_input(
                ctx={"tenant_id": "test"},
                policy_config={},
                data_sources=[spec],
                meta={},
            )

        assert "returned None" in str(exc_info.value)
        assert "fail-closed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_optional_source_none_allowed(self):
        """Optional source returning None should not raise error."""

        class NoneEvidenceStore:
            async def get_latest(self, evidence_type, selector, project=None):
                return None

        orchestrator = DataOrchestrator(evidence_store=NoneEvidenceStore())

        spec = DataSourceSpec(
            id="optional_evidence",
            type=DataSourceType.EVIDENCE,
            required=False,  # This is optional
            into="evidence.test",
            spec={"evidence_type": "test_type", "selector": {}},
        )

        # Should not raise - optional sources can be None
        doc = await orchestrator.build_input(
            ctx={"tenant_id": "test"},
            policy_config={},
            data_sources=[spec],
            meta={},
        )

        # Value should be set to None in document
        assert doc.get_path("evidence.test") is None

    @pytest.mark.asyncio
    async def test_required_source_with_value_succeeds(self):
        """Required source with actual value should succeed."""

        class ValueEvidenceStore:
            async def get_latest(self, evidence_type, selector, project=None):
                return {"status": "granted"}

        orchestrator = DataOrchestrator(evidence_store=ValueEvidenceStore())

        spec = DataSourceSpec(
            id="required_evidence",
            type=DataSourceType.EVIDENCE,
            required=True,
            into="evidence.test",
            spec={"evidence_type": "test_type", "selector": {}},
        )

        doc = await orchestrator.build_input(
            ctx={"tenant_id": "test"},
            policy_config={},
            data_sources=[spec],
            meta={},
        )

        assert doc.get_path("evidence.test") == {"status": "granted"}
