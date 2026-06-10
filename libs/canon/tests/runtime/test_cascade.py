"""Tests for canon.runtime.cascade module.

Tests the phase completion cascade engine: when a phase completes,
evaluate and potentially activate downstream phases.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from canon.runtime.cascade import (
    CascadeResult,
    activate_phase,
    find_downstream_phases,
    is_workflow_complete,
    on_phase_completed,
    on_phase_failed,
)
from canon.runtime.phase_state import InvalidPhaseTransition, PhaseState
from canon.runtime.require_eval import RequireResult

from .conftest import RUN_ID, USER_ID

# ---------------------------------------------------------------------------
# CascadeResult tests
# ---------------------------------------------------------------------------


class TestCascadeResult:
    """Test CascadeResult data class."""

    def test_default_values(self):
        result = CascadeResult()
        assert result.activated_phases == []
        assert result.workflow_complete is False
        assert result.errors == []

    def test_custom_values(self):
        result = CascadeResult(
            activated_phases=["hm_approval", "ceo_approval"],
            workflow_complete=True,
            errors=["some error"],
        )
        assert result.activated_phases == ["hm_approval", "ceo_approval"]
        assert result.workflow_complete is True
        assert result.errors == ["some error"]

    def test_none_args_become_empty_lists(self):
        result = CascadeResult(activated_phases=None, errors=None)
        assert result.activated_phases == []
        assert result.errors == []

    def test_to_dict_serialization(self):
        result = CascadeResult(
            activated_phases=["hm_approval", "ceo_approval"],
            workflow_complete=True,
            errors=["err1"],
        )
        d = result.to_dict()
        assert d["activated_phases"] == ["hm_approval", "ceo_approval"]
        assert d["workflow_complete"] is True
        assert d["errors"] == ["err1"]

    def test_to_dict_errors_none_when_empty(self):
        """Empty errors list serializes as None."""
        result = CascadeResult()
        d = result.to_dict()
        assert d["errors"] is None
        assert d["activated_phases"] == []
        assert d["workflow_complete"] is False

    def test_to_dict_errors_present_when_nonempty(self):
        result = CascadeResult(errors=["failure in gate"])
        d = result.to_dict()
        assert d["errors"] == ["failure in gate"]


# ---------------------------------------------------------------------------
# find_downstream_phases tests (pure AST traversal, minimal mocking)
# ---------------------------------------------------------------------------


class TestFindDownstreamPhases:
    """Test downstream phase discovery from compiled charter AST."""

    @pytest.mark.anyio
    async def test_linear_chain_first_phase(self, three_phase_compiled, mock_conn):
        """Completing initiation -> downstream = [hm_approval]."""
        result = await find_downstream_phases(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            completed_phase="initiation",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )
        assert result == ["hm_approval"]

    @pytest.mark.anyio
    async def test_linear_chain_middle_phase(self, three_phase_compiled, mock_conn):
        """Completing hm_approval -> downstream = [ceo_approval]."""
        result = await find_downstream_phases(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            completed_phase="hm_approval",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )
        assert result == ["ceo_approval"]

    @pytest.mark.anyio
    async def test_terminal_phase_no_downstream(self, three_phase_compiled, mock_conn):
        """Completing ceo_approval -> downstream = [] (no one depends on it)."""
        result = await find_downstream_phases(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            completed_phase="ceo_approval",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )
        assert result == []

    @pytest.mark.anyio
    async def test_diamond_fans_out(self, diamond_compiled, mock_conn):
        """Completing initiation in diamond -> [review_a, review_b]."""
        result = await find_downstream_phases(
            run_id=RUN_ID,
            workflow_name="diamond_workflow",
            completed_phase="initiation",
            compiled=diamond_compiled,
            conn=mock_conn,
        )
        assert set(result) == {"review_a", "review_b"}

    @pytest.mark.anyio
    async def test_diamond_branch_converges(self, diamond_compiled, mock_conn):
        """Completing review_a in diamond -> [final]."""
        result = await find_downstream_phases(
            run_id=RUN_ID,
            workflow_name="diamond_workflow",
            completed_phase="review_a",
            compiled=diamond_compiled,
            conn=mock_conn,
        )
        assert result == ["final"]

    @pytest.mark.anyio
    async def test_diamond_terminal_no_downstream(self, diamond_compiled, mock_conn):
        """Completing final in diamond -> [] (terminal)."""
        result = await find_downstream_phases(
            run_id=RUN_ID,
            workflow_name="diamond_workflow",
            completed_phase="final",
            compiled=diamond_compiled,
            conn=mock_conn,
        )
        assert result == []

    @pytest.mark.anyio
    async def test_unknown_workflow_returns_empty(self, three_phase_compiled, mock_conn):
        """Unknown workflow -> empty list."""
        result = await find_downstream_phases(
            run_id=RUN_ID,
            workflow_name="nonexistent_workflow",
            completed_phase="initiation",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )
        assert result == []

    @pytest.mark.anyio
    async def test_unknown_phase_returns_empty(self, three_phase_compiled, mock_conn):
        """Phase that no one depends on -> empty list."""
        result = await find_downstream_phases(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            completed_phase="nonexistent_phase",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )
        assert result == []


# ---------------------------------------------------------------------------
# activate_phase tests (mock select_one, update)
# ---------------------------------------------------------------------------


class TestActivatePhase:
    """Test phase activation logic."""

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_pending_to_waiting_user(
        self, mock_select_one, mock_update, three_phase_compiled, mock_conn
    ):
        """Phase in PENDING -> transitions to WAITING_USER -> returns True."""
        mock_select_one.return_value = {"status": "pending"}

        result = await activate_phase(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is True
        mock_update.assert_called_once()
        _, kwargs = mock_update.call_args
        assert kwargs["data"]["status"] == "waiting_user"
        assert "activated_at" in kwargs["data"]

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_already_waiting_user_returns_false(
        self, mock_select_one, mock_update, three_phase_compiled, mock_conn
    ):
        """Phase already WAITING_USER -> returns False (skip)."""
        mock_select_one.return_value = {"status": "waiting_user"}

        result = await activate_phase(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is False
        mock_update.assert_not_called()

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_already_completed_returns_false(
        self, mock_select_one, mock_update, three_phase_compiled, mock_conn
    ):
        """Phase already COMPLETED -> returns False (skip)."""
        mock_select_one.return_value = {"status": "completed"}

        result = await activate_phase(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is False
        mock_update.assert_not_called()

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_already_failed_returns_false(
        self, mock_select_one, mock_update, three_phase_compiled, mock_conn
    ):
        """Phase already FAILED -> returns False (skip)."""
        mock_select_one.return_value = {"status": "failed"}

        result = await activate_phase(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is False
        mock_update.assert_not_called()

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_already_in_progress_returns_false(
        self, mock_select_one, mock_update, three_phase_compiled, mock_conn
    ):
        """Phase already IN_PROGRESS -> returns False (skip)."""
        mock_select_one.return_value = {"status": "in_progress"}

        result = await activate_phase(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is False
        mock_update.assert_not_called()

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_phase_not_found_raises_value_error(
        self, mock_select_one, three_phase_compiled, mock_conn
    ):
        """Phase not found -> raises ValueError."""
        mock_select_one.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await activate_phase(
                run_id=RUN_ID,
                workflow_name="approval_workflow",
                phase_name="nonexistent",
                compiled=three_phase_compiled,
                conn=mock_conn,
            )


# ---------------------------------------------------------------------------
# on_phase_completed tests (mock select_one, update, fetch, evaluate_requires)
# ---------------------------------------------------------------------------


class TestOnPhaseCompleted:
    """Test the main cascade entry point for phase completion."""

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.fetch", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.evaluate_requires", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_complete_first_phase_activates_downstream(
        self,
        mock_select_one,
        mock_update,
        mock_evaluate,
        mock_fetch,
        three_phase_compiled,
        mock_conn,
    ):
        """Complete initiation -> activates hm_approval."""
        # 1st select_one: get initiation phase (in_progress -> can complete)
        # 2nd select_one: get hm_approval phase (pending -> can activate)
        mock_select_one.side_effect = [
            {"status": "in_progress"},  # initiation lookup
            {"status": "pending"},  # hm_approval lookup in activate_phase
        ]
        mock_evaluate.return_value = RequireResult(satisfied=True, unsatisfied=())
        # Not all terminal -> workflow not complete
        mock_fetch.return_value = [
            {"phase_name": "initiation", "status": "completed"},
            {"phase_name": "hm_approval", "status": "waiting_user"},
            {"phase_name": "ceo_approval", "status": "pending"},
        ]

        result = await on_phase_completed(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="initiation",
            action_by_id=USER_ID,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert "hm_approval" in result.activated_phases
        assert result.workflow_complete is False
        assert result.errors == []
        # evaluate_requires called once for hm_approval
        mock_evaluate.assert_called_once()

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_phase_not_found_returns_error(
        self, mock_select_one, three_phase_compiled, mock_conn
    ):
        """Phase not found -> returns result with error, no exception."""
        mock_select_one.return_value = None

        result = await on_phase_completed(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="nonexistent",
            action_by_id=USER_ID,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert len(result.errors) == 1
        assert "not found" in result.errors[0]
        assert result.activated_phases == []
        assert result.workflow_complete is False

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_invalid_transition_from_pending_raises(
        self, mock_select_one, three_phase_compiled, mock_conn
    ):
        """Phase in PENDING cannot transition to COMPLETED -> raises."""
        mock_select_one.return_value = {"status": "pending"}

        with pytest.raises(InvalidPhaseTransition) as exc_info:
            await on_phase_completed(
                run_id=RUN_ID,
                workflow_name="approval_workflow",
                phase_name="initiation",
                action_by_id=USER_ID,
                compiled=three_phase_compiled,
                conn=mock_conn,
            )

        assert exc_info.value.from_state == "pending"
        assert exc_info.value.to_state == "completed"

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_invalid_transition_from_completed_raises(
        self, mock_select_one, three_phase_compiled, mock_conn
    ):
        """Phase already COMPLETED cannot transition to COMPLETED again."""
        mock_select_one.return_value = {"status": "completed"}

        with pytest.raises(InvalidPhaseTransition) as exc_info:
            await on_phase_completed(
                run_id=RUN_ID,
                workflow_name="approval_workflow",
                phase_name="initiation",
                action_by_id=USER_ID,
                compiled=three_phase_compiled,
                conn=mock_conn,
            )

        assert exc_info.value.from_state == "completed"
        assert exc_info.value.to_state == "completed"

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.fetch", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_workflow_complete_after_final_phase(
        self,
        mock_select_one,
        mock_update,
        mock_fetch,
        three_phase_compiled,
        mock_conn,
    ):
        """Complete ceo_approval (terminal) -> workflow_complete=True."""
        # Only one select_one call (for ceo_approval itself)
        # No downstream phases, so no activation select_one calls
        mock_select_one.return_value = {"status": "in_progress"}
        mock_fetch.return_value = [
            {"phase_name": "initiation", "status": "completed"},
            {"phase_name": "hm_approval", "status": "completed"},
            {"phase_name": "ceo_approval", "status": "completed"},
        ]

        result = await on_phase_completed(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="ceo_approval",
            action_by_id=USER_ID,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result.workflow_complete is True
        assert result.activated_phases == []
        assert result.errors == []
        # update calls: mark phase completed + update current_phase + complete run
        assert mock_update.call_count == 3

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.fetch", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.evaluate_requires", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_downstream_requires_not_satisfied_skips_activation(
        self,
        mock_select_one,
        mock_update,
        mock_evaluate,
        mock_fetch,
        diamond_compiled,
        mock_conn,
    ):
        """In diamond, completing review_a -> final not activated (review_b still needed)."""
        mock_select_one.return_value = {"status": "in_progress"}
        # evaluate_requires for 'final' says not satisfied (review_b still pending)
        mock_evaluate.return_value = RequireResult(
            satisfied=False,
            unsatisfied=("review_b.passed",),
        )
        mock_fetch.return_value = [
            {"phase_name": "initiation", "status": "completed"},
            {"phase_name": "review_a", "status": "completed"},
            {"phase_name": "review_b", "status": "waiting_user"},
            {"phase_name": "final", "status": "pending"},
        ]

        result = await on_phase_completed(
            run_id=RUN_ID,
            workflow_name="diamond_workflow",
            phase_name="review_a",
            action_by_id=USER_ID,
            compiled=diamond_compiled,
            conn=mock_conn,
        )

        # final was not activated because review_b is not done
        assert result.activated_phases == []
        assert result.workflow_complete is False

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_unknown_status_returns_error(
        self, mock_select_one, three_phase_compiled, mock_conn
    ):
        """Unknown status string -> returns result with error."""
        mock_select_one.return_value = {"status": "bogus_status"}

        result = await on_phase_completed(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="initiation",
            action_by_id=USER_ID,
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert len(result.errors) == 1
        assert "Unknown phase status" in result.errors[0]

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.fetch", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.evaluate_requires", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_action_notes_and_action_taken_forwarded(
        self,
        mock_select_one,
        mock_update,
        mock_evaluate,
        mock_fetch,
        three_phase_compiled,
        mock_conn,
    ):
        """Optional action_notes and action_taken are passed to the update."""
        mock_select_one.side_effect = [
            {"status": "in_progress"},
            {"status": "pending"},
        ]
        mock_evaluate.return_value = RequireResult(satisfied=True, unsatisfied=())
        mock_fetch.return_value = [
            {"phase_name": "initiation", "status": "completed"},
            {"phase_name": "hm_approval", "status": "waiting_user"},
            {"phase_name": "ceo_approval", "status": "pending"},
        ]

        await on_phase_completed(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="initiation",
            action_by_id=USER_ID,
            compiled=three_phase_compiled,
            conn=mock_conn,
            action_notes="Looks good",
            action_taken="approve",
        )

        # First update call marks the phase as completed with notes
        first_update_kwargs = mock_update.call_args_list[0][1]
        assert first_update_kwargs["data"]["action_notes"] == "Looks good"
        assert first_update_kwargs["data"]["action_taken"] == "approve"
        assert first_update_kwargs["data"]["action_by_id"] == USER_ID


# ---------------------------------------------------------------------------
# on_phase_failed tests (mock select_one, update)
# ---------------------------------------------------------------------------


class TestOnPhaseFailed:
    """Test phase failure handling."""

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_fail_in_progress_phase(self, mock_select_one, mock_update, mock_conn):
        """Fail an in-progress phase -> marks phase failed + run failed."""
        mock_select_one.return_value = {"status": "in_progress"}

        result = await on_phase_failed(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            action_by_id=USER_ID,
            conn=mock_conn,
            failure_reason="Rejected by manager",
        )

        assert result.activated_phases == []
        assert result.errors == []
        assert result.workflow_complete is False
        # update called twice: phase_executions + charter_runs
        assert mock_update.call_count == 2

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.update", new_callable=AsyncMock)
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_fail_marks_phase_with_correct_data(
        self, mock_select_one, mock_update, mock_conn
    ):
        """Verify the phase update data includes failure details."""
        mock_select_one.return_value = {"status": "in_progress"}

        await on_phase_failed(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            action_by_id=USER_ID,
            conn=mock_conn,
            failure_reason="Gate check failed",
            failed_gate="verify_consent",
        )

        # First update: phase_executions
        phase_update_kwargs = mock_update.call_args_list[0][1]
        assert phase_update_kwargs["data"]["status"] == PhaseState.FAILED.value
        assert phase_update_kwargs["data"]["failure_reason"] == "Gate check failed"
        assert phase_update_kwargs["data"]["failed_gate"] == "verify_consent"
        assert phase_update_kwargs["data"]["action_by_id"] == USER_ID

        # Second update: charter_runs
        run_update_kwargs = mock_update.call_args_list[1][1]
        assert run_update_kwargs["data"]["status"] == "failed"
        assert run_update_kwargs["data"]["failure_reason"] == "Gate check failed"
        assert run_update_kwargs["data"]["final_outcome"] == "failed"

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_phase_not_found_returns_error(self, mock_select_one, mock_conn):
        """Phase not found -> error in result, no exception."""
        mock_select_one.return_value = None

        result = await on_phase_failed(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="nonexistent",
            action_by_id=USER_ID,
            conn=mock_conn,
        )

        assert len(result.errors) == 1
        assert "not found" in result.errors[0]
        assert result.activated_phases == []

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_invalid_transition_from_completed_raises(self, mock_select_one, mock_conn):
        """Phase in COMPLETED -> FAILED is invalid, raises InvalidPhaseTransition."""
        mock_select_one.return_value = {"status": "completed"}

        with pytest.raises(InvalidPhaseTransition) as exc_info:
            await on_phase_failed(
                run_id=RUN_ID,
                workflow_name="approval_workflow",
                phase_name="hm_approval",
                action_by_id=USER_ID,
                conn=mock_conn,
            )

        assert exc_info.value.from_state == "completed"
        assert exc_info.value.to_state == "failed"

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_invalid_transition_from_pending_raises(self, mock_select_one, mock_conn):
        """Phase in PENDING -> FAILED is invalid, raises InvalidPhaseTransition."""
        mock_select_one.return_value = {"status": "pending"}

        with pytest.raises(InvalidPhaseTransition) as exc_info:
            await on_phase_failed(
                run_id=RUN_ID,
                workflow_name="approval_workflow",
                phase_name="hm_approval",
                action_by_id=USER_ID,
                conn=mock_conn,
            )

        assert exc_info.value.from_state == "pending"
        assert exc_info.value.to_state == "failed"

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.select_one", new_callable=AsyncMock)
    async def test_unknown_status_returns_error(self, mock_select_one, mock_conn):
        """Unknown status string -> returns result with error."""
        mock_select_one.return_value = {"status": "bogus_status"}

        result = await on_phase_failed(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            phase_name="hm_approval",
            action_by_id=USER_ID,
            conn=mock_conn,
        )

        assert len(result.errors) == 1
        assert "Unknown phase status" in result.errors[0]


# ---------------------------------------------------------------------------
# is_workflow_complete tests (mock fetch)
# ---------------------------------------------------------------------------


class TestIsWorkflowComplete:
    """Test workflow completion check."""

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.fetch", new_callable=AsyncMock)
    async def test_all_phases_completed(self, mock_fetch, three_phase_compiled, mock_conn):
        """All phases completed -> True."""
        mock_fetch.return_value = [
            {"phase_name": "initiation", "status": "completed"},
            {"phase_name": "hm_approval", "status": "completed"},
            {"phase_name": "ceo_approval", "status": "completed"},
        ]

        result = await is_workflow_complete(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is True

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.fetch", new_callable=AsyncMock)
    async def test_mixed_terminal_states_is_complete(
        self, mock_fetch, three_phase_compiled, mock_conn
    ):
        """Mix of completed, skipped, failed (all terminal) -> True."""
        mock_fetch.return_value = [
            {"phase_name": "initiation", "status": "completed"},
            {"phase_name": "hm_approval", "status": "skipped"},
            {"phase_name": "ceo_approval", "status": "failed"},
        ]

        result = await is_workflow_complete(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is True

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.fetch", new_callable=AsyncMock)
    async def test_some_phases_pending(self, mock_fetch, three_phase_compiled, mock_conn):
        """Some phases pending -> False."""
        mock_fetch.return_value = [
            {"phase_name": "initiation", "status": "completed"},
            {"phase_name": "hm_approval", "status": "waiting_user"},
            {"phase_name": "ceo_approval", "status": "pending"},
        ]

        result = await is_workflow_complete(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is False

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.fetch", new_callable=AsyncMock)
    async def test_single_non_terminal_phase(self, mock_fetch, three_phase_compiled, mock_conn):
        """One phase in_progress among completed -> False."""
        mock_fetch.return_value = [
            {"phase_name": "initiation", "status": "completed"},
            {"phase_name": "hm_approval", "status": "in_progress"},
            {"phase_name": "ceo_approval", "status": "completed"},
        ]

        result = await is_workflow_complete(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is False

    @pytest.mark.anyio
    @patch("canon.runtime.cascade.fetch", new_callable=AsyncMock)
    async def test_empty_phases_returns_false(self, mock_fetch, three_phase_compiled, mock_conn):
        """No phase execution rows -> False."""
        mock_fetch.return_value = []

        result = await is_workflow_complete(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            compiled=three_phase_compiled,
            conn=mock_conn,
        )

        assert result is False
