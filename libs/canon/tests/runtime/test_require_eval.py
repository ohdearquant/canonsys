"""Tests for canon.runtime.require_eval module.

Covers:
- RequireResult frozen dataclass creation and defaults
- evaluate_single_require dispatch for all ref types
- evaluate_requires aggregation, phase lookup, and edge cases
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, patch

import pytest

from canon.dsl.ast import (
    ArgNode,
    AwaitRefNode,
    BuiltinRefNode,
    FeatureCallNode,
    PhaseRefNode,
    RequireNode,
)
from canon.runtime.require_eval import (
    RequireResult,
    evaluate_requires,
    evaluate_single_require,
)

from .conftest import RUN_ID

# ---------------------------------------------------------------------------
# RequireResult dataclass
# ---------------------------------------------------------------------------


class TestRequireResult:
    """RequireResult construction and frozen semantics."""

    def test_create_satisfied(self):
        result = RequireResult(satisfied=True, unsatisfied=())
        assert result.satisfied is True
        assert result.unsatisfied == ()
        assert result.details == {}

    def test_create_unsatisfied(self):
        result = RequireResult(
            satisfied=False,
            unsatisfied=("initiation.passed",),
            details={"initiation.passed": {"satisfied": False, "reason": "pending"}},
        )
        assert result.satisfied is False
        assert result.unsatisfied == ("initiation.passed",)
        assert "initiation.passed" in result.details

    def test_default_details_is_empty_dict(self):
        result = RequireResult(satisfied=True, unsatisfied=())
        assert result.details == {}
        assert isinstance(result.details, dict)

    def test_explicit_none_details_becomes_empty_dict(self):
        result = RequireResult(satisfied=True, unsatisfied=(), details=None)
        assert result.details == {}

    def test_frozen_cannot_set_satisfied(self):
        result = RequireResult(satisfied=True, unsatisfied=())
        with pytest.raises(FrozenInstanceError):
            result.satisfied = False  # type: ignore[misc]

    def test_frozen_cannot_set_unsatisfied(self):
        result = RequireResult(satisfied=True, unsatisfied=())
        with pytest.raises(FrozenInstanceError):
            result.unsatisfied = ("x",)  # type: ignore[misc]

    def test_frozen_cannot_set_details(self):
        result = RequireResult(satisfied=True, unsatisfied=(), details={})
        with pytest.raises(FrozenInstanceError):
            result.details = {"a": {}}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# evaluate_single_require - PhaseRefNode
# ---------------------------------------------------------------------------


class TestEvaluateSingleRequirePhaseRef:
    """PhaseRefNode evaluation queries phase_executions and checks status."""

    @pytest.mark.anyio
    @patch(
        "canon.runtime.require_eval.select_one",
        new_callable=AsyncMock,
    )
    async def test_phase_completed_is_satisfied(
        self, mock_select_one, three_phase_compiled, mock_conn
    ):
        mock_select_one.return_value = {"status": "completed"}

        req = RequireNode(ref=PhaseRefNode(phase="initiation", condition="passed"))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is True
        assert result["expr"] == "initiation.passed"
        assert result["reason"] is None
        assert result["actual_status"] == "completed"

        mock_select_one.assert_awaited_once()
        call_kwargs = mock_select_one.call_args
        assert call_kwargs[1]["where"]["run_id"] == RUN_ID
        assert call_kwargs[1]["where"]["phase_name"] == "initiation"

    @pytest.mark.anyio
    @patch(
        "canon.runtime.require_eval.select_one",
        new_callable=AsyncMock,
    )
    async def test_phase_pending_is_unsatisfied(
        self, mock_select_one, three_phase_compiled, mock_conn
    ):
        mock_select_one.return_value = {"status": "pending"}

        req = RequireNode(ref=PhaseRefNode(phase="initiation", condition="passed"))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert result["expr"] == "initiation.passed"
        assert "pending" in result["reason"]
        assert result["actual_status"] == "pending"

    @pytest.mark.anyio
    @patch(
        "canon.runtime.require_eval.select_one",
        new_callable=AsyncMock,
    )
    async def test_phase_not_found_is_unsatisfied(
        self, mock_select_one, three_phase_compiled, mock_conn
    ):
        mock_select_one.return_value = None

        req = RequireNode(ref=PhaseRefNode(phase="initiation", condition="passed"))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert "not found" in result["reason"]

    @pytest.mark.anyio
    @patch(
        "canon.runtime.require_eval.select_one",
        new_callable=AsyncMock,
    )
    async def test_phase_complete_condition_alias(
        self, mock_select_one, three_phase_compiled, mock_conn
    ):
        """condition='complete' is an alias for 'passed' -- both check 'completed'."""
        mock_select_one.return_value = {"status": "completed"}

        req = RequireNode(ref=PhaseRefNode(phase="initiation", condition="complete"))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is True
        assert result["expr"] == "initiation.complete"

    @pytest.mark.anyio
    async def test_unknown_condition_is_unsatisfied(self, three_phase_compiled, mock_conn):
        """An unrecognized condition (not 'passed' or 'complete') fails safe."""
        req = RequireNode(ref=PhaseRefNode(phase="initiation", condition="failed"))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert "Unknown phase condition" in result["reason"]
        assert result["expr"] == "initiation.failed"


# ---------------------------------------------------------------------------
# evaluate_single_require - FeatureCallNode
# ---------------------------------------------------------------------------


class TestEvaluateSingleRequireFeatureCall:
    """FeatureCallNode returns unsatisfied (not yet implemented)."""

    @pytest.mark.anyio
    async def test_feature_call_no_args(self, three_phase_compiled, mock_conn):
        req = RequireNode(ref=FeatureCallNode(name="verify_consent", args=()))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert result["expr"] == "verify_consent()"
        assert "not yet implemented" in result["reason"]
        assert result["feature_name"] == "verify_consent"

    @pytest.mark.anyio
    async def test_feature_call_with_positional_arg(self, three_phase_compiled, mock_conn):
        req = RequireNode(
            ref=FeatureCallNode(
                name="verify_consent",
                args=(ArgNode(name=None, value="background_check"),),
            )
        )
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert result["expr"] == "verify_consent('background_check')"

    @pytest.mark.anyio
    async def test_feature_call_with_keyword_arg(self, three_phase_compiled, mock_conn):
        req = RequireNode(
            ref=FeatureCallNode(
                name="verify_consent",
                args=(ArgNode(name="scope", value="background_check"),),
            )
        )
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert result["expr"] == "verify_consent(scope='background_check')"


# ---------------------------------------------------------------------------
# evaluate_single_require - BuiltinRefNode
# ---------------------------------------------------------------------------


class TestEvaluateSingleRequireBuiltinRef:
    """BuiltinRefNode returns unsatisfied (not yet implemented)."""

    @pytest.mark.anyio
    async def test_all_phases_passed(self, three_phase_compiled, mock_conn):
        req = RequireNode(ref=BuiltinRefNode(name="all_phases_passed"))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert result["expr"] == "all_phases_passed"
        assert "not yet implemented" in result["reason"]

    @pytest.mark.anyio
    async def test_any_phase_failed(self, three_phase_compiled, mock_conn):
        req = RequireNode(ref=BuiltinRefNode(name="any_phase_failed"))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert result["expr"] == "any_phase_failed"
        assert "not yet implemented" in result["reason"]

    @pytest.mark.anyio
    async def test_unknown_builtin(self, three_phase_compiled, mock_conn):
        req = RequireNode(ref=BuiltinRefNode(name="nonexistent_predicate"))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert "Unknown builtin predicate" in result["reason"]


# ---------------------------------------------------------------------------
# evaluate_single_require - AwaitRefNode
# ---------------------------------------------------------------------------


class TestEvaluateSingleRequireAwaitRef:
    """AwaitRefNode returns unsatisfied (not yet implemented)."""

    @pytest.mark.anyio
    async def test_await_ref(self, three_phase_compiled, mock_conn):
        req = RequireNode(ref=AwaitRefNode(trigger="candidate_files_dispute"))
        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert result["expr"] == "await candidate_files_dispute"
        assert "not been fired" in result["reason"] or "not yet implemented" in result["reason"]
        assert result["trigger_name"] == "candidate_files_dispute"


# ---------------------------------------------------------------------------
# evaluate_single_require - Unknown ref type
# ---------------------------------------------------------------------------


class TestEvaluateSingleRequireUnknownRef:
    """Unknown ref types fail safe with unsatisfied."""

    @pytest.mark.anyio
    async def test_unknown_ref_type(self, three_phase_compiled, mock_conn):
        # Fabricate a RequireNode with a non-standard ref object
        fake_ref = object()
        req = RequireNode.__new__(RequireNode)
        object.__setattr__(req, "ref", fake_ref)

        result = await evaluate_single_require(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            require_node=req,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result["satisfied"] is False
        assert "Unknown require type" in result["reason"]


# ---------------------------------------------------------------------------
# evaluate_requires - aggregation
# ---------------------------------------------------------------------------


class TestEvaluateRequires:
    """evaluate_requires aggregates single-require results for a phase."""

    @pytest.mark.anyio
    @patch(
        "canon.runtime.require_eval.select_one",
        new_callable=AsyncMock,
    )
    async def test_all_satisfied(self, mock_select_one, three_phase_compiled, mock_conn):
        """hm_approval requires initiation.passed -- if completed, result is satisfied."""
        mock_select_one.return_value = {"status": "completed"}

        result = await evaluate_requires(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result.satisfied is True
        assert result.unsatisfied == ()
        assert "initiation.passed" in result.details
        assert result.details["initiation.passed"]["satisfied"] is True

    @pytest.mark.anyio
    @patch(
        "canon.runtime.require_eval.select_one",
        new_callable=AsyncMock,
    )
    async def test_unsatisfied(self, mock_select_one, three_phase_compiled, mock_conn):
        """hm_approval requires initiation.passed -- if pending, result is unsatisfied."""
        mock_select_one.return_value = {"status": "pending"}

        result = await evaluate_requires(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result.satisfied is False
        assert "initiation.passed" in result.unsatisfied

    @pytest.mark.anyio
    @patch(
        "canon.runtime.require_eval.select_one",
        new_callable=AsyncMock,
    )
    async def test_diamond_partially_unsatisfied(
        self, mock_select_one, diamond_compiled, mock_conn
    ):
        """final requires review_a.passed AND review_b.passed.
        Only review_a is completed -> partially unsatisfied.
        """

        async def _select_one_side_effect(table, *, where, conn, tenant_scope):
            phase = where["phase_name"]
            if phase == "review_a":
                return {"status": "completed"}
            if phase == "review_b":
                return {"status": "pending"}
            return None

        mock_select_one.side_effect = _select_one_side_effect

        result = await evaluate_requires(
            run_id=RUN_ID,
            workflow_name="diamond_workflow",
            phase_name="final",
            compiled=diamond_compiled,
            conn=mock_conn,
        )

        assert result.satisfied is False
        assert "review_b.passed" in result.unsatisfied
        assert "review_a.passed" not in result.unsatisfied
        # Both should appear in details
        assert "review_a.passed" in result.details
        assert "review_b.passed" in result.details

    @pytest.mark.anyio
    @patch(
        "canon.runtime.require_eval.select_one",
        new_callable=AsyncMock,
    )
    async def test_diamond_all_satisfied(self, mock_select_one, diamond_compiled, mock_conn):
        """final requires review_a.passed AND review_b.passed -- both completed."""
        mock_select_one.return_value = {"status": "completed"}

        result = await evaluate_requires(
            run_id=RUN_ID,
            workflow_name="diamond_workflow",
            phase_name="final",
            compiled=diamond_compiled,
            conn=mock_conn,
        )

        assert result.satisfied is True
        assert result.unsatisfied == ()

    @pytest.mark.anyio
    async def test_phase_not_found_raises_value_error(self, three_phase_compiled, mock_conn):
        with pytest.raises(ValueError, match="Phase 'nonexistent' not found"):
            await evaluate_requires(
                run_id=RUN_ID,
                workflow_name="approval_workflow",
                phase_name="nonexistent",
                compiled=three_phase_compiled,
                conn=mock_conn,
            )

    @pytest.mark.anyio
    async def test_workflow_not_found_raises_value_error(self, three_phase_compiled, mock_conn):
        with pytest.raises(ValueError, match="not found"):
            await evaluate_requires(
                run_id=RUN_ID,
                workflow_name="nonexistent_workflow",
                phase_name="initiation",
                compiled=three_phase_compiled,
                conn=mock_conn,
            )

    @pytest.mark.anyio
    async def test_no_requires_is_satisfied(self, three_phase_compiled, mock_conn):
        """initiation has no requires -> automatically satisfied."""
        result = await evaluate_requires(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="initiation",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result.satisfied is True
        assert result.unsatisfied == ()
        assert result.details == {}
