"""Tests for charter runtime condition evaluation.

Tests cover:
- evaluate_predicate: all operators, missing fields, type coercion, edge cases
- evaluate_when_block / evaluate_when_blocks: matching/non-matching predicates
- evaluate_situations: multiple situations, waiting period overrides, require aggregation
"""

from __future__ import annotations

import pytest

from canon.dsl.ast import (
    ActionNode,
    AwaitNode,
    FeatureCallNode,
    PredicateNode,
    RequireNode,
    SituationNode,
    WaitingPeriodNode,
    WhenBlockNode,
)
from canon.runtime.conditions import (
    ConditionResult,
    SituationOverrides,
    WhenBlockResult,
    evaluate_predicate,
    evaluate_situations,
    evaluate_when_block,
    evaluate_when_blocks,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def nyc_predicate() -> PredicateNode:
    """Predicate: jurisdiction == 'NYC'."""
    return PredicateNode(field="jurisdiction", operator="==", value="NYC")


@pytest.fixture
def filed_predicate() -> PredicateNode:
    """Predicate: dispute_status == 'FILED'."""
    return PredicateNode(field="dispute_status", operator="==", value="FILED")


@pytest.fixture
def salary_predicate() -> PredicateNode:
    """Predicate: salary > 100000."""
    return PredicateNode(field="salary", operator=">", value=100000)


@pytest.fixture
def when_block_dispute(filed_predicate: PredicateNode) -> WhenBlockNode:
    """When block for dispute filed scenario."""
    return WhenBlockNode(
        predicate=filed_predicate,
        requires=(RequireNode(ref=FeatureCallNode(name="require_legal_review_complete", args=())),),
        actions=(ActionNode(call=FeatureCallNode(name="investigate_dispute", args=())),),
        awaits=(AwaitNode(trigger="candidate_files_dispute"),),
    )


@pytest.fixture
def when_block_nyc(nyc_predicate: PredicateNode) -> WhenBlockNode:
    """When block for NYC jurisdiction."""
    return WhenBlockNode(
        predicate=nyc_predicate,
        requires=(RequireNode(ref=FeatureCallNode(name="verify_aedt_disclosure", args=())),),
        actions=(),
        awaits=(),
    )


@pytest.fixture
def situation_nyc(nyc_predicate: PredicateNode) -> SituationNode:
    """Situation node for NYC jurisdiction."""
    return SituationNode(
        predicate=nyc_predicate,
        waiting_period=WaitingPeriodNode(min_value=30, max_value=90, unit="days"),
        requires=(RequireNode(ref=FeatureCallNode(name="verify_consent", args=())),),
    )


@pytest.fixture
def situation_california() -> SituationNode:
    """Situation node for California jurisdiction."""
    return SituationNode(
        predicate=PredicateNode(field="jurisdiction", operator="==", value="CA"),
        waiting_period=WaitingPeriodNode(min_value=60, max_value=120, unit="days"),
        requires=(RequireNode(ref=FeatureCallNode(name="verify_warn_notice", args=())),),
    )


@pytest.fixture
def situation_no_waiting() -> SituationNode:
    """Situation node without waiting period."""
    return SituationNode(
        predicate=PredicateNode(field="employee_type", operator="==", value="contractor"),
        waiting_period=None,
        requires=(RequireNode(ref=FeatureCallNode(name="verify_contract_terms", args=())),),
    )


# =============================================================================
# Tests: evaluate_predicate
# =============================================================================


class TestEvaluatePredicate:
    """Test predicate evaluation with all operators and edge cases."""

    # -- Equality operator --

    def test_eq_string_match(self, nyc_predicate: PredicateNode):
        result = evaluate_predicate(nyc_predicate, {"jurisdiction": "NYC"})
        assert result.matched is True
        assert result.predicate_field == "jurisdiction"
        assert result.predicate_operator == "=="
        assert result.predicate_value == "NYC"
        assert result.actual_value == "NYC"
        assert result.reason is None

    def test_eq_string_no_match(self, nyc_predicate: PredicateNode):
        result = evaluate_predicate(nyc_predicate, {"jurisdiction": "CA"})
        assert result.matched is False
        assert result.actual_value == "CA"
        assert result.reason is not None
        assert "CA" in result.reason

    def test_eq_int_match(self):
        pred = PredicateNode(field="count", operator="==", value=5)
        result = evaluate_predicate(pred, {"count": 5})
        assert result.matched is True

    def test_eq_bool_match(self):
        pred = PredicateNode(field="is_active", operator="==", value=True)
        result = evaluate_predicate(pred, {"is_active": True})
        assert result.matched is True

    def test_eq_bool_no_match(self):
        pred = PredicateNode(field="is_active", operator="==", value=True)
        result = evaluate_predicate(pred, {"is_active": False})
        assert result.matched is False

    # -- Inequality operator --

    def test_ne_match(self):
        pred = PredicateNode(field="status", operator="!=", value="CLOSED")
        result = evaluate_predicate(pred, {"status": "OPEN"})
        assert result.matched is True

    def test_ne_no_match(self):
        pred = PredicateNode(field="status", operator="!=", value="CLOSED")
        result = evaluate_predicate(pred, {"status": "CLOSED"})
        assert result.matched is False

    # -- Greater than --

    def test_gt_match(self, salary_predicate: PredicateNode):
        result = evaluate_predicate(salary_predicate, {"salary": 150000})
        assert result.matched is True

    def test_gt_no_match_equal(self, salary_predicate: PredicateNode):
        result = evaluate_predicate(salary_predicate, {"salary": 100000})
        assert result.matched is False

    def test_gt_no_match_less(self, salary_predicate: PredicateNode):
        result = evaluate_predicate(salary_predicate, {"salary": 50000})
        assert result.matched is False

    # -- Less than --

    def test_lt_match(self):
        pred = PredicateNode(field="score", operator="<", value=80)
        result = evaluate_predicate(pred, {"score": 60})
        assert result.matched is True

    def test_lt_no_match(self):
        pred = PredicateNode(field="score", operator="<", value=80)
        result = evaluate_predicate(pred, {"score": 80})
        assert result.matched is False

    # -- Greater than or equal --

    def test_gte_match_equal(self):
        pred = PredicateNode(field="level", operator=">=", value=3)
        result = evaluate_predicate(pred, {"level": 3})
        assert result.matched is True

    def test_gte_match_greater(self):
        pred = PredicateNode(field="level", operator=">=", value=3)
        result = evaluate_predicate(pred, {"level": 5})
        assert result.matched is True

    def test_gte_no_match(self):
        pred = PredicateNode(field="level", operator=">=", value=3)
        result = evaluate_predicate(pred, {"level": 2})
        assert result.matched is False

    # -- Less than or equal --

    def test_lte_match_equal(self):
        pred = PredicateNode(field="days", operator="<=", value=30)
        result = evaluate_predicate(pred, {"days": 30})
        assert result.matched is True

    def test_lte_match_less(self):
        pred = PredicateNode(field="days", operator="<=", value=30)
        result = evaluate_predicate(pred, {"days": 10})
        assert result.matched is True

    def test_lte_no_match(self):
        pred = PredicateNode(field="days", operator="<=", value=30)
        result = evaluate_predicate(pred, {"days": 31})
        assert result.matched is False

    # -- Missing field --

    def test_missing_field(self, nyc_predicate: PredicateNode):
        result = evaluate_predicate(nyc_predicate, {})
        assert result.matched is False
        assert result.actual_value is None
        assert "not found in context" in result.reason

    def test_missing_field_different_keys(self, nyc_predicate: PredicateNode):
        result = evaluate_predicate(nyc_predicate, {"state": "NY", "city": "NYC"})
        assert result.matched is False
        assert "jurisdiction" in result.reason

    # -- Unknown operator --

    def test_unknown_operator(self):
        pred = PredicateNode(field="x", operator="~=", value="y")
        result = evaluate_predicate(pred, {"x": "y"})
        assert result.matched is False
        assert "Unknown operator" in result.reason

    # -- Empty context --

    def test_empty_context(self, nyc_predicate: PredicateNode):
        result = evaluate_predicate(nyc_predicate, {})
        assert result.matched is False

    # -- Type coercion --

    def test_string_to_int_coercion(self):
        """Context has string '5', predicate expects int 5."""
        pred = PredicateNode(field="count", operator="==", value=5)
        result = evaluate_predicate(pred, {"count": "5"})
        assert result.matched is True

    def test_string_to_float_coercion(self):
        """Context has string '3.14', predicate expects float."""
        pred = PredicateNode(field="rate", operator="==", value=3.14)
        result = evaluate_predicate(pred, {"rate": "3.14"})
        assert result.matched is True

    def test_string_to_bool_coercion(self):
        """Context has string 'true', predicate expects bool True."""
        pred = PredicateNode(field="active", operator="==", value=True)
        result = evaluate_predicate(pred, {"active": "true"})
        assert result.matched is True

    def test_string_to_bool_coercion_false(self):
        """Context has string 'false', predicate expects bool True."""
        pred = PredicateNode(field="active", operator="==", value=True)
        result = evaluate_predicate(pred, {"active": "false"})
        assert result.matched is False

    def test_int_to_string_coercion(self):
        """Context has int 42, predicate expects string '42'."""
        pred = PredicateNode(field="code", operator="==", value="42")
        result = evaluate_predicate(pred, {"code": 42})
        assert result.matched is True

    def test_numeric_comparison_with_string_coercion(self):
        """Context has string '150', predicate expects int > 100."""
        pred = PredicateNode(field="score", operator=">", value=100)
        result = evaluate_predicate(pred, {"score": "150"})
        assert result.matched is True

    def test_incompatible_type_comparison(self):
        """Context has non-coercible type for ordered comparison."""
        pred = PredicateNode(field="data", operator=">", value=10)
        result = evaluate_predicate(pred, {"data": "not_a_number"})
        # Should fail gracefully (either coercion error or type mismatch)
        assert result.matched is False

    # -- ConditionResult structure --

    def test_result_is_frozen(self, nyc_predicate: PredicateNode):
        result = evaluate_predicate(nyc_predicate, {"jurisdiction": "NYC"})
        assert isinstance(result, ConditionResult)
        with pytest.raises(AttributeError):
            result.matched = False  # type: ignore[misc]

    def test_result_fields_populated(self, nyc_predicate: PredicateNode):
        result = evaluate_predicate(nyc_predicate, {"jurisdiction": "NYC"})
        assert result.predicate_field == "jurisdiction"
        assert result.predicate_operator == "=="
        assert result.predicate_value == "NYC"
        assert result.actual_value == "NYC"

    # -- Float comparison --

    def test_float_equality(self):
        pred = PredicateNode(field="rate", operator="==", value=0.05)
        result = evaluate_predicate(pred, {"rate": 0.05})
        assert result.matched is True

    def test_float_gt(self):
        pred = PredicateNode(field="rate", operator=">", value=0.05)
        result = evaluate_predicate(pred, {"rate": 0.06})
        assert result.matched is True

    # -- None value in context --

    def test_none_value_in_context(self):
        """None values in context should not match (except != comparisons)."""
        pred = PredicateNode(field="jurisdiction", operator="==", value="NYC")
        result = evaluate_predicate(pred, {"jurisdiction": None})
        assert result.matched is False


# =============================================================================
# Tests: evaluate_when_block
# =============================================================================


class TestEvaluateWhenBlock:
    """Test when_block evaluation."""

    def test_matching_when_block(self, when_block_dispute: WhenBlockNode):
        result = evaluate_when_block(when_block_dispute, {"dispute_status": "FILED"})
        assert result.matched is True
        assert result.condition.matched is True
        assert result.block is when_block_dispute

    def test_non_matching_when_block(self, when_block_dispute: WhenBlockNode):
        result = evaluate_when_block(when_block_dispute, {"dispute_status": "RESOLVED"})
        assert result.matched is False
        assert result.condition.matched is False

    def test_missing_context_field(self, when_block_dispute: WhenBlockNode):
        result = evaluate_when_block(when_block_dispute, {})
        assert result.matched is False

    def test_matched_block_has_requires(self, when_block_dispute: WhenBlockNode):
        result = evaluate_when_block(when_block_dispute, {"dispute_status": "FILED"})
        assert result.matched is True
        assert len(result.block.requires) == 1
        assert result.block.requires[0].ref.name == "require_legal_review_complete"

    def test_matched_block_has_actions(self, when_block_dispute: WhenBlockNode):
        result = evaluate_when_block(when_block_dispute, {"dispute_status": "FILED"})
        assert len(result.block.actions) == 1
        assert result.block.actions[0].call.name == "investigate_dispute"

    def test_matched_block_has_awaits(self, when_block_dispute: WhenBlockNode):
        result = evaluate_when_block(when_block_dispute, {"dispute_status": "FILED"})
        assert len(result.block.awaits) == 1
        assert result.block.awaits[0].trigger == "candidate_files_dispute"

    def test_result_is_frozen(self, when_block_dispute: WhenBlockNode):
        result = evaluate_when_block(when_block_dispute, {"dispute_status": "FILED"})
        assert isinstance(result, WhenBlockResult)
        with pytest.raises(AttributeError):
            result.matched = False  # type: ignore[misc]


class TestEvaluateWhenBlocks:
    """Test batch when_block evaluation."""

    def test_all_match(
        self,
        when_block_dispute: WhenBlockNode,
        when_block_nyc: WhenBlockNode,
    ):
        context = {"dispute_status": "FILED", "jurisdiction": "NYC"}
        results = evaluate_when_blocks((when_block_dispute, when_block_nyc), context)
        assert len(results) == 2
        assert all(r.matched for r in results)

    def test_partial_match(
        self,
        when_block_dispute: WhenBlockNode,
        when_block_nyc: WhenBlockNode,
    ):
        context = {"dispute_status": "FILED", "jurisdiction": "CA"}
        results = evaluate_when_blocks((when_block_dispute, when_block_nyc), context)
        assert len(results) == 2
        assert results[0].matched is True  # dispute matches
        assert results[1].matched is False  # NYC does not match

    def test_none_match(
        self,
        when_block_dispute: WhenBlockNode,
        when_block_nyc: WhenBlockNode,
    ):
        context = {"dispute_status": "RESOLVED", "jurisdiction": "TX"}
        results = evaluate_when_blocks((when_block_dispute, when_block_nyc), context)
        assert len(results) == 2
        assert not any(r.matched for r in results)

    def test_empty_blocks(self):
        results = evaluate_when_blocks((), {"jurisdiction": "NYC"})
        assert results == []

    def test_empty_context(self, when_block_dispute: WhenBlockNode):
        results = evaluate_when_blocks((when_block_dispute,), {})
        assert len(results) == 1
        assert results[0].matched is False


# =============================================================================
# Tests: evaluate_situations
# =============================================================================


class TestEvaluateSituations:
    """Test situation evaluation with waiting periods and requires."""

    def test_single_situation_matches(self, situation_nyc: SituationNode):
        result = evaluate_situations((situation_nyc,), {"jurisdiction": "NYC"})
        assert isinstance(result, SituationOverrides)
        assert len(result.matched_situations) == 1
        assert result.matched_situations[0] is situation_nyc

    def test_single_situation_no_match(self, situation_nyc: SituationNode):
        result = evaluate_situations((situation_nyc,), {"jurisdiction": "TX"})
        assert len(result.matched_situations) == 0
        assert len(result.additional_requires) == 0
        assert result.waiting_period_override is None

    def test_additional_requires_collected(self, situation_nyc: SituationNode):
        result = evaluate_situations((situation_nyc,), {"jurisdiction": "NYC"})
        assert len(result.additional_requires) == 1
        assert result.additional_requires[0].ref.name == "verify_consent"

    def test_waiting_period_set(self, situation_nyc: SituationNode):
        result = evaluate_situations((situation_nyc,), {"jurisdiction": "NYC"})
        assert result.waiting_period_override is not None
        assert result.waiting_period_override.min_value == 30
        assert result.waiting_period_override.max_value == 90
        assert result.waiting_period_override.unit == "days"

    def test_no_situations(self):
        result = evaluate_situations((), {"jurisdiction": "NYC"})
        assert len(result.matched_situations) == 0
        assert len(result.additional_requires) == 0
        assert result.waiting_period_override is None

    def test_empty_context(self, situation_nyc: SituationNode):
        result = evaluate_situations((situation_nyc,), {})
        assert len(result.matched_situations) == 0

    def test_multiple_situations_one_matches(
        self,
        situation_nyc: SituationNode,
        situation_california: SituationNode,
    ):
        result = evaluate_situations(
            (situation_nyc, situation_california),
            {"jurisdiction": "NYC"},
        )
        assert len(result.matched_situations) == 1
        assert result.matched_situations[0] is situation_nyc

    def test_multiple_situations_both_match_impossible(
        self,
        situation_nyc: SituationNode,
        situation_no_waiting: SituationNode,
    ):
        """Two different predicates, both satisfied by context."""
        result = evaluate_situations(
            (situation_nyc, situation_no_waiting),
            {"jurisdiction": "NYC", "employee_type": "contractor"},
        )
        assert len(result.matched_situations) == 2
        assert len(result.additional_requires) == 2  # 1 from each situation

    def test_waiting_period_most_restrictive(
        self,
        situation_nyc: SituationNode,
        situation_california: SituationNode,
    ):
        """When both situations have waiting periods, use most restrictive."""
        # Create a context that matches both NYC and CA
        # (unrealistic but tests the logic)
        nyc_pred = PredicateNode(field="region1", operator="==", value="NYC")
        ca_pred = PredicateNode(field="region2", operator="==", value="CA")

        sit_nyc = SituationNode(
            predicate=nyc_pred,
            waiting_period=WaitingPeriodNode(min_value=30, max_value=90, unit="days"),
            requires=(),
        )
        sit_ca = SituationNode(
            predicate=ca_pred,
            waiting_period=WaitingPeriodNode(min_value=60, max_value=120, unit="days"),
            requires=(),
        )

        result = evaluate_situations(
            (sit_nyc, sit_ca),
            {"region1": "NYC", "region2": "CA"},
        )
        assert len(result.matched_situations) == 2
        # CA has longer min (60 > 30), so it should be selected
        assert result.waiting_period_override is not None
        assert result.waiting_period_override.min_value == 60

    def test_waiting_period_none_when_no_override(self, situation_no_waiting: SituationNode):
        """Situation without waiting period does not override."""
        result = evaluate_situations(
            (situation_no_waiting,),
            {"employee_type": "contractor"},
        )
        assert result.waiting_period_override is None
        assert len(result.matched_situations) == 1

    def test_condition_results_populated(
        self,
        situation_nyc: SituationNode,
        situation_california: SituationNode,
    ):
        """condition_results should have one entry per situation."""
        result = evaluate_situations(
            (situation_nyc, situation_california),
            {"jurisdiction": "NYC"},
        )
        assert len(result.condition_results) == 2
        assert result.condition_results[0].matched is True  # NYC matches
        assert result.condition_results[1].matched is False  # CA does not

    def test_result_is_frozen(self, situation_nyc: SituationNode):
        result = evaluate_situations((situation_nyc,), {"jurisdiction": "NYC"})
        assert isinstance(result, SituationOverrides)
        with pytest.raises(AttributeError):
            result.matched_situations = ()  # type: ignore[misc]

    def test_requires_aggregated_from_multiple(self):
        """Multiple matching situations aggregate their requires."""
        sit1 = SituationNode(
            predicate=PredicateNode(field="a", operator="==", value="x"),
            requires=(
                RequireNode(ref=FeatureCallNode(name="feat_a", args=())),
                RequireNode(ref=FeatureCallNode(name="feat_b", args=())),
            ),
        )
        sit2 = SituationNode(
            predicate=PredicateNode(field="b", operator="==", value="y"),
            requires=(RequireNode(ref=FeatureCallNode(name="feat_c", args=())),),
        )

        result = evaluate_situations(
            (sit1, sit2),
            {"a": "x", "b": "y"},
        )
        assert len(result.additional_requires) == 3
        names = [r.ref.name for r in result.additional_requires]
        assert names == ["feat_a", "feat_b", "feat_c"]


# =============================================================================
# Tests: Edge cases and integration
# =============================================================================


class TestEdgeCases:
    """Edge cases and integration scenarios."""

    def test_predicate_with_zero_value(self):
        """Zero should be a valid comparison value."""
        pred = PredicateNode(field="count", operator="==", value=0)
        result = evaluate_predicate(pred, {"count": 0})
        assert result.matched is True

    def test_predicate_with_empty_string(self):
        """Empty string should be a valid comparison value."""
        pred = PredicateNode(field="name", operator="==", value="")
        result = evaluate_predicate(pred, {"name": ""})
        assert result.matched is True

    def test_predicate_with_negative_number(self):
        """Negative numbers should work."""
        pred = PredicateNode(field="offset", operator="<", value=0)
        result = evaluate_predicate(pred, {"offset": -5})
        assert result.matched is True

    def test_when_block_empty_requires(self):
        """When block with no requires/actions/awaits."""
        block = WhenBlockNode(
            predicate=PredicateNode(field="x", operator="==", value="y"),
            requires=(),
            actions=(),
            awaits=(),
        )
        result = evaluate_when_block(block, {"x": "y"})
        assert result.matched is True
        assert len(result.block.requires) == 0
        assert len(result.block.actions) == 0
        assert len(result.block.awaits) == 0

    def test_situation_with_only_waiting_period(self):
        """Situation with waiting period but no requires."""
        sit = SituationNode(
            predicate=PredicateNode(field="state", operator="==", value="TX"),
            waiting_period=WaitingPeriodNode(min_value=15, max_value=30, unit="days"),
            requires=(),
        )
        result = evaluate_situations((sit,), {"state": "TX"})
        assert len(result.matched_situations) == 1
        assert len(result.additional_requires) == 0
        assert result.waiting_period_override is not None
        assert result.waiting_period_override.min_value == 15

    def test_context_with_extra_keys(self, nyc_predicate: PredicateNode):
        """Extra keys in context should not affect evaluation."""
        result = evaluate_predicate(
            nyc_predicate,
            {"jurisdiction": "NYC", "extra_key": "value", "another": 42},
        )
        assert result.matched is True

    def test_case_sensitive_string_comparison(self):
        """String comparisons should be case-sensitive."""
        pred = PredicateNode(field="jurisdiction", operator="==", value="NYC")
        result = evaluate_predicate(pred, {"jurisdiction": "nyc"})
        assert result.matched is False

    def test_multiple_when_blocks_independent(self):
        """Each when_block is evaluated independently."""
        block1 = WhenBlockNode(
            predicate=PredicateNode(field="a", operator="==", value=1),
        )
        block2 = WhenBlockNode(
            predicate=PredicateNode(field="b", operator="==", value=2),
        )
        block3 = WhenBlockNode(
            predicate=PredicateNode(field="c", operator="==", value=3),
        )

        results = evaluate_when_blocks(
            (block1, block2, block3),
            {"a": 1, "b": 99, "c": 3},
        )
        assert results[0].matched is True
        assert results[1].matched is False
        assert results[2].matched is True
