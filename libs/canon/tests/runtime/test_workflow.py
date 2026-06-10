"""Tests for canon.runtime.workflow module.

Tests the workflow lifecycle operations:
- start_workflow: create CharterRun + PhaseExecutions, activate entry phases
- complete_charter_run: mark runs as completed/failed/cancelled
- cancel_charter_run: skip non-terminal phases and cancel
- get_run_status: retrieve run status with phase counts
- is_workflow_complete: check if all phases are terminal

Also tests pure helper functions:
- _get_requires_phases: extract phase names from RequireNode tuples
- _get_entry_phases: find phases with no dependencies
- _get_phase_role: match phase to role from compiled charter
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

import pytest

from canon.dsl.ast import BuiltinRefNode, FeatureCallNode, PhaseRefNode, RequireNode
from canon.entities.charter import CharterRunStatus, PhaseStatus
from canon.runtime.workflow import (
    WorkflowAlreadyActiveError,
    WorkflowNotFoundError,
    _get_entry_phases,
    _get_phase_role,
    _get_requires_phases,
    cancel_charter_run,
    complete_charter_run,
    get_run_status,
    is_workflow_complete,
    start_workflow,
)

from .conftest import (
    CHARTER_ID,
    OFFER_ID,
    RUN_ID,
    SUBJECT_ID,
    TENANT_ID,
    USER_ID,
    _make_require_phase,
)

# ---------------------------------------------------------------------------
# WorkflowNotFoundError
# ---------------------------------------------------------------------------


class TestWorkflowNotFoundError:
    """Test WorkflowNotFoundError exception."""

    def test_message_includes_workflow_and_charter_name(self):
        err = WorkflowNotFoundError("my_workflow", "My Charter")
        assert "my_workflow" in str(err)
        assert "My Charter" in str(err)

    def test_attributes_stored_correctly(self):
        err = WorkflowNotFoundError("approval_flow", "Hiring Charter")
        assert err.workflow_name == "approval_flow"
        assert err.charter_name == "Hiring Charter"

    def test_is_exception(self):
        err = WorkflowNotFoundError("wf", "ch")
        assert isinstance(err, Exception)

    def test_message_format(self):
        err = WorkflowNotFoundError("pip_workflow", "PIP Charter v1.0")
        assert str(err) == "Workflow 'pip_workflow' not found in charter 'PIP Charter v1.0'"


# ---------------------------------------------------------------------------
# WorkflowAlreadyActiveError
# ---------------------------------------------------------------------------


class TestWorkflowAlreadyActiveError:
    """Test WorkflowAlreadyActiveError exception."""

    def test_message_includes_run_id(self):
        err = WorkflowAlreadyActiveError(RUN_ID)
        assert str(RUN_ID) in str(err)

    def test_attribute_stored_correctly(self):
        err = WorkflowAlreadyActiveError(RUN_ID)
        assert err.run_id == RUN_ID

    def test_is_exception(self):
        err = WorkflowAlreadyActiveError(RUN_ID)
        assert isinstance(err, Exception)

    def test_message_format(self):
        err = WorkflowAlreadyActiveError(RUN_ID)
        assert str(err) == f"Workflow already active: {RUN_ID}"


# ---------------------------------------------------------------------------
# _get_requires_phases (pure logic)
# ---------------------------------------------------------------------------


class TestGetRequiresPhases:
    """Test _get_requires_phases helper - extracts phase names from require nodes."""

    def test_extracts_phase_names_from_phase_ref_nodes(self):
        requires = (
            RequireNode(ref=PhaseRefNode(phase="initiation", condition="passed")),
            RequireNode(ref=PhaseRefNode(phase="review", condition="passed")),
        )
        result = _get_requires_phases(requires)
        assert result == ["initiation", "review"]

    def test_ignores_non_phase_ref_nodes(self):
        """FeatureCallNode and BuiltinRefNode requires are not phase dependencies."""
        requires = (
            RequireNode(ref=FeatureCallNode(name="verify_consent", args=())),
            RequireNode(ref=PhaseRefNode(phase="initiation", condition="passed")),
            RequireNode(ref=BuiltinRefNode(name="all_phases_passed")),
        )
        result = _get_requires_phases(requires)
        assert result == ["initiation"]

    def test_returns_empty_list_for_no_requires(self):
        result = _get_requires_phases(())
        assert result == []

    def test_returns_empty_list_for_only_feature_call_requires(self):
        requires = (RequireNode(ref=FeatureCallNode(name="check_consent", args=())),)
        result = _get_requires_phases(requires)
        assert result == []

    def test_single_phase_dependency(self):
        requires = (_make_require_phase("hm_approval"),)
        result = _get_requires_phases(requires)
        assert result == ["hm_approval"]


# ---------------------------------------------------------------------------
# _get_entry_phases (pure logic, uses compiled fixtures)
# ---------------------------------------------------------------------------


class TestGetEntryPhases:
    """Test _get_entry_phases - finds phases with no dependencies."""

    def test_linear_chain_only_first_is_entry(self, three_phase_compiled):
        """In initiation -> hm_approval -> ceo_approval, only initiation is entry."""
        result = _get_entry_phases(three_phase_compiled, "approval_workflow")
        assert result == ["initiation"]

    def test_diamond_only_initiation_is_entry(self, diamond_compiled):
        """In diamond: initiation -> [review_a, review_b] -> final,
        only initiation has no requires."""
        result = _get_entry_phases(diamond_compiled, "diamond_workflow")
        assert result == ["initiation"]

    def test_unknown_workflow_returns_empty(self, three_phase_compiled):
        result = _get_entry_phases(three_phase_compiled, "nonexistent_workflow")
        assert result == []


# ---------------------------------------------------------------------------
# _get_phase_role (pure logic, uses compiled fixtures)
# ---------------------------------------------------------------------------


class TestGetPhaseRole:
    """Test _get_phase_role - match phase to role from compiled charter."""

    def test_phase_with_matching_role_returns_role_name(self, three_phase_compiled):
        """initiation has action do_initiation, which is in hiring_manager role."""
        result = _get_phase_role(three_phase_compiled, "approval_workflow", "initiation")
        assert result == "hiring_manager"

    def test_hm_approval_returns_hiring_manager(self, three_phase_compiled):
        """hm_approval has action do_hm_approval, also in hiring_manager role."""
        result = _get_phase_role(three_phase_compiled, "approval_workflow", "hm_approval")
        assert result == "hiring_manager"

    def test_ceo_approval_returns_ceo(self, three_phase_compiled):
        """ceo_approval has action do_ceo_approval, which is in ceo role."""
        result = _get_phase_role(three_phase_compiled, "approval_workflow", "ceo_approval")
        assert result == "ceo"

    def test_phase_with_no_matching_role_returns_none(self, diamond_compiled):
        """Diamond charter has no roles defined, so all phases return None."""
        result = _get_phase_role(diamond_compiled, "diamond_workflow", "initiation")
        assert result is None

    def test_unknown_phase_returns_none(self, three_phase_compiled):
        """A nonexistent phase has no actions, so no role match."""
        result = _get_phase_role(three_phase_compiled, "approval_workflow", "nonexistent_phase")
        assert result is None

    def test_unknown_workflow_returns_none(self, three_phase_compiled):
        result = _get_phase_role(three_phase_compiled, "nonexistent_workflow", "initiation")
        assert result is None


# ---------------------------------------------------------------------------
# start_workflow (async, mock get_compiled_charter + mock_conn)
# ---------------------------------------------------------------------------


class TestStartWorkflow:
    """Test start_workflow - creates CharterRun and PhaseExecutions."""

    @pytest.mark.anyio
    async def test_returns_uuid(self, three_phase_compiled, mock_conn):
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=three_phase_compiled,
        ):
            run_id = await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="approval_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        assert isinstance(run_id, UUID)

    @pytest.mark.anyio
    async def test_creates_charter_run_via_execute(self, three_phase_compiled, mock_conn):
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=three_phase_compiled,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="approval_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        # First execute call is the CharterRun INSERT
        first_call = mock_conn.execute.call_args_list[0]
        sql = first_call[0][0]
        assert "INSERT INTO charter_runs" in sql

    @pytest.mark.anyio
    async def test_creates_phase_executions_for_all_phases(self, three_phase_compiled, mock_conn):
        """Three phases in workflow -> 3 PhaseExecution INSERTs."""
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=three_phase_compiled,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="approval_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        # Count INSERT INTO phase_executions calls
        phase_inserts = [
            c for c in mock_conn.execute.call_args_list if "INSERT INTO phase_executions" in c[0][0]
        ]
        assert len(phase_inserts) == 3

    @pytest.mark.anyio
    async def test_activates_entry_phases_to_waiting_user(self, three_phase_compiled, mock_conn):
        """Entry phase (initiation) should be UPDATEd to WAITING_USER."""
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=three_phase_compiled,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="approval_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        # Look for UPDATE phase_executions SET status = WAITING_USER
        update_calls = [
            c for c in mock_conn.execute.call_args_list if "UPDATE phase_executions" in c[0][0]
        ]
        assert len(update_calls) >= 1

        # The activation UPDATE should use WAITING_USER status
        activation_call = update_calls[0]
        args = activation_call[0]
        assert PhaseStatus.WAITING_USER in args

    @pytest.mark.anyio
    async def test_charter_run_status_is_active(self, three_phase_compiled, mock_conn):
        """CharterRun should be created with ACTIVE status."""
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=three_phase_compiled,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="approval_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        # CharterRun INSERT args should include ACTIVE status
        first_call = mock_conn.execute.call_args_list[0]
        args = first_call[0]
        assert CharterRunStatus.ACTIVE in args

    @pytest.mark.anyio
    async def test_raises_workflow_not_found_for_unknown_workflow(
        self, three_phase_compiled, mock_conn
    ):
        with (
            patch(
                "canon.runtime.workflow.get_compiled_charter",
                return_value=three_phase_compiled,
            ),
            pytest.raises(WorkflowNotFoundError) as exc_info,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="nonexistent_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        assert exc_info.value.workflow_name == "nonexistent_workflow"
        assert exc_info.value.charter_name == "Test Approval Charter"

    @pytest.mark.anyio
    async def test_passes_run_context(self, three_phase_compiled, mock_conn):
        """run_context should be passed to the CharterRun INSERT."""
        ctx = {"extra": "data", "source": "test"}
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=three_phase_compiled,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="approval_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
                run_context=ctx,
            )

        # CharterRun INSERT should contain the context dict
        first_call = mock_conn.execute.call_args_list[0]
        args = first_call[0]
        assert ctx in args

    @pytest.mark.anyio
    async def test_default_run_context_is_empty_dict(self, three_phase_compiled, mock_conn):
        """When run_context is None, should default to empty dict."""
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=three_phase_compiled,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="approval_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        first_call = mock_conn.execute.call_args_list[0]
        args = first_call[0]
        # Empty dict should be in args (the run_context default)
        assert {} in args

    @pytest.mark.anyio
    async def test_diamond_workflow_activates_only_entry_phase(self, diamond_compiled, mock_conn):
        """Diamond: initiation is the only entry phase."""
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=diamond_compiled,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="diamond_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        # 4 phases in diamond -> 4 PhaseExecution INSERTs
        phase_inserts = [
            c for c in mock_conn.execute.call_args_list if "INSERT INTO phase_executions" in c[0][0]
        ]
        assert len(phase_inserts) == 4

        # Only 1 activation UPDATE (for initiation only)
        update_calls = [
            c for c in mock_conn.execute.call_args_list if "UPDATE phase_executions" in c[0][0]
        ]
        assert len(update_calls) == 1

    @pytest.mark.anyio
    async def test_phase_execution_stores_requires_phases(self, three_phase_compiled, mock_conn):
        """PhaseExecution INSERT should include requires_phases list."""
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=three_phase_compiled,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="approval_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        # Collect all phase_executions INSERT args
        phase_inserts = [
            c[0]
            for c in mock_conn.execute.call_args_list
            if "INSERT INTO phase_executions" in c[0][0]
        ]
        # At least one phase should have requires_phases = ["initiation"]
        all_requires = [call[7] for call in phase_inserts]  # index 7 = requires_phases
        assert ["initiation"] in all_requires

    @pytest.mark.anyio
    async def test_phase_execution_stores_assignee_role(self, three_phase_compiled, mock_conn):
        """PhaseExecution INSERT should include assignee_role from charter roles."""
        with patch(
            "canon.runtime.workflow.get_compiled_charter",
            return_value=three_phase_compiled,
        ):
            await start_workflow(
                charter_id=CHARTER_ID,
                subject_id=SUBJECT_ID,
                related_entity_type="exception_offer",
                related_entity_id=OFFER_ID,
                workflow_name="approval_workflow",
                initiated_by_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )

        phase_inserts = [
            c[0]
            for c in mock_conn.execute.call_args_list
            if "INSERT INTO phase_executions" in c[0][0]
        ]
        # index 8 = assignee_role
        all_roles = [call[8] for call in phase_inserts]
        assert "hiring_manager" in all_roles
        assert "ceo" in all_roles


# ---------------------------------------------------------------------------
# complete_charter_run (async, mock_conn)
# ---------------------------------------------------------------------------


class TestCompleteCharterRun:
    """Test complete_charter_run - marks runs as completed."""

    @pytest.mark.anyio
    async def test_sets_status_to_completed(self, mock_conn):
        await complete_charter_run(RUN_ID, mock_conn)

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        sql = call_args[0]
        assert "UPDATE charter_runs" in sql
        assert CharterRunStatus.COMPLETED in call_args

    @pytest.mark.anyio
    async def test_maps_cancelled_outcome_to_cancelled_status(self, mock_conn):
        await complete_charter_run(RUN_ID, mock_conn, outcome="cancelled")

        call_args = mock_conn.execute.call_args[0]
        assert CharterRunStatus.CANCELLED in call_args

    @pytest.mark.anyio
    async def test_maps_failed_outcome_to_failed_status(self, mock_conn):
        await complete_charter_run(RUN_ID, mock_conn, outcome="failed")

        call_args = mock_conn.execute.call_args[0]
        assert CharterRunStatus.FAILED in call_args

    @pytest.mark.anyio
    async def test_maps_approved_outcome_to_completed_status(self, mock_conn):
        """'approved' is a completed variant."""
        await complete_charter_run(RUN_ID, mock_conn, outcome="approved")

        call_args = mock_conn.execute.call_args[0]
        assert CharterRunStatus.COMPLETED in call_args
        # outcome string should still be "approved"
        assert "approved" in call_args

    @pytest.mark.anyio
    async def test_maps_rejected_outcome_to_completed_status(self, mock_conn):
        """'rejected' is a completed variant."""
        await complete_charter_run(RUN_ID, mock_conn, outcome="rejected")

        call_args = mock_conn.execute.call_args[0]
        assert CharterRunStatus.COMPLETED in call_args
        assert "rejected" in call_args

    @pytest.mark.anyio
    async def test_unknown_outcome_defaults_to_completed(self, mock_conn):
        await complete_charter_run(RUN_ID, mock_conn, outcome="unknown_thing")

        call_args = mock_conn.execute.call_args[0]
        assert CharterRunStatus.COMPLETED in call_args

    @pytest.mark.anyio
    async def test_handles_failure_reason(self, mock_conn):
        await complete_charter_run(
            RUN_ID, mock_conn, outcome="failed", failure_reason="Gate check failed"
        )

        call_args = mock_conn.execute.call_args[0]
        assert "Gate check failed" in call_args

    @pytest.mark.anyio
    async def test_failure_reason_defaults_to_none(self, mock_conn):
        await complete_charter_run(RUN_ID, mock_conn)

        call_args = mock_conn.execute.call_args[0]
        # failure_reason should be None
        assert None in call_args

    @pytest.mark.anyio
    async def test_passes_run_id_to_query(self, mock_conn):
        await complete_charter_run(RUN_ID, mock_conn)

        call_args = mock_conn.execute.call_args[0]
        assert RUN_ID in call_args


# ---------------------------------------------------------------------------
# cancel_charter_run (async, mock_conn)
# ---------------------------------------------------------------------------


class TestCancelCharterRun:
    """Test cancel_charter_run - skips non-terminal phases and cancels run."""

    @pytest.mark.anyio
    async def test_skips_non_terminal_phases(self, mock_conn):
        await cancel_charter_run(RUN_ID, USER_ID, mock_conn)

        # First execute call should be the phase skip UPDATE
        first_call = mock_conn.execute.call_args_list[0]
        sql = first_call[0][0]
        assert "UPDATE phase_executions" in sql
        assert PhaseStatus.SKIPPED in first_call[0]

    @pytest.mark.anyio
    async def test_excludes_terminal_statuses_from_skip(self, mock_conn):
        """Should NOT skip phases already in COMPLETED, FAILED, or SKIPPED."""
        await cancel_charter_run(RUN_ID, USER_ID, mock_conn)

        first_call = mock_conn.execute.call_args_list[0]
        args = first_call[0]
        assert PhaseStatus.COMPLETED in args
        assert PhaseStatus.FAILED in args
        assert PhaseStatus.SKIPPED in args

    @pytest.mark.anyio
    async def test_calls_complete_charter_run_with_cancelled(self, mock_conn):
        """Should call complete_charter_run with outcome='cancelled'."""
        await cancel_charter_run(RUN_ID, USER_ID, mock_conn)

        # Second execute call should be the charter_runs UPDATE
        second_call = mock_conn.execute.call_args_list[1]
        sql = second_call[0][0]
        assert "UPDATE charter_runs" in sql
        assert CharterRunStatus.CANCELLED in second_call[0]

    @pytest.mark.anyio
    async def test_passes_reason_as_failure_reason(self, mock_conn):
        await cancel_charter_run(RUN_ID, USER_ID, mock_conn, reason="Budget cut")

        # The complete_charter_run call should include the reason
        second_call = mock_conn.execute.call_args_list[1]
        args = second_call[0]
        assert "Budget cut" in args

    @pytest.mark.anyio
    async def test_records_cancelled_by_user(self, mock_conn):
        """Phase skip should record who cancelled."""
        await cancel_charter_run(RUN_ID, USER_ID, mock_conn)

        first_call = mock_conn.execute.call_args_list[0]
        args = first_call[0]
        assert USER_ID in args

    @pytest.mark.anyio
    async def test_reason_defaults_to_none(self, mock_conn):
        await cancel_charter_run(RUN_ID, USER_ID, mock_conn)

        # complete_charter_run should be called with failure_reason=None
        second_call = mock_conn.execute.call_args_list[1]
        args = second_call[0]
        # The failure_reason position should be None
        assert None in args


# ---------------------------------------------------------------------------
# get_run_status (async, mock_conn)
# ---------------------------------------------------------------------------


class TestGetRunStatus:
    """Test get_run_status - retrieve run status with phase counts."""

    @pytest.mark.anyio
    async def test_returns_run_info_and_phase_counts(self, mock_conn):
        mock_conn.fetchrow.return_value = {
            "id": RUN_ID,
            "status": CharterRunStatus.ACTIVE,
            "current_workflow": "approval_workflow",
            "current_phase": "hm_approval",
            "initiated_at": "2026-01-01T00:00:00Z",
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": None,
            "final_outcome": None,
        }
        mock_conn.fetch.side_effect = [
            # phase_counts query
            [
                {"status": PhaseStatus.COMPLETED, "count": 1},
                {"status": PhaseStatus.WAITING_USER, "count": 1},
                {"status": PhaseStatus.PENDING, "count": 1},
            ],
            # waiting_phases query
            [
                {
                    "phase_name": "hm_approval",
                    "assignee_role": "hiring_manager",
                    "activated_at": "2026-01-01T00:01:00Z",
                },
            ],
        ]

        result = await get_run_status(RUN_ID, mock_conn)

        assert result["run_id"] == RUN_ID
        assert result["status"] == CharterRunStatus.ACTIVE
        assert result["current_workflow"] == "approval_workflow"
        assert result["current_phase"] == "hm_approval"
        assert result["phase_counts"] == {
            PhaseStatus.COMPLETED: 1,
            PhaseStatus.WAITING_USER: 1,
            PhaseStatus.PENDING: 1,
        }
        assert len(result["waiting_phases"]) == 1
        assert result["waiting_phases"][0]["phase_name"] == "hm_approval"
        assert result["waiting_phases"][0]["assignee_role"] == "hiring_manager"

    @pytest.mark.anyio
    async def test_returns_error_dict_when_run_not_found(self, mock_conn):
        mock_conn.fetchrow.return_value = None

        result = await get_run_status(RUN_ID, mock_conn)

        assert result == {"error": "Run not found"}

    @pytest.mark.anyio
    async def test_completed_run_has_final_outcome(self, mock_conn):
        mock_conn.fetchrow.return_value = {
            "id": RUN_ID,
            "status": CharterRunStatus.COMPLETED,
            "current_workflow": "approval_workflow",
            "current_phase": None,
            "initiated_at": "2026-01-01T00:00:00Z",
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-02T00:00:00Z",
            "final_outcome": "approved",
        }
        mock_conn.fetch.side_effect = [
            [{"status": PhaseStatus.COMPLETED, "count": 3}],
            [],  # no waiting phases
        ]

        result = await get_run_status(RUN_ID, mock_conn)

        assert result["status"] == CharterRunStatus.COMPLETED
        assert result["final_outcome"] == "approved"
        assert result["waiting_phases"] == []

    @pytest.mark.anyio
    async def test_empty_phase_counts(self, mock_conn):
        """Run with no phase executions yet."""
        mock_conn.fetchrow.return_value = {
            "id": RUN_ID,
            "status": CharterRunStatus.ACTIVE,
            "current_workflow": "wf",
            "current_phase": None,
            "initiated_at": "2026-01-01T00:00:00Z",
            "started_at": None,
            "completed_at": None,
            "final_outcome": None,
        }
        mock_conn.fetch.side_effect = [
            [],  # no phase counts
            [],  # no waiting phases
        ]

        result = await get_run_status(RUN_ID, mock_conn)

        assert result["phase_counts"] == {}
        assert result["waiting_phases"] == []

    @pytest.mark.anyio
    async def test_queries_use_correct_run_id(self, mock_conn):
        mock_conn.fetchrow.return_value = None

        await get_run_status(RUN_ID, mock_conn)

        # fetchrow should be called with run_id
        mock_conn.fetchrow.assert_called_once()
        call_args = mock_conn.fetchrow.call_args[0]
        assert RUN_ID in call_args


# ---------------------------------------------------------------------------
# is_workflow_complete (async, mock_conn)
# ---------------------------------------------------------------------------


class TestIsWorkflowComplete:
    """Test is_workflow_complete - check if all phases are terminal."""

    @pytest.mark.anyio
    async def test_all_phases_terminal_returns_true(self, three_phase_compiled, mock_conn):
        mock_conn.fetchrow.return_value = {
            "current_workflow": "approval_workflow",
        }
        mock_conn.fetchval.return_value = 0  # no non-terminal phases

        result = await is_workflow_complete(RUN_ID, three_phase_compiled, mock_conn)

        assert result is True

    @pytest.mark.anyio
    async def test_some_phases_pending_returns_false(self, three_phase_compiled, mock_conn):
        mock_conn.fetchrow.return_value = {
            "current_workflow": "approval_workflow",
        }
        mock_conn.fetchval.return_value = 2  # 2 non-terminal phases

        result = await is_workflow_complete(RUN_ID, three_phase_compiled, mock_conn)

        assert result is False

    @pytest.mark.anyio
    async def test_run_not_found_returns_false(self, three_phase_compiled, mock_conn):
        mock_conn.fetchrow.return_value = None

        result = await is_workflow_complete(RUN_ID, three_phase_compiled, mock_conn)

        assert result is False

    @pytest.mark.anyio
    async def test_null_workflow_returns_false(self, three_phase_compiled, mock_conn):
        """Run exists but current_workflow is None."""
        mock_conn.fetchrow.return_value = {
            "current_workflow": None,
        }

        result = await is_workflow_complete(RUN_ID, three_phase_compiled, mock_conn)

        assert result is False

    @pytest.mark.anyio
    async def test_checks_terminal_statuses(self, three_phase_compiled, mock_conn):
        """Should check against COMPLETED, FAILED, SKIPPED as terminal."""
        mock_conn.fetchrow.return_value = {
            "current_workflow": "approval_workflow",
        }
        mock_conn.fetchval.return_value = 0

        await is_workflow_complete(RUN_ID, three_phase_compiled, mock_conn)

        # fetchval query should exclude COMPLETED, FAILED, SKIPPED
        call_args = mock_conn.fetchval.call_args[0]
        assert PhaseStatus.COMPLETED in call_args
        assert PhaseStatus.FAILED in call_args
        assert PhaseStatus.SKIPPED in call_args

    @pytest.mark.anyio
    async def test_single_non_terminal_phase_returns_false(self, three_phase_compiled, mock_conn):
        mock_conn.fetchrow.return_value = {
            "current_workflow": "approval_workflow",
        }
        mock_conn.fetchval.return_value = 1

        result = await is_workflow_complete(RUN_ID, three_phase_compiled, mock_conn)

        assert result is False
