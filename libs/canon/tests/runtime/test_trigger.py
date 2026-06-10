"""Tests for canon.runtime.trigger - trigger firing for await directives."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from canon.runtime.evidence import EvidenceEventType
from canon.runtime.phase_state import PhaseState
from canon.runtime.trigger import (
    TriggerNotFoundError,
    TriggerResult,
    fire_trigger,
    has_trigger_fired,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def run_id() -> UUID:
    return uuid4()


@pytest.fixture()
def actor_id() -> UUID:
    return uuid4()


@pytest.fixture()
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture()
def mock_conn():
    """Mock asyncpg connection."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.execute = AsyncMock()
    return conn


# =============================================================================
# TriggerResult tests
# =============================================================================


class TestTriggerResult:
    def test_creation(self):
        eid = uuid4()
        result = TriggerResult(
            trigger_name="candidate_files_dispute",
            phases_unblocked=("dispute_resolution",),
            evidence_ids=(eid,),
        )
        assert result.trigger_name == "candidate_files_dispute"
        assert result.phases_unblocked == ("dispute_resolution",)
        assert result.evidence_ids == (eid,)

    def test_to_dict(self):
        eid = uuid4()
        result = TriggerResult(
            trigger_name="board_ack",
            phases_unblocked=("ceo_approval", "board_review"),
            evidence_ids=(eid,),
        )
        d = result.to_dict()
        assert d["trigger_name"] == "board_ack"
        assert d["phases_unblocked"] == ["ceo_approval", "board_review"]
        assert d["evidence_ids"] == [str(eid)]

    def test_empty_result(self):
        result = TriggerResult(
            trigger_name="noop",
            phases_unblocked=(),
            evidence_ids=(),
        )
        assert result.to_dict()["phases_unblocked"] == []


# =============================================================================
# TriggerNotFoundError tests
# =============================================================================


class TestTriggerNotFoundError:
    def test_error_message(self):
        rid = uuid4()
        err = TriggerNotFoundError(rid, "some_trigger")
        assert "some_trigger" in str(err)
        assert str(rid) in str(err)

    def test_error_attributes(self):
        rid = uuid4()
        err = TriggerNotFoundError(rid, "some_trigger")
        assert err.run_id == rid
        assert err.trigger_name == "some_trigger"


# =============================================================================
# fire_trigger tests
# =============================================================================


class TestFireTrigger:
    @pytest.mark.asyncio()
    async def test_raises_when_no_waiting_phases(self, run_id, actor_id, tenant_id, mock_conn):
        """fire_trigger raises TriggerNotFoundError when no phases are in WAITING_TRIGGER."""
        with patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []  # No waiting phases

            with pytest.raises(TriggerNotFoundError):
                await fire_trigger(
                    run_id=run_id,
                    trigger_name="candidate_files_dispute",
                    actor_id=actor_id,
                    tenant_id=tenant_id,
                    conn=mock_conn,
                )

    @pytest.mark.asyncio()
    async def test_raises_when_no_matching_trigger(self, run_id, actor_id, tenant_id, mock_conn):
        """fire_trigger raises TriggerNotFoundError when phases wait for a different trigger."""
        with patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                {
                    "id": uuid4(),
                    "phase_name": "dispute_resolution",
                    "workflow_name": "approval_workflow",
                    "trigger_names": ["other_trigger"],
                }
            ]

            with pytest.raises(TriggerNotFoundError):
                await fire_trigger(
                    run_id=run_id,
                    trigger_name="candidate_files_dispute",
                    actor_id=actor_id,
                    tenant_id=tenant_id,
                    conn=mock_conn,
                )

    @pytest.mark.asyncio()
    async def test_unblocks_matching_phase(self, run_id, actor_id, tenant_id, mock_conn):
        """fire_trigger transitions matching phase and records evidence."""
        evidence_id = uuid4()

        with (
            patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch,
            patch(
                "canon.runtime.trigger.record_phase_evidence",
                new_callable=AsyncMock,
            ) as mock_evidence,
        ):
            mock_fetch.return_value = [
                {
                    "id": uuid4(),
                    "phase_name": "dispute_resolution",
                    "workflow_name": "approval_workflow",
                    "trigger_names": ["candidate_files_dispute"],
                }
            ]

            mock_evidence.return_value = MagicMock(evidence_id=evidence_id)
            # Simulate successful optimistic-lock UPDATE
            mock_conn.execute.return_value = "UPDATE 1"

            result = await fire_trigger(
                run_id=run_id,
                trigger_name="candidate_files_dispute",
                actor_id=actor_id,
                tenant_id=tenant_id,
                conn=mock_conn,
            )

            assert isinstance(result, TriggerResult)
            assert result.trigger_name == "candidate_files_dispute"
            assert result.phases_unblocked == ("dispute_resolution",)
            assert len(result.evidence_ids) == 1

            # Verify phase was transitioned via conn.execute (optimistic lock)
            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0]
            assert PhaseState.IN_PROGRESS.value in call_args
            assert PhaseState.WAITING_TRIGGER.value in call_args

            # Verify evidence was recorded
            mock_evidence.assert_called_once()
            ev_kwargs = mock_evidence.call_args.kwargs
            assert ev_kwargs["event_type"] == EvidenceEventType.TRIGGER_FIRED
            assert ev_kwargs["data"]["trigger_name"] == "candidate_files_dispute"

    @pytest.mark.asyncio()
    async def test_unblocks_multiple_phases(self, run_id, actor_id, tenant_id, mock_conn):
        """fire_trigger can unblock multiple phases waiting on the same trigger."""
        with (
            patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch,
            patch(
                "canon.runtime.trigger.record_phase_evidence",
                new_callable=AsyncMock,
            ) as mock_evidence,
        ):
            mock_fetch.return_value = [
                {
                    "id": uuid4(),
                    "phase_name": "phase_a",
                    "workflow_name": "wf",
                    "trigger_names": ["shared_trigger"],
                },
                {
                    "id": uuid4(),
                    "phase_name": "phase_b",
                    "workflow_name": "wf",
                    "trigger_names": ["shared_trigger"],
                },
            ]

            mock_evidence.return_value = MagicMock(evidence_id=uuid4())
            mock_conn.execute.return_value = "UPDATE 1"

            result = await fire_trigger(
                run_id=run_id,
                trigger_name="shared_trigger",
                actor_id=actor_id,
                tenant_id=tenant_id,
                conn=mock_conn,
            )

            assert len(result.phases_unblocked) == 2
            assert "phase_a" in result.phases_unblocked
            assert "phase_b" in result.phases_unblocked

    @pytest.mark.asyncio()
    async def test_passes_trigger_data_to_evidence(self, run_id, actor_id, tenant_id, mock_conn):
        """fire_trigger passes optional data payload to evidence record."""
        with (
            patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch,
            patch(
                "canon.runtime.trigger.record_phase_evidence",
                new_callable=AsyncMock,
            ) as mock_evidence,
        ):
            mock_fetch.return_value = [
                {
                    "id": uuid4(),
                    "phase_name": "upload_phase",
                    "workflow_name": "wf",
                    "trigger_names": ["document_uploaded"],
                }
            ]

            mock_evidence.return_value = MagicMock(evidence_id=uuid4())
            mock_conn.execute.return_value = "UPDATE 1"

            await fire_trigger(
                run_id=run_id,
                trigger_name="document_uploaded",
                actor_id=actor_id,
                tenant_id=tenant_id,
                data={"file_name": "report.pdf", "size": 1024},
                conn=mock_conn,
            )

            ev_kwargs = mock_evidence.call_args.kwargs
            assert ev_kwargs["data"]["trigger_data"] == {
                "file_name": "report.pdf",
                "size": 1024,
            }


# =============================================================================
# has_trigger_fired tests
# =============================================================================


class TestHasTriggerFired:
    @pytest.mark.asyncio()
    async def test_returns_true_when_evidence_exists(self, run_id, mock_conn):
        """has_trigger_fired returns True when matching evidence record found."""
        with patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [{"id": uuid4()}]

            result = await has_trigger_fired(
                run_id=run_id,
                trigger_name="some_trigger",
                conn=mock_conn,
            )

            assert result is True

    @pytest.mark.asyncio()
    async def test_returns_false_when_no_evidence(self, run_id, mock_conn):
        """has_trigger_fired returns False when no matching evidence found."""
        with patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            result = await has_trigger_fired(
                run_id=run_id,
                trigger_name="some_trigger",
                conn=mock_conn,
            )

            assert result is False

    @pytest.mark.asyncio()
    async def test_queries_correct_evidence_type(self, run_id, mock_conn):
        """has_trigger_fired queries for the correct evidence type and trigger name."""
        with patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            await has_trigger_fired(
                run_id=run_id,
                trigger_name="board_ack",
                conn=mock_conn,
            )

            call_args = mock_fetch.call_args
            # Verify the SQL parameters
            args = call_args.args
            assert str(run_id) in args  # source_id
            assert f"runtime.{EvidenceEventType.TRIGGER_FIRED.value}" in args
            assert "board_ack" in args


# =============================================================================
# Integration: _evaluate_await_ref uses has_trigger_fired
# =============================================================================


class TestEvaluateAwaitRefIntegration:
    @pytest.mark.asyncio()
    async def test_await_satisfied_when_trigger_fired(self, run_id, mock_conn):
        """_evaluate_await_ref returns satisfied=True after trigger fires."""
        from canon.dsl.ast import AwaitRefNode
        from canon.runtime.require_eval import _evaluate_await_ref

        ref = AwaitRefNode(trigger="candidate_files_dispute")

        with patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [{"id": uuid4()}]  # Evidence exists

            result = await _evaluate_await_ref(run_id, ref, mock_conn)

            assert result["satisfied"] is True
            assert result["reason"] is None
            assert result["trigger_name"] == "candidate_files_dispute"

    @pytest.mark.asyncio()
    async def test_await_unsatisfied_when_trigger_not_fired(self, run_id, mock_conn):
        """_evaluate_await_ref returns satisfied=False when trigger hasn't fired."""
        from canon.dsl.ast import AwaitRefNode
        from canon.runtime.require_eval import _evaluate_await_ref

        ref = AwaitRefNode(trigger="board_ack")

        with patch("canon.runtime.trigger.fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []  # No evidence

            result = await _evaluate_await_ref(run_id, ref, mock_conn)

            assert result["satisfied"] is False
            assert "not been fired" in result["reason"]


# =============================================================================
# Integration: activate_phase with awaits
# =============================================================================


class TestActivatePhaseWithAwaits:
    @pytest.mark.asyncio()
    async def test_phase_with_awaits_goes_to_waiting_trigger(self, run_id, mock_conn):
        """activate_phase sends phases with await directives to WAITING_TRIGGER."""
        from canon.dsl.ast import (
            AwaitNode,
            CharterNode,
            PhaseNode,
            SchemaRefNode,
            WorkflowNode,
        )
        from canon.dsl.compiler import CompiledCharter
        from canon.runtime.cascade import activate_phase

        phase = PhaseNode(
            name="dispute_resolution",
            requires=(),
            actions=(),
            outputs=(),
            awaits=(AwaitNode(trigger="candidate_files_dispute"),),
        )
        workflow = WorkflowNode(name="wf", phases=(phase,))
        charter_ast = CharterNode(
            name="test",
            version="1.0",
            schemas=(SchemaRefNode(namespace="test", version="2026.01"),),
            workflows=(workflow,),
        )
        compiled = CompiledCharter(
            name="test",
            version="1.0",
            ast=charter_ast,
            feature_names=frozenset(),
            schema_types={},
            phase_order={"wf": ("dispute_resolution",)},
            policy_ids=frozenset(),
            package_names=frozenset(),
            situations=(),
            roles=(),
        )

        with (
            patch("canon.runtime.cascade.select_one", new_callable=AsyncMock) as mock_select,
            patch("canon.runtime.cascade.update", new_callable=AsyncMock) as mock_update,
        ):
            mock_select.return_value = {"status": PhaseState.PENDING.value}

            result = await activate_phase(
                run_id=run_id,
                workflow_name="wf",
                phase_name="dispute_resolution",
                compiled=compiled,
                conn=mock_conn,
            )

            assert result is True

            # Verify the phase was set to WAITING_TRIGGER
            call_kwargs = mock_update.call_args.kwargs
            assert call_kwargs["data"]["status"] == PhaseState.WAITING_TRIGGER.value
            assert call_kwargs["data"]["trigger_names"] == ["candidate_files_dispute"]

    @pytest.mark.asyncio()
    async def test_phase_without_awaits_goes_to_waiting_user(self, run_id, mock_conn):
        """activate_phase sends phases without await directives to WAITING_USER."""
        from canon.dsl.ast import CharterNode, PhaseNode, SchemaRefNode, WorkflowNode
        from canon.dsl.compiler import CompiledCharter
        from canon.runtime.cascade import activate_phase

        phase = PhaseNode(
            name="approval",
            requires=(),
            actions=(),
            outputs=(),
        )
        workflow = WorkflowNode(name="wf", phases=(phase,))
        charter_ast = CharterNode(
            name="test",
            version="1.0",
            schemas=(SchemaRefNode(namespace="test", version="2026.01"),),
            workflows=(workflow,),
        )
        compiled = CompiledCharter(
            name="test",
            version="1.0",
            ast=charter_ast,
            feature_names=frozenset(),
            schema_types={},
            phase_order={"wf": ("approval",)},
            policy_ids=frozenset(),
            package_names=frozenset(),
            situations=(),
            roles=(),
        )

        with (
            patch("canon.runtime.cascade.select_one", new_callable=AsyncMock) as mock_select,
            patch("canon.runtime.cascade.update", new_callable=AsyncMock) as mock_update,
        ):
            mock_select.return_value = {"status": PhaseState.PENDING.value}

            result = await activate_phase(
                run_id=run_id,
                workflow_name="wf",
                phase_name="approval",
                compiled=compiled,
                conn=mock_conn,
            )

            assert result is True

            call_kwargs = mock_update.call_args.kwargs
            assert call_kwargs["data"]["status"] == PhaseState.WAITING_USER.value
            assert "trigger_names" not in call_kwargs["data"]
