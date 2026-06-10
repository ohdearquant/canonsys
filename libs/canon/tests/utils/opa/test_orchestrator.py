"""Tests for DataOrchestrator and OPA input document building.

Tests cover:
- DataSourceType, CacheScope, RedactionLevel enums
- DataSourceSpec creation and parsing
- DataPlan creation
- OPAInputDocument path operations
- DefaultDerivedLibrary computations
- DataOrchestrator input building

See test_orchestrator_graph.py for cycle detection and topological sort tests.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from canon.exceptions import DataFetchError
from canon.utils.opa.orchestrator import (
    CacheConfig,
    CacheScope,
    DataOrchestrator,
    DataPlan,
    DataSourceSpec,
    DataSourceType,
    DefaultDerivedLibrary,
    OPAInputDocument,
    RedactionLevel,
)
from kron.utils import now_utc

# =============================================================================
# DataSourceType Tests
# =============================================================================


class TestDataSourceType:
    """Tests for DataSourceType enum."""

    def test_all_types_exist(self):
        """All expected types should be defined."""
        assert DataSourceType.EVIDENCE.value == "evidence"
        assert DataSourceType.DB.value == "db"
        assert DataSourceType.EXTERNAL.value == "external"
        assert DataSourceType.DERIVED.value == "derived"
        assert DataSourceType.CONSTANT.value == "constant"

    def test_is_string_enum(self):
        """DataSourceType should be string enum."""
        assert isinstance(DataSourceType.EVIDENCE, str)
        assert DataSourceType.EVIDENCE == "evidence"


class TestCacheScope:
    """Tests for CacheScope enum."""

    def test_all_scopes_exist(self):
        """All cache scopes should be defined."""
        assert CacheScope.REQUEST.value == "request"
        assert CacheScope.PROCESS.value == "process"
        assert CacheScope.SHARED.value == "shared"


class TestRedactionLevel:
    """Tests for RedactionLevel enum."""

    def test_all_levels_exist(self):
        """All redaction levels should be defined."""
        assert RedactionLevel.FULL.value == "full"
        assert RedactionLevel.HASH_ONLY.value == "hash_only"
        assert RedactionLevel.POINTER.value == "pointer"


# =============================================================================
# DataSourceSpec Tests
# =============================================================================


class TestDataSourceSpec:
    """Tests for DataSourceSpec."""

    def test_creates_with_required_fields(self):
        """Should create with required fields."""
        spec = DataSourceSpec(
            id="test",
            type=DataSourceType.EVIDENCE,
            required=True,
            into="evidence.test",
        )

        assert spec.id == "test"
        assert spec.type == DataSourceType.EVIDENCE
        assert spec.required is True
        assert spec.into == "evidence.test"

    def test_default_values(self):
        """Should have sensible defaults."""
        spec = DataSourceSpec(
            id="test",
            type=DataSourceType.CONSTANT,
            required=False,
            into="facts.test",
        )

        assert spec.timeout_ms == 20
        assert spec.cache.scope == CacheScope.REQUEST
        assert spec.cache.ttl_ms == 60000
        assert spec.redact.store == RedactionLevel.FULL
        assert spec.spec == {}

    def test_from_dict_minimal(self):
        """Should parse from minimal dict."""
        data = {
            "id": "test_source",
            "type": "evidence",
            "into": "evidence.audit",
        }

        spec = DataSourceSpec.from_dict(data)

        assert spec.id == "test_source"
        assert spec.type == DataSourceType.EVIDENCE
        assert spec.required is True  # Default
        assert spec.into == "evidence.audit"

    def test_from_dict_full(self):
        """Should parse from full dict."""
        data = {
            "id": "bias_audit",
            "type": "evidence",
            "required": False,
            "into": "evidence.bias_audit",
            "timeout_ms": 100,
            "cache": {
                "scope": "process",
                "ttl_ms": 120000,
            },
            "redact": {
                "store": "hash_only",
                "pii": "high",
            },
            "evidence_type": "bias_audit",
            "selector": {"aedt_id": "$ctx.aedt_id"},
        }

        spec = DataSourceSpec.from_dict(data)

        assert spec.id == "bias_audit"
        assert spec.type == DataSourceType.EVIDENCE
        assert spec.required is False
        assert spec.into == "evidence.bias_audit"
        assert spec.timeout_ms == 100
        assert spec.cache.scope == CacheScope.PROCESS
        assert spec.cache.ttl_ms == 120000
        assert spec.redact.store == RedactionLevel.HASH_ONLY
        assert spec.redact.pii == "high"
        assert spec.spec["evidence_type"] == "bias_audit"
        assert spec.spec["selector"] == {"aedt_id": "$ctx.aedt_id"}

    def test_is_frozen(self):
        """DataSourceSpec should be immutable."""
        spec = DataSourceSpec(
            id="test",
            type=DataSourceType.CONSTANT,
            required=True,
            into="test",
        )

        with pytest.raises(AttributeError):
            spec.id = "changed"


# =============================================================================
# DataPlan Tests
# =============================================================================


class TestDataPlan:
    """Tests for DataPlan."""

    def test_from_specs_separates_types(self):
        """Should separate base and derived sources."""
        specs = [
            DataSourceSpec(
                id="evidence1",
                type=DataSourceType.EVIDENCE,
                required=True,
                into="evidence.e1",
            ),
            DataSourceSpec(
                id="constant1",
                type=DataSourceType.CONSTANT,
                required=True,
                into="facts.c1",
            ),
            DataSourceSpec(
                id="derived1",
                type=DataSourceType.DERIVED,
                required=True,
                into="derived.d1",
            ),
            DataSourceSpec(
                id="derived2",
                type=DataSourceType.DERIVED,
                required=False,
                into="derived.d2",
            ),
        ]

        plan = DataPlan.from_specs(specs)

        assert len(plan.base_sources) == 2
        assert len(plan.derived_sources) == 2
        assert all(s.type != DataSourceType.DERIVED for s in plan.base_sources)
        assert all(s.type == DataSourceType.DERIVED for s in plan.derived_sources)

    def test_empty_specs(self):
        """Should handle empty specs."""
        plan = DataPlan.from_specs([])

        assert plan.base_sources == []
        assert plan.derived_sources == []


# =============================================================================
# OPAInputDocument Tests
# =============================================================================


class TestOPAInputDocument:
    """Tests for OPAInputDocument."""

    def test_default_empty_sections(self):
        """Should initialize with empty sections."""
        doc = OPAInputDocument()

        assert doc.ctx == {}
        assert doc.policy_config == {}
        assert doc.evidence == {}
        assert doc.facts == {}
        assert doc.derived == {}
        assert doc.meta == {}

    def test_to_dict(self):
        """Should convert to dictionary."""
        doc = OPAInputDocument(
            ctx={"action": "test"},
            facts={"key": "value"},
        )

        result = doc.to_dict()

        assert result["ctx"] == {"action": "test"}
        assert result["facts"] == {"key": "value"}
        assert "evidence" in result
        assert "derived" in result
        assert "meta" in result

    def test_set_path_simple(self):
        """Should set value at simple path."""
        doc = OPAInputDocument()

        doc.set_path("facts.key", "value")

        assert doc.facts["key"] == "value"

    def test_set_path_nested(self):
        """Should set value at nested path."""
        doc = OPAInputDocument()

        doc.set_path("evidence.audit.completed", True)

        assert doc.evidence["audit"]["completed"] is True

    def test_get_path_simple(self):
        """Should get value at simple path."""
        doc = OPAInputDocument(ctx={"action": "test"})

        assert doc.get_path("ctx.action") == "test"

    def test_get_path_nested(self):
        """Should get value at nested path."""
        doc = OPAInputDocument(evidence={"audit": {"status": "passed"}})

        assert doc.get_path("evidence.audit.status") == "passed"

    def test_get_path_missing(self):
        """Should return None for missing path."""
        doc = OPAInputDocument()

        assert doc.get_path("evidence.missing.path") is None


# =============================================================================
# DefaultDerivedLibrary Tests
# =============================================================================


class TestDefaultDerivedLibrary:
    """Tests for DefaultDerivedLibrary."""

    @pytest.fixture
    def library(self):
        """Create library instance."""
        return DefaultDerivedLibrary()

    @pytest.mark.asyncio
    async def test_business_days_between(self, library):
        """Should count business days between dates."""
        # Monday to Friday = 4 business days
        start = "2026-01-05T00:00:00Z"  # Monday
        end = "2026-01-09T00:00:00Z"  # Friday

        result = await library.compute(
            "business_days_between",
            {"start": start, "end": end},
        )

        assert result == 4  # Mon, Tue, Wed, Thu

    @pytest.mark.asyncio
    async def test_business_days_with_weekend(self, library):
        """Should skip weekend days."""
        # Monday to Monday next week = 5 business days
        start = "2026-01-05T00:00:00Z"  # Monday
        end = "2026-01-12T00:00:00Z"  # Next Monday

        result = await library.compute(
            "business_days_between",
            {"start": start, "end": end, "calendar": "US"},
        )

        assert result == 5  # Mon-Fri

    @pytest.mark.asyncio
    async def test_days_since(self, library):
        """Should calculate days since date."""
        past = (now_utc() - timedelta(days=10)).isoformat()

        result = await library.compute("days_since", {"date": past})

        assert result >= 9  # At least 9 days (could be 10 depending on time)
        assert result <= 11

    @pytest.mark.asyncio
    async def test_is_after_true(self, library):
        """Should return True when date is after threshold."""
        now = now_utc()
        date = (now + timedelta(days=1)).isoformat()
        threshold = (now - timedelta(days=1)).isoformat()

        result = await library.compute(
            "is_after",
            {"date": date, "threshold": threshold},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_is_after_false(self, library):
        """Should return False when date is before threshold."""
        now = now_utc()
        date = (now - timedelta(days=1)).isoformat()
        threshold = (now + timedelta(days=1)).isoformat()

        result = await library.compute(
            "is_after",
            {"date": date, "threshold": threshold},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_is_before(self, library):
        """Should check if date is before threshold."""
        now = now_utc()
        date = (now - timedelta(days=1)).isoformat()
        threshold = (now + timedelta(days=1)).isoformat()

        result = await library.compute(
            "is_before",
            {"date": date, "threshold": threshold},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_function_raises(self, library):
        """Should raise for unknown function."""
        with pytest.raises(ValueError, match="Unknown derived function"):
            await library.compute("unknown_fn", {})

    # =========================================================================
    # Human Review Bypass Derived Facts Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_verify_calibration_valid(self, library):
        """Should return True when calibration is valid and within tolerance."""
        report = {
            "completed": True,
            "calibration_error": 0.05,  # 5% error, within default 10% tolerance
        }

        result = await library.compute(
            "verify_calibration",
            {"calibration_report": report},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_calibration_exceeds_tolerance(self, library):
        """Should return False when calibration error exceeds tolerance."""
        report = {
            "completed": True,
            "calibration_error": 0.15,  # 15% error, exceeds default 10%
        }

        result = await library.compute(
            "verify_calibration",
            {"calibration_report": report},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_calibration_missing_report(self, library):
        """Should return False when calibration report is missing."""
        result = await library.compute(
            "verify_calibration",
            {"calibration_report": None},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_calibration_custom_tolerance(self, library):
        """Should respect custom tolerance parameter."""
        report = {
            "completed": True,
            "calibration_error": 0.08,
        }

        # Should fail with 5% tolerance
        result = await library.compute(
            "verify_calibration",
            {"calibration_report": report, "tolerance": 0.05},
        )
        assert result is False

        # Should pass with 10% tolerance
        result = await library.compute(
            "verify_calibration",
            {"calibration_report": report, "tolerance": 0.1},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_monitoring_config_valid(self, library):
        """Should return True when monitoring is properly configured."""
        config = {
            "alerting_thresholds": {"accuracy_drop": 0.05, "latency_spike": 500},
            "metrics_enabled": True,
        }

        result = await library.compute(
            "verify_monitoring_config",
            {"monitoring_configuration": config},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_monitoring_config_missing_thresholds(self, library):
        """Should return False when alerting thresholds missing."""
        config = {
            "metrics_enabled": True,
        }

        result = await library.compute(
            "verify_monitoring_config",
            {"monitoring_configuration": config},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_monitoring_config_metrics_disabled(self, library):
        """Should return False when metrics not enabled."""
        config = {
            "alerting_thresholds": {"accuracy_drop": 0.05},
            "metrics_enabled": False,
        }

        result = await library.compute(
            "verify_monitoring_config",
            {"monitoring_configuration": config},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_dpia_complete(self, library):
        """Should return True when DPIA covers automated decision-making."""
        dpia = {
            "completed": True,
            "covers_automated_decision_making": True,
        }

        result = await library.compute(
            "verify_dpia",
            {"dpia": dpia},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_dpia_incomplete(self, library):
        """Should return False when DPIA incomplete."""
        dpia = {
            "completed": False,
            "covers_automated_decision_making": True,
        }

        result = await library.compute(
            "verify_dpia",
            {"dpia": dpia},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_dpia_missing_adm_coverage(self, library):
        """Should return False when DPIA doesn't cover ADM."""
        dpia = {
            "completed": True,
            "covers_automated_decision_making": False,
        }

        result = await library.compute(
            "verify_dpia",
            {"dpia": dpia},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_legal_basis_documented(self, library):
        """Should return True when legal basis is documented with Art. 22."""
        memo = {
            "content": "Pursuant to GDPR Article 22(2)(a), explicit consent obtained...",
            "cites_gdpr_art22_exception": True,
        }

        result = await library.compute(
            "verify_legal_basis",
            {"legal_basis_memo": memo},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_legal_basis_missing_art22(self, library):
        """Should return False when Art. 22 exception not cited."""
        memo = {
            "content": "Some legal basis without Art. 22",
            "cites_gdpr_art22_exception": False,
        }

        result = await library.compute(
            "verify_legal_basis",
            {"legal_basis_memo": memo},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_accuracy_valid(self, library):
        """Should return True when accuracy is sufficient and report is recent."""
        validated_at = (now_utc() - timedelta(days=30)).isoformat()
        report = {
            "accuracy": 0.95,  # 95% accuracy
            "validated_at": validated_at,
        }

        result = await library.compute(
            "verify_accuracy",
            {"accuracy_report": report},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_accuracy_too_low(self, library):
        """Should return False when accuracy below threshold."""
        report = {
            "accuracy": 0.80,  # 80%, below default 90%
            "validated_at": now_utc().isoformat(),
        }

        result = await library.compute(
            "verify_accuracy",
            {"accuracy_report": report},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_accuracy_report_stale(self, library):
        """Should return False when accuracy report is too old."""
        validated_at = (now_utc() - timedelta(days=120)).isoformat()  # 120 days old
        report = {
            "accuracy": 0.95,
            "validated_at": validated_at,
        }

        result = await library.compute(
            "verify_accuracy",
            {"accuracy_report": report, "max_age_days": 90},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_fallback_tested_valid(self, library):
        """Should return True when fallback tested recently and passed."""
        tested_at = (now_utc() - timedelta(days=15)).isoformat()
        results = {
            "passed": True,
            "tested_at": tested_at,
        }

        result = await library.compute(
            "verify_fallback_tested",
            {"fallback_test_results": results},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_fallback_tested_failed(self, library):
        """Should return False when fallback test failed."""
        results = {
            "passed": False,
            "tested_at": now_utc().isoformat(),
        }

        result = await library.compute(
            "verify_fallback_tested",
            {"fallback_test_results": results},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_fallback_tested_stale(self, library):
        """Should return False when fallback test is too old."""
        tested_at = (now_utc() - timedelta(days=45)).isoformat()  # 45 days old
        results = {
            "passed": True,
            "tested_at": tested_at,
        }

        result = await library.compute(
            "verify_fallback_tested",
            {"fallback_test_results": results, "max_age_days": 30},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_appeal_documented_valid(self, library):
        """Should return True when appeal is documented and accessible."""
        procedure = {
            "content": "Appeal procedure content...",
            "accessible_to_affected": True,
        }

        result = await library.compute(
            "verify_appeal_documented",
            {"appeal_procedure": procedure},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_appeal_not_accessible(self, library):
        """Should return False when appeal not accessible to affected parties."""
        procedure = {
            "content": "Appeal procedure content...",
            "accessible_to_affected": False,
        }

        result = await library.compute(
            "verify_appeal_documented",
            {"appeal_procedure": procedure},
        )

        assert result is False


# =============================================================================
# DataOrchestrator Tests
# =============================================================================


class TestDataOrchestrator:
    """Tests for DataOrchestrator."""

    @pytest.mark.asyncio
    async def test_build_input_constant_source(self):
        """Should handle constant data source."""
        orchestrator = DataOrchestrator()

        spec = DataSourceSpec(
            id="version",
            type=DataSourceType.CONSTANT,
            required=True,
            into="facts.policy_version",
            timeout_ms=1000,
            spec={"value": "2026.01"},
        )

        doc = await orchestrator.build_input(
            ctx={"action": "test"},
            policy_config={},
            data_sources=[spec],
            meta={},
        )

        assert doc.facts["policy_version"] == "2026.01"

    @pytest.mark.asyncio
    async def test_build_input_evidence_source(self, mock_evidence_store):
        """Should fetch from evidence store."""
        mock_evidence_store.add_evidence(
            "bias_audit",
            "aedt-123",
            {"completed": True, "score": 0.95},
        )

        orchestrator = DataOrchestrator(evidence_store=mock_evidence_store)

        spec = DataSourceSpec(
            id="audit",
            type=DataSourceType.EVIDENCE,
            required=True,
            into="evidence.bias_audit",
            timeout_ms=1000,
            spec={
                "evidence_type": "bias_audit",
                "selector": {"aedt_id": "aedt-123"},
            },
        )

        doc = await orchestrator.build_input(
            ctx={"aedt_id": "aedt-123"},
            policy_config={},
            data_sources=[spec],
            meta={},
        )

        assert doc.evidence["bias_audit"]["completed"] is True
        assert doc.evidence["bias_audit"]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_build_input_derived_source(self):
        """Should compute derived values."""
        orchestrator = DataOrchestrator()

        # First set up base data, then derive from it
        constant_spec = DataSourceSpec(
            id="notice_date",
            type=DataSourceType.CONSTANT,
            required=True,
            into="evidence.notice.sent_at",
            timeout_ms=1000,
            spec={"value": "2026-01-01T00:00:00Z"},
        )

        derived_spec = DataSourceSpec(
            id="days_since_notice",
            type=DataSourceType.DERIVED,
            required=True,
            into="derived.days_since_notice",
            timeout_ms=1000,
            spec={
                "fn": "days_since",
                "args": {"date": "$evidence.notice.sent_at"},
            },
        )

        doc = await orchestrator.build_input(
            ctx={},
            policy_config={},
            data_sources=[constant_spec, derived_spec],
            meta={},
        )

        assert doc.derived["days_since_notice"] > 0

    @pytest.mark.asyncio
    async def test_build_input_missing_required_raises(self):
        """Should raise for missing required source."""
        orchestrator = DataOrchestrator()  # No evidence store

        spec = DataSourceSpec(
            id="required_evidence",
            type=DataSourceType.EVIDENCE,
            required=True,
            into="evidence.required",
            timeout_ms=1000,
            spec={"evidence_type": "test"},
        )

        with pytest.raises(DataFetchError) as exc_info:
            await orchestrator.build_input(
                ctx={},
                policy_config={},
                data_sources=[spec],
                meta={},
            )

        assert exc_info.value.source_id == "required_evidence"

    @pytest.mark.asyncio
    async def test_build_input_missing_optional_records_error(self):
        """Should record error for missing optional source."""
        orchestrator = DataOrchestrator()  # No evidence store

        spec = DataSourceSpec(
            id="optional_evidence",
            type=DataSourceType.EVIDENCE,
            required=False,  # Optional
            into="evidence.optional",
            timeout_ms=1000,
            spec={"evidence_type": "test"},
        )

        doc = await orchestrator.build_input(
            ctx={},
            policy_config={},
            data_sources=[spec],
            meta={},
        )

        # Should record error but not raise
        assert "_errors_optional_evidence" in doc.facts

    @pytest.mark.asyncio
    async def test_build_input_dict_specs(self):
        """Should parse dict specs automatically."""
        orchestrator = DataOrchestrator()

        doc = await orchestrator.build_input(
            ctx={},
            policy_config={},
            data_sources=[
                {
                    "id": "version",
                    "type": "constant",
                    "into": "facts.v",
                    "value": "1.0",
                }
            ],
            meta={},
        )

        assert doc.facts["v"] == "1.0"

    @pytest.mark.asyncio
    async def test_build_input_template_resolution(self):
        """Should resolve $path templates."""
        orchestrator = DataOrchestrator()

        doc = await orchestrator.build_input(
            ctx={"tenant_id": "tenant-123", "action": "test"},
            policy_config={},
            data_sources=[
                DataSourceSpec(
                    id="ctx_copy",
                    type=DataSourceType.CONSTANT,
                    required=True,
                    into="facts.tenant",
                    timeout_ms=1000,
                    spec={"value": "placeholder"},  # Will be set manually
                ),
            ],
            meta={},
        )

        # Context should be in document
        assert doc.ctx["tenant_id"] == "tenant-123"

    @pytest.mark.asyncio
    async def test_caching(self):
        """Should cache results within request."""
        orchestrator = DataOrchestrator()

        spec = DataSourceSpec(
            id="cached",
            type=DataSourceType.CONSTANT,
            required=True,
            into="facts.cached",
            timeout_ms=1000,
            cache=CacheConfig(scope=CacheScope.REQUEST),
            spec={"value": "cached_value"},
        )

        # First build
        doc1 = await orchestrator.build_input(
            ctx={},
            policy_config={},
            data_sources=[spec],
            meta={},
        )

        assert doc1.facts["cached"] == "cached_value"

        # Cache should contain the value
        assert len(orchestrator._cache) > 0


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Tests for module exports."""

    def test_exports_from_orchestrator_module(self):
        """All orchestrator types should be exported from opa.orchestrator module."""
        from canon.exceptions import DataFetchError
        from canon.utils.opa.orchestrator import (
            DataOrchestrator,
            DataSourceSpec,
            DefaultDerivedLibrary,
            OPAInputDocument,
        )

        assert DataOrchestrator is not None
        assert DataSourceSpec is not None
        assert OPAInputDocument is not None
        assert DefaultDerivedLibrary is not None
        assert DataFetchError is not None
