"""Integration tests for CharterExecutor: compile → execute end-to-end."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from canon.dsl.catalog import SchemaCatalog
from canon.dsl.compiler import compile_charter
from canon.hub.executor import (
    CharterExecutor,
    PhaseGateError,
    PhaseResult,
    PhraseResolver,
    WorkflowResult,
)

# ---------------------------------------------------------------------------
# Mock types for schema catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EligibilityReport:
    eligible: bool = True


@dataclass(frozen=True)
class PIPReport:
    recommendation: str = ""


@dataclass(frozen=True)
class TerminationCertificate:
    certificate_id: str = ""


# ---------------------------------------------------------------------------
# Mock registries (same pattern as DSL tests)
# ---------------------------------------------------------------------------


class _MockFeatureRegistry:
    def __init__(self, known: set[str]) -> None:
        self._known = known

    def get_feature(self, name: str) -> object | None:
        return object() if name in self._known else None


class _MockPolicyRegistry:
    def __init__(self, known: set[str]) -> None:
        self._known = known

    def has_policy(self, policy_id: str) -> bool:
        return policy_id in self._known


class _MockPackageRegistry:
    def has_package(self, name: str) -> bool:
        return True


# ---------------------------------------------------------------------------
# Mock phrase callables
# ---------------------------------------------------------------------------

_execution_log: list[str] = []


async def mock_verify_consent(args, ctx):
    _execution_log.append("verify_consent")
    return {"verified": True, "scope": args.get("_pos_0", "default")}


async def mock_assess_eligibility(args, ctx):
    _execution_log.append("assess_eligibility")
    return {"eligible": True, "subject_id": str(uuid4())}


async def mock_evaluate_performance(args, ctx):
    _execution_log.append("evaluate_performance")
    return {"score": 3.2, "meets_threshold": True}


async def mock_conduct_review(args, ctx):
    _execution_log.append("conduct_review")
    return {"recommendation": "continue_pip", "reviewer_id": str(uuid4())}


async def mock_certify_termination(args, ctx):
    _execution_log.append("certify_termination")
    return {"certificate_id": str(uuid4()), "immutable": True}


async def mock_verify_consent_fail(args, ctx):
    _execution_log.append("verify_consent_FAIL")
    raise PhaseGateError("eligibility", "verify_consent", "consent not granted")


MOCK_PHRASES = {
    "verify_consent": mock_verify_consent,
    "assess_eligibility": mock_assess_eligibility,
    "evaluate_performance": mock_evaluate_performance,
    "conduct_review": mock_conduct_review,
    "certify_termination": mock_certify_termination,
}

ALL_FEATURE_NAMES = set(MOCK_PHRASES) | {
    "check_employment_status",
    "generate_pip_report",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PIP_CHARTER_SOURCE = """\
charter "Performance Improvement Plan" v1.0

schemas: canon.hr@2026.01

policies:
    - employment.pip
    - employment.termination

workflow pip_workflow:
    phase eligibility:
        require verify_consent("background_check")
        action assess_eligibility()
        output EligibilityReport

    phase review:
        require eligibility.passed
        action evaluate_performance()
        action conduct_review()
        output PIPReport

    phase decision:
        require review.passed
        action certify_termination()
        output TerminationCertificate
        certify immutable
        evidence termination_record

situations:
    when jurisdiction == "NYC":
        waiting_period 30..90 days
        require verify_consent("aedt_disclosure")

roles:
    hr_manager:
        actions: [assess_eligibility, evaluate_performance, conduct_review]
        break_glass: false
        requires_mfa: true
    legal_counsel:
        actions: [certify_termination]
        break_glass: true
        requires_mfa: true
"""


@pytest.fixture()
def mock_catalog() -> SchemaCatalog:
    catalog = SchemaCatalog()
    catalog.register("canon.hr", "2026.01", "EligibilityReport", EligibilityReport)
    catalog.register("canon.hr", "2026.01", "PIPReport", PIPReport)
    catalog.register("canon.hr", "2026.01", "TerminationCertificate", TerminationCertificate)
    return catalog


@pytest.fixture()
def compiled_pip(mock_catalog):
    return compile_charter(
        PIP_CHARTER_SOURCE,
        catalog=mock_catalog,
        feature_registry=_MockFeatureRegistry(ALL_FEATURE_NAMES),
        policy_registry=_MockPolicyRegistry({"employment.pip", "employment.termination"}),
        package_registry=_MockPackageRegistry(),
    )


@pytest.fixture()
def resolver() -> PhraseResolver:
    return PhraseResolver.from_callables(MOCK_PHRASES)


@pytest.fixture()
def executor(resolver) -> CharterExecutor:
    return CharterExecutor(resolver)


@pytest.fixture(autouse=True)
def _clear_log():
    _execution_log.clear()
    yield
    _execution_log.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPIPWorkflowEndToEnd:
    """Full PIP charter: compile → execute → verify results."""

    async def test_pip_charter_executes_all_phases(self, executor, compiled_pip):
        result = await executor.execute(compiled_pip, "pip_workflow", ctx=None)

        assert isinstance(result, WorkflowResult)
        assert result.charter_name == "Performance Improvement Plan"
        assert result.workflow_name == "pip_workflow"
        assert result.passed is True
        assert len(result.phase_results) == 3
        assert "eligibility" in result.phase_results
        assert "review" in result.phase_results
        assert "decision" in result.phase_results

    async def test_all_phases_pass(self, executor, compiled_pip):
        result = await executor.execute(compiled_pip, "pip_workflow", ctx=None)

        for name, pr in result.phase_results.items():
            assert pr.passed, f"Phase '{name}' should pass"
            assert pr.error is None

    async def test_action_results_populated(self, executor, compiled_pip):
        result = await executor.execute(compiled_pip, "pip_workflow", ctx=None)

        elig = result.phase_results["eligibility"]
        assert "assess_eligibility" in elig.action_results
        assert elig.action_results["assess_eligibility"]["eligible"] is True

        review = result.phase_results["review"]
        assert "evaluate_performance" in review.action_results
        assert "conduct_review" in review.action_results

        decision = result.phase_results["decision"]
        assert "certify_termination" in decision.action_results
        assert decision.action_results["certify_termination"]["immutable"] is True


class TestPhaseOrdering:
    """Verify phases execute in topological (dependency) order."""

    async def test_eligibility_before_review_before_decision(self, executor, compiled_pip):
        await executor.execute(compiled_pip, "pip_workflow", ctx=None)

        # Check execution log order
        assert _execution_log.index("assess_eligibility") < _execution_log.index(
            "evaluate_performance"
        )
        assert _execution_log.index("conduct_review") < _execution_log.index("certify_termination")

    async def test_all_actions_executed(self, executor, compiled_pip):
        await executor.execute(compiled_pip, "pip_workflow", ctx=None)

        assert "verify_consent" in _execution_log  # require gate
        assert "assess_eligibility" in _execution_log
        assert "evaluate_performance" in _execution_log
        assert "conduct_review" in _execution_log
        assert "certify_termination" in _execution_log


class TestGateFailure:
    """Verify require-gate failures cascade to downstream phases."""

    async def test_failed_require_cascades(self, compiled_pip):
        fail_phrases = dict(MOCK_PHRASES)
        fail_phrases["verify_consent"] = mock_verify_consent_fail

        resolver = PhraseResolver.from_callables(fail_phrases)
        executor = CharterExecutor(resolver)

        result = await executor.execute(compiled_pip, "pip_workflow", ctx=None)

        assert result.passed is False
        assert result.phase_results["eligibility"].passed is False
        assert "consent not granted" in result.phase_results["eligibility"].error

    async def test_downstream_phases_fail_on_dependency(self, compiled_pip):
        fail_phrases = dict(MOCK_PHRASES)
        fail_phrases["verify_consent"] = mock_verify_consent_fail

        resolver = PhraseResolver.from_callables(fail_phrases)
        executor = CharterExecutor(resolver)

        result = await executor.execute(compiled_pip, "pip_workflow", ctx=None)

        # Review depends on eligibility.passed → also fails
        assert result.phase_results["review"].passed is False
        # Decision depends on review.passed → also fails
        assert result.phase_results["decision"].passed is False

    async def test_failed_phase_prevents_downstream_actions(self, compiled_pip):
        fail_phrases = dict(MOCK_PHRASES)
        fail_phrases["verify_consent"] = mock_verify_consent_fail

        resolver = PhraseResolver.from_callables(fail_phrases)
        executor = CharterExecutor(resolver)

        await executor.execute(compiled_pip, "pip_workflow", ctx=None)

        # verify_consent was called but certify_termination was NOT
        assert "verify_consent_FAIL" in _execution_log
        assert "certify_termination" not in _execution_log


class TestStreamExecute:
    """Verify streaming execution yields PhaseResults."""

    async def test_stream_yields_phase_results(self, executor, compiled_pip):
        results = []
        async for pr in executor.stream_execute(compiled_pip, "pip_workflow", ctx=None):
            results.append(pr)

        assert len(results) == 3
        assert all(isinstance(r, PhaseResult) for r in results)
        assert results[0].phase_name == "eligibility"
        assert results[1].phase_name == "review"
        assert results[2].phase_name == "decision"

    async def test_stream_all_pass(self, executor, compiled_pip):
        async for pr in executor.stream_execute(compiled_pip, "pip_workflow", ctx=None):
            assert pr.passed, f"Phase '{pr.phase_name}' should pass"


class TestPhraseResolver:
    """Test PhraseResolver construction and lookup."""

    def test_from_callables(self):
        resolver = PhraseResolver.from_callables(MOCK_PHRASES)
        assert resolver.has("verify_consent")
        assert resolver.has("certify_termination")
        assert not resolver.has("nonexistent")

    def test_resolve_returns_callable(self):
        resolver = PhraseResolver.from_callables(MOCK_PHRASES)
        fn = resolver.resolve("verify_consent")
        assert fn is mock_verify_consent

    def test_resolve_unknown_raises(self):
        resolver = PhraseResolver.from_callables(MOCK_PHRASES)
        with pytest.raises(KeyError, match="not resolved"):
            resolver.resolve("nonexistent_feature")

    def test_feature_names(self):
        resolver = PhraseResolver.from_callables(MOCK_PHRASES)
        assert resolver.feature_names == frozenset(MOCK_PHRASES)
