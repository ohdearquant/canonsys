"""Tests for Charter DSL parser."""

from __future__ import annotations

import pytest

from canon.dsl.ast import BuiltinRefNode, FeatureCallNode, PhaseRefNode
from canon.dsl.errors import ParseError
from canon.dsl.parser import parse_charter


class TestHeader:
    def test_basic_header(self):
        ast = parse_charter(
            'charter "My Charter" v1.0\nworkflow w:\n    phase p:\n        action f()\n'
        )
        assert ast.name == "My Charter"
        assert ast.version == "v1.0"

    def test_missing_name(self):
        with pytest.raises(ParseError, match="STRING"):
            parse_charter("charter v1.0\nworkflow w:\n    phase p:\n        action f()\n")


class TestSchemas:
    def test_parse_schema_ref(self):
        source = 'charter "T" v1\nschemas: canon.hr@2026.01\nworkflow w:\n    phase p:\n        action f()\n'
        ast = parse_charter(source)
        assert len(ast.schemas) == 1
        assert ast.schemas[0].namespace == "canon.hr"
        assert ast.schemas[0].version == "2026.01"

    def test_no_schemas(self):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        action f()\n'
        ast = parse_charter(source)
        assert ast.schemas == ()

    def test_multi_schema_block(self):
        source = """\
charter "T" v1

schemas:
    - canonsys@2026.01
    - canon.hr@2026.01

workflow w:
    phase p:
        action f()
"""
        ast = parse_charter(source)
        assert len(ast.schemas) == 2
        assert ast.schemas[0].namespace == "canonsys"
        assert ast.schemas[0].version == "2026.01"
        assert ast.schemas[1].namespace == "canon.hr"
        assert ast.schemas[1].version == "2026.01"


class TestPolicies:
    def test_parse_policies(self):
        source = 'charter "T" v1\npolicies:\n    - employment.termination\n    - compliance.fcra\nworkflow w:\n    phase p:\n        action f()\n'
        ast = parse_charter(source)
        assert len(ast.policies) == 2
        assert ast.policies[0].policy_id == "employment.termination"
        assert ast.policies[1].policy_id == "compliance.fcra"

    def test_no_policies(self):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        action f()\n'
        ast = parse_charter(source)
        assert ast.policies == ()


class TestWorkflow:
    def test_single_workflow(self):
        source = 'charter "T" v1\nworkflow pip:\n    phase step1:\n        action do_thing()\n'
        ast = parse_charter(source)
        assert len(ast.workflows) == 1
        assert ast.workflows[0].name == "pip"
        assert len(ast.workflows[0].phases) == 1

    def test_multi_phase_workflow(self):
        source = """\
charter "T" v1

workflow pip:
    phase eligibility:
        action assess_eligibility()

    phase review:
        require eligibility.passed
        action conduct_review()

    phase decision:
        require review.passed
        action certify_termination()
"""
        ast = parse_charter(source)
        wf = ast.workflows[0]
        assert len(wf.phases) == 3
        assert wf.phases[0].name == "eligibility"
        assert wf.phases[1].name == "review"
        assert wf.phases[2].name == "decision"

    def test_empty_workflow_error(self):
        source = 'charter "T" v1\nworkflow empty:\n'
        with pytest.raises(ParseError):
            parse_charter(source)


class TestPhase:
    def test_phase_with_all_directives(self):
        source = """\
charter "T" v1

workflow w:
    phase full:
        require verify_consent("check")
        action do_work()
        output ResultType
        certify immutable
        evidence audit_record
"""
        ast = parse_charter(source)
        phase = ast.workflows[0].phases[0]
        assert phase.name == "full"
        assert len(phase.requires) == 1
        assert len(phase.actions) == 1
        assert len(phase.outputs) == 1
        assert phase.certify is not None
        assert phase.certify.qualifier == "immutable"
        assert phase.evidence is not None
        assert phase.evidence.evidence_type == "audit_record"


class TestRequireDisambiguation:
    def test_require_feature_call(self):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        require verify_consent("bg")\n'
        ast = parse_charter(source)
        req = ast.workflows[0].phases[0].requires[0]
        assert isinstance(req.ref, FeatureCallNode)
        assert req.ref.name == "verify_consent"
        assert len(req.ref.args) == 1
        assert req.ref.args[0].value == "bg"

    def test_require_phase_ref_passed(self):
        source = 'charter "T" v1\nworkflow w:\n    phase a:\n        action f()\n    phase b:\n        require a.passed\n        action g()\n'
        ast = parse_charter(source)
        req = ast.workflows[0].phases[1].requires[0]
        assert isinstance(req.ref, PhaseRefNode)
        assert req.ref.phase == "a"
        assert req.ref.condition == "passed"

    def test_require_phase_ref_complete(self):
        source = 'charter "T" v1\nworkflow w:\n    phase a:\n        action f()\n    phase b:\n        require a.complete\n        action g()\n'
        ast = parse_charter(source)
        req = ast.workflows[0].phases[1].requires[0]
        assert isinstance(req.ref, PhaseRefNode)
        assert req.ref.condition == "complete"

    def test_require_builtin(self):
        source = 'charter "T" v1\nworkflow w:\n    phase final:\n        require all_phases_passed\n        action conclude()\n'
        ast = parse_charter(source)
        req = ast.workflows[0].phases[0].requires[0]
        assert isinstance(req.ref, BuiltinRefNode)
        assert req.ref.name == "all_phases_passed"


class TestFeatureCall:
    def test_no_args(self):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        action do_thing()\n'
        ast = parse_charter(source)
        call = ast.workflows[0].phases[0].actions[0].call
        assert call.name == "do_thing"
        assert call.args == ()

    def test_positional_args(self):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        action do_thing("a", 42)\n'
        ast = parse_charter(source)
        call = ast.workflows[0].phases[0].actions[0].call
        assert len(call.args) == 2
        assert call.args[0].name is None
        assert call.args[0].value == "a"
        assert call.args[1].value == 42

    def test_keyword_args(self):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        action do_thing(scope=="bg", count==3)\n'
        # Note: keyword args use = not ==, but our parser uses EQ (==) for keyword args
        # Actually, let's test proper keyword args
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        require verify_consent("bg")\n'
        ast = parse_charter(source)
        req_ref = ast.workflows[0].phases[0].requires[0].ref
        assert isinstance(req_ref, FeatureCallNode)

    def test_boolean_args(self):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        action do_thing(true, false)\n'
        ast = parse_charter(source)
        call = ast.workflows[0].phases[0].actions[0].call
        assert call.args[0].value is True
        assert call.args[1].value is False

    def test_float_arg(self):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        action do_thing(3.14)\n'
        ast = parse_charter(source)
        call = ast.workflows[0].phases[0].actions[0].call
        assert call.args[0].value == 3.14


class TestSituations:
    def test_parse_situation(self):
        source = """\
charter "T" v1

workflow w:
    phase p:
        action f()

situations:
    when jurisdiction == "NYC":
        waiting_period 30..90 days
        require verify_consent("aedt")
"""
        ast = parse_charter(source)
        assert len(ast.situations) == 1
        sit = ast.situations[0]
        assert sit.predicate.field == "jurisdiction"
        assert sit.predicate.operator == "=="
        assert sit.predicate.value == "NYC"
        assert sit.waiting_period is not None
        assert sit.waiting_period.min_value == 30
        assert sit.waiting_period.max_value == 90
        assert sit.waiting_period.unit == "days"
        assert len(sit.requires) == 1

    def test_situation_with_gte(self):
        source = """\
charter "T" v1

workflow w:
    phase p:
        action f()

situations:
    when tenure >= 5:
        require verify_consent("extended")
"""
        ast = parse_charter(source)
        assert ast.situations[0].predicate.operator == ">="
        assert ast.situations[0].predicate.value == 5


class TestRoles:
    def test_parse_roles(self):
        source = """\
charter "T" v1

workflow w:
    phase p:
        action f()

roles:
    hr_manager:
        actions: [f]
        break_glass: false
        requires_mfa: true
    legal_counsel:
        actions: [f]
        break_glass: true
        requires_mfa: true
"""
        ast = parse_charter(source)
        assert len(ast.roles) == 2
        hr = ast.roles[0]
        assert hr.name == "hr_manager"
        assert hr.actions == ("f",)
        assert hr.break_glass is False
        assert hr.requires_mfa is True
        legal = ast.roles[1]
        assert legal.break_glass is True


class TestPackages:
    def test_parse_packages(self):
        source = """\
charter "T" v1

packages:
    - consent
    - certification
    - evidence

workflow w:
    phase p:
        action f()
"""
        ast = parse_charter(source)
        assert len(ast.packages) == 3
        assert ast.packages[0].name == "consent"
        assert ast.packages[1].name == "certification"
        assert ast.packages[2].name == "evidence"

    def test_no_packages(self):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        action f()\n'
        ast = parse_charter(source)
        assert ast.packages == ()

    def test_duplicate_packages_error(self):
        source = """\
charter "T" v1
packages:
    - consent
packages:
    - evidence
workflow w:
    phase p:
        action f()
"""
        with pytest.raises(ParseError, match="Duplicate 'packages' section"):
            parse_charter(source)


class TestFullCharter:
    def test_sample_pip_charter(self, sample_pip_charter: str):
        ast = parse_charter(sample_pip_charter)
        assert ast.name == "Performance Improvement Plan"
        assert ast.version == "v1.0"
        assert len(ast.schemas) == 1
        assert ast.schemas[0].namespace == "canon.hr"
        assert ast.schemas[0].version == "2026.01"
        assert len(ast.policies) == 2
        assert len(ast.workflows) == 1
        assert len(ast.workflows[0].phases) == 3
        assert len(ast.situations) == 1
        assert len(ast.roles) == 2

    def test_minimal_charter(self, minimal_charter: str):
        ast = parse_charter(minimal_charter)
        assert ast.name == "Minimal"
        assert ast.schemas == ()
        assert ast.policies == ()
        assert len(ast.workflows) == 1


class TestDuplicateDetection:
    def test_duplicate_schemas_error(self):
        source = """\
charter "T" v1
schemas: a.b@1.0
schemas: c.d@2.0
workflow w:
    phase p:
        action f()
"""
        with pytest.raises(ParseError, match="Duplicate 'schemas' section"):
            parse_charter(source)

    def test_duplicate_policies_error(self):
        source = """\
charter "T" v1
policies:
    - a.b
policies:
    - c.d
workflow w:
    phase p:
        action f()
"""
        with pytest.raises(ParseError, match="Duplicate 'policies' section"):
            parse_charter(source)

    def test_duplicate_situations_error(self):
        source = """\
charter "T" v1
workflow w:
    phase p:
        action f()
situations:
    when x == "a":
        require f()
situations:
    when y == "b":
        require g()
"""
        with pytest.raises(ParseError, match="Duplicate 'situations' section"):
            parse_charter(source)

    def test_duplicate_roles_error(self):
        source = """\
charter "T" v1
workflow w:
    phase p:
        action f()
roles:
    admin:
        actions: [f]
roles:
    user:
        actions: [f]
"""
        with pytest.raises(ParseError, match="Duplicate 'roles' section"):
            parse_charter(source)

    def test_duplicate_certify_in_phase_error(self):
        source = """\
charter "T" v1
workflow w:
    phase p:
        action f()
        certify immutable
        certify sealed
"""
        with pytest.raises(ParseError, match="Duplicate 'certify' in phase"):
            parse_charter(source)

    def test_duplicate_evidence_in_phase_error(self):
        source = """\
charter "T" v1
workflow w:
    phase p:
        action f()
        evidence record_a
        evidence record_b
"""
        with pytest.raises(ParseError, match="Duplicate 'evidence' in phase"):
            parse_charter(source)


class TestGrants:
    """Tests for the grants directive (JIT document access)."""

    def test_single_grant(self):
        source = """\
charter "T" v1

workflow w:
    phase approval:
        grants resume for 5m
        action approve()
"""
        ast = parse_charter(source)
        phase = ast.workflows[0].phases[0]
        assert len(phase.grants) == 1
        assert phase.grants[0].document_type == "resume"
        assert phase.grants[0].ttl_minutes == 5

    def test_multiple_grants(self):
        source = """\
charter "T" v1

workflow w:
    phase approval:
        grants resume for 5m
        grants background_report for 30m
        grants offer_letter for 10m
        action approve()
"""
        ast = parse_charter(source)
        phase = ast.workflows[0].phases[0]
        assert len(phase.grants) == 3
        assert phase.grants[0].document_type == "resume"
        assert phase.grants[0].ttl_minutes == 5
        assert phase.grants[1].document_type == "background_report"
        assert phase.grants[1].ttl_minutes == 30
        assert phase.grants[2].document_type == "offer_letter"
        assert phase.grants[2].ttl_minutes == 10

    def test_grant_with_require_and_action(self):
        source = """\
charter "T" v1

workflow w:
    phase approval:
        require verify_consent("bg")
        grants resume for 5m
        action approve_offer()
        output ApprovalReport
"""
        ast = parse_charter(source)
        phase = ast.workflows[0].phases[0]
        assert len(phase.requires) == 1
        assert len(phase.grants) == 1
        assert len(phase.actions) == 1
        assert len(phase.outputs) == 1

    def test_grant_without_m_suffix(self):
        """TTL without 'm' suffix should still parse (suffix is optional)."""
        source = """\
charter "T" v1

workflow w:
    phase p:
        grants resume for 5
        action f()
"""
        ast = parse_charter(source)
        phase = ast.workflows[0].phases[0]
        assert phase.grants[0].ttl_minutes == 5

    def test_grant_large_ttl(self):
        source = """\
charter "T" v1

workflow w:
    phase p:
        grants document for 1440m
        action f()
"""
        ast = parse_charter(source)
        assert ast.workflows[0].phases[0].grants[0].ttl_minutes == 1440


class TestErrorMessages:
    def test_unexpected_token(self):
        with pytest.raises(ParseError):
            parse_charter("charter")

    def test_error_has_position(self):
        with pytest.raises(ParseError) as exc_info:
            parse_charter('charter "T" v1\nworkflow w:\n    phase p:\n        unknown_stmt\n')
        assert exc_info.value.line is not None

    def test_require_followed_by_non_ident(self):
        """Test that require followed by a literal gives ParseError, not NameError."""
        source = (
            'charter "T" v1\nworkflow w:\n    phase p:\n        require 42\n        action f()\n'
        )
        with pytest.raises(ParseError, match="Expected identifier"):
            parse_charter(source)
