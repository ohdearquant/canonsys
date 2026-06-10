"""Integration tests for Charter DSL — full pipeline."""

from __future__ import annotations

from canon.dsl import CompiledCharter, Resolver, compile_charter, parse_charter
from canon.dsl.ast import CharterNode, PhaseRefNode


class TestLexParseRoundtrip:
    """Test that lex -> parse produces correct AST."""

    def test_full_pipeline_produces_charter_node(self, sample_pip_charter):
        ast = parse_charter(sample_pip_charter)
        assert isinstance(ast, CharterNode)
        assert ast.name == "Performance Improvement Plan"

    def test_phase_dependencies_parsed(self, sample_pip_charter):
        ast = parse_charter(sample_pip_charter)
        wf = ast.workflows[0]
        review = wf.phases[1]
        assert len(review.requires) == 1
        assert isinstance(review.requires[0].ref, PhaseRefNode)
        assert review.requires[0].ref.phase == "eligibility"


class TestFullCompilation:
    """End-to-end: source -> CompiledCharter."""

    def test_pip_charter_compiles(
        self, sample_pip_charter, mock_catalog, mock_features, mock_policies
    ):
        compiled = compile_charter(
            sample_pip_charter,
            catalog=mock_catalog,
            feature_registry=mock_features,
            policy_registry=mock_policies,
        )

        # Correct type
        assert isinstance(compiled, CompiledCharter)

        # Charter metadata
        assert compiled.name == "Performance Improvement Plan"
        assert compiled.version == "v1.0"

        # 1 workflow, 3 phases
        assert len(compiled.workflow_names) == 1
        assert len(compiled.phase_order["pip_workflow"]) == 3

        # Topological order: eligibility < review < decision
        order = compiled.phase_order["pip_workflow"]
        assert order == ("eligibility", "review", "decision")

        # Feature coverage
        expected_features = {
            "verify_consent",
            "assess_eligibility",
            "evaluate_performance",
            "conduct_review",
            "certify_termination",
        }
        assert expected_features.issubset(compiled.feature_names)

        # Schema resolution
        assert len(compiled.schema_types) == 3
        for name in ("EligibilityReport", "PIPReport", "TerminationCertificate"):
            assert name in compiled.schema_types

        # Policy IDs
        assert compiled.policy_ids == frozenset(
            {
                "employment.pip",
                "employment.termination",
            }
        )

        # Situations
        assert len(compiled.situations) == 1
        sit = compiled.situations[0]
        assert sit.predicate.field == "jurisdiction"
        assert sit.predicate.operator == "=="
        assert sit.predicate.value == "NYC"
        assert sit.waiting_period is not None
        assert sit.waiting_period.min_value == 30
        assert sit.waiting_period.max_value == 90

        # Roles
        assert len(compiled.roles) == 2
        role_names = {r.name for r in compiled.roles}
        assert role_names == {"hr_manager", "legal_counsel"}


class TestResolverStandalone:
    """Resolver with different registry configurations."""

    def test_resolver_no_registries(self, sample_pip_charter):
        """Without registries, resolver skips all external checks."""
        ast = parse_charter(sample_pip_charter)
        resolved = Resolver().resolve(ast)
        assert resolved.ast is ast
        assert len(resolved.feature_names) > 0
        assert resolved.phase_order["pip_workflow"] == (
            "eligibility",
            "review",
            "decision",
        )

    def test_resolver_partial_registry(self, sample_pip_charter, mock_catalog):
        """With only catalog, resolver validates schemas but not features."""
        ast = parse_charter(sample_pip_charter)
        resolved = Resolver(catalog=mock_catalog).resolve(ast)
        assert "EligibilityReport" in resolved.schema_types


class TestMultipleWorkflows:
    """Charters with multiple workflows."""

    def test_two_workflows(self):
        source = """\
charter "Multi" v1

workflow hiring:
    phase screen:
        action screen_candidates()
    phase interview:
        require screen.passed
        action conduct_interview()

workflow onboarding:
    phase setup:
        action create_account()
    phase training:
        require setup.passed
        action assign_training()
"""
        compiled = compile_charter(source)
        assert compiled.workflow_names == ("hiring", "onboarding")
        assert compiled.phase_order["hiring"] == ("screen", "interview")
        assert compiled.phase_order["onboarding"] == ("setup", "training")


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_phase_with_no_requires(self):
        source = """\
charter "T" v1
workflow w:
    phase standalone:
        action do_work()
"""
        compiled = compile_charter(source)
        assert compiled.phase_order["w"] == ("standalone",)

    def test_multiple_actions_in_phase(self):
        source = """\
charter "T" v1
workflow w:
    phase multi:
        action step_one()
        action step_two()
        action step_three()
"""
        ast = parse_charter(source)
        assert len(ast.workflows[0].phases[0].actions) == 3

    def test_multiple_requires_in_phase(self):
        source = """\
charter "T" v1
workflow w:
    phase a:
        action f()
    phase b:
        action g()
    phase c:
        require a.passed
        require b.passed
        action h()
"""
        compiled = compile_charter(source)
        order = compiled.phase_order["w"]
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("c")

    def test_charter_with_comments(self):
        source = """\
# This is a charter
charter "Commented" v1

# Workflow section
workflow w:
    # First phase
    phase p:
        action f()
"""
        ast = parse_charter(source)
        assert ast.name == "Commented"
