"""Tests for Charter DSL compiler."""

from __future__ import annotations

import pytest

from canon.dsl.compiler import CompiledCharter, compile_charter
from canon.dsl.errors import LexError, ParseError


class TestCompileCharter:
    def test_minimal_compilation(self, minimal_charter):
        compiled = compile_charter(minimal_charter)
        assert isinstance(compiled, CompiledCharter)
        assert compiled.name == "Minimal"
        assert compiled.version == "v0.1"
        assert "verify_consent" in compiled.feature_names
        assert compiled.workflow_names == ("basic",)

    def test_full_compilation(self, sample_pip_charter, mock_catalog, mock_features, mock_policies):
        compiled = compile_charter(
            sample_pip_charter,
            catalog=mock_catalog,
            feature_registry=mock_features,
            policy_registry=mock_policies,
        )
        assert compiled.name == "Performance Improvement Plan"
        assert compiled.version == "v1.0"
        assert compiled.workflow_names == ("pip_workflow",)

        # Phase order should be topological
        order = compiled.phase_order["pip_workflow"]
        assert order.index("eligibility") < order.index("review")
        assert order.index("review") < order.index("decision")

        # Features collected
        assert "verify_consent" in compiled.feature_names
        assert "assess_eligibility" in compiled.feature_names
        assert "certify_termination" in compiled.feature_names

        # Schemas resolved
        assert "EligibilityReport" in compiled.schema_types
        assert "PIPReport" in compiled.schema_types
        assert "TerminationCertificate" in compiled.schema_types

        # Policies collected
        assert "employment.pip" in compiled.policy_ids
        assert "employment.termination" in compiled.policy_ids

        # Situations
        assert len(compiled.situations) == 1
        assert compiled.situations[0].predicate.field == "jurisdiction"

        # Roles
        assert len(compiled.roles) == 2

    def test_lex_error_propagates(self):
        with pytest.raises(LexError):
            compile_charter('charter "T" v1\n\tbad_indent')

    def test_parse_error_propagates(self):
        with pytest.raises(ParseError):
            compile_charter("not a charter")

    def test_resolve_error_propagates(self, mock_features):
        source = 'charter "T" v1\nworkflow w:\n    phase p:\n        action unknown_feature()\n'
        with pytest.raises(ExceptionGroup):
            compile_charter(source, feature_registry=mock_features)


class TestCompiledCharterProperties:
    def test_workflow_names(self):
        source = """\
charter "T" v1

workflow first:
    phase a:
        action f()

workflow second:
    phase b:
        action g()
"""
        compiled = compile_charter(source)
        assert compiled.workflow_names == ("first", "second")

    def test_no_registries_compiles(self):
        """Compilation without registries skips validation."""
        source = """\
charter "T" v1
schemas: any.ns@1.0
policies:
    - any.policy
workflow w:
    phase p:
        action any_feature()
        output AnyType
"""
        compiled = compile_charter(source)
        assert compiled.name == "T"
        assert "any_feature" in compiled.feature_names
