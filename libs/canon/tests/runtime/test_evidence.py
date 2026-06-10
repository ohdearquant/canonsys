"""Tests for canon.runtime.evidence module.

Tests cover:
- EvidenceEventType enum completeness and naming convention
- EvidenceResult frozen dataclass and serialization
- record_phase_evidence with mocked insert_entity
- record_grant_evidence with mocked insert_entity
- record_workflow_evidence with mocked insert_entity
- Title formatting helpers for all event types
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from canon.runtime.evidence import (
    EvidenceEventType,
    EvidenceResult,
    _format_evidence_title,
    _format_grant_evidence_title,
    _format_workflow_evidence_title,
    record_grant_evidence,
    record_phase_evidence,
    record_workflow_evidence,
)

from .conftest import RUN_ID, SUBJECT_ID, TENANT_ID, USER_ID

# ---------------------------------------------------------------------------
# Convenience aliases
# ---------------------------------------------------------------------------
TOKEN_ID = UUID("00000000-0000-0000-0000-000000200000")

_PATCH_INSERT = "canon.runtime.evidence.insert_entity"


# ===========================================================================
# EvidenceEventType enum
# ===========================================================================


class TestEvidenceEventType:
    """Test the StrEnum with 16 event types across 4 domains."""

    def test_total_count(self):
        assert len(EvidenceEventType) == 16

    # -- Phase events (6) --------------------------------------------------

    def test_phase_activated(self):
        assert EvidenceEventType.PHASE_ACTIVATED.value == "phase.activated"

    def test_phase_claimed(self):
        assert EvidenceEventType.PHASE_CLAIMED.value == "phase.claimed"

    def test_phase_completed(self):
        assert EvidenceEventType.PHASE_COMPLETED.value == "phase.completed"

    def test_phase_failed(self):
        assert EvidenceEventType.PHASE_FAILED.value == "phase.failed"

    def test_phase_skipped(self):
        assert EvidenceEventType.PHASE_SKIPPED.value == "phase.skipped"

    def test_phase_delegated(self):
        assert EvidenceEventType.PHASE_DELEGATED.value == "phase.delegated"

    def test_phase_event_count(self):
        phase_events = [e for e in EvidenceEventType if e.value.startswith("phase.")]
        assert len(phase_events) == 6

    # -- Grant events (5) --------------------------------------------------

    def test_grant_issued(self):
        assert EvidenceEventType.GRANT_ISSUED.value == "grant.issued"

    def test_grant_accessed(self):
        assert EvidenceEventType.GRANT_ACCESSED.value == "grant.accessed"

    def test_grant_revoked(self):
        assert EvidenceEventType.GRANT_REVOKED.value == "grant.revoked"

    def test_grant_expired(self):
        assert EvidenceEventType.GRANT_EXPIRED.value == "grant.expired"

    def test_grant_transferred(self):
        assert EvidenceEventType.GRANT_TRANSFERRED.value == "grant.transferred"

    def test_grant_event_count(self):
        grant_events = [e for e in EvidenceEventType if e.value.startswith("grant.")]
        assert len(grant_events) == 5

    # -- Workflow events (4) ------------------------------------------------

    def test_workflow_started(self):
        assert EvidenceEventType.WORKFLOW_STARTED.value == "workflow.started"

    def test_workflow_completed(self):
        assert EvidenceEventType.WORKFLOW_COMPLETED.value == "workflow.completed"

    def test_workflow_failed(self):
        assert EvidenceEventType.WORKFLOW_FAILED.value == "workflow.failed"

    def test_workflow_cancelled(self):
        assert EvidenceEventType.WORKFLOW_CANCELLED.value == "workflow.cancelled"

    def test_workflow_event_count(self):
        wf_events = [e for e in EvidenceEventType if e.value.startswith("workflow.")]
        assert len(wf_events) == 4

    # -- Naming convention --------------------------------------------------

    def test_all_values_follow_domain_action_pattern(self):
        """Every value must be '{domain}.{action}'."""
        for ev in EvidenceEventType:
            parts = ev.value.split(".")
            assert len(parts) == 2, f"{ev.name} value '{ev.value}' is not domain.action"
            assert parts[0] in ("phase", "grant", "workflow", "trigger")

    def test_roundtrip_from_string(self):
        for ev in EvidenceEventType:
            assert EvidenceEventType(ev.value) is ev

    def test_is_str_subclass(self):
        """StrEnum members are also str instances."""
        for ev in EvidenceEventType:
            assert isinstance(ev, str)


# ===========================================================================
# EvidenceResult dataclass
# ===========================================================================


class TestEvidenceResult:
    """Test the frozen result dataclass."""

    def _make(self, **overrides) -> EvidenceResult:
        defaults = {
            "evidence_id": uuid4(),
            "evidence_type": "runtime.phase.completed",
            "created_at": datetime.now(UTC),
        }
        defaults.update(overrides)
        return EvidenceResult(**defaults)

    def test_creation_and_field_access(self):
        eid = uuid4()
        now = datetime.now(UTC)
        result = EvidenceResult(
            evidence_id=eid,
            evidence_type="runtime.phase.completed",
            created_at=now,
        )
        assert result.evidence_id == eid
        assert result.evidence_type == "runtime.phase.completed"
        assert result.created_at == now

    def test_frozen_immutability(self):
        result = self._make()
        with pytest.raises(FrozenInstanceError):
            result.evidence_type = "changed"  # type: ignore[misc]

    def test_to_dict_keys(self):
        result = self._make()
        d = result.to_dict()
        assert set(d.keys()) == {"evidence_id", "evidence_type", "created_at"}

    def test_to_dict_evidence_id_is_string(self):
        eid = uuid4()
        result = self._make(evidence_id=eid)
        assert result.to_dict()["evidence_id"] == str(eid)

    def test_to_dict_created_at_is_isoformat(self):
        now = datetime.now(UTC)
        result = self._make(created_at=now)
        assert result.to_dict()["created_at"] == now.isoformat()

    def test_to_dict_evidence_type_passthrough(self):
        result = self._make(evidence_type="runtime.grant.issued")
        assert result.to_dict()["evidence_type"] == "runtime.grant.issued"


# ===========================================================================
# record_phase_evidence
# ===========================================================================


class TestRecordPhaseEvidence:
    """Test phase evidence recording with mocked insert_entity."""

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_returns_evidence_result(self, mock_insert, mock_conn):
        result = await record_phase_evidence(
            run_id=RUN_ID,
            phase_name="hm_approval",
            event_type=EvidenceEventType.PHASE_COMPLETED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            conn=mock_conn,
        )
        assert isinstance(result, EvidenceResult)
        assert isinstance(result.evidence_id, UUID)
        assert result.evidence_type == "runtime.phase.completed"
        assert isinstance(result.created_at, datetime)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_calls_insert_entity(self, mock_insert, mock_conn):
        await record_phase_evidence(
            run_id=RUN_ID,
            phase_name="initiation",
            event_type=EvidenceEventType.PHASE_ACTIVATED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            conn=mock_conn,
        )
        mock_insert.assert_awaited_once()
        args, kwargs = mock_insert.call_args
        evidence = args[0]
        # Verify entity structure
        assert evidence.content.tenant_id == TENANT_ID
        assert evidence.content.evidence_type == "runtime.phase.activated"
        assert evidence.content.source == "canon.runtime"
        assert evidence.content.source_id == str(RUN_ID)
        assert evidence.content.collected_by_id == USER_ID
        assert kwargs["conn"] is mock_conn

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_evidence_data_contains_required_fields(self, mock_insert, mock_conn):
        await record_phase_evidence(
            run_id=RUN_ID,
            phase_name="hm_approval",
            event_type=EvidenceEventType.PHASE_COMPLETED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["run_id"] == str(RUN_ID)
        assert data["phase_name"] == "hm_approval"
        assert data["event_type"] == "phase.completed"
        assert data["actor_id"] == str(USER_ID)
        assert "timestamp" in data

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_merges_additional_data(self, mock_insert, mock_conn):
        extra = {"action": "approve", "notes": "LGTM"}
        await record_phase_evidence(
            run_id=RUN_ID,
            phase_name="hm_approval",
            event_type=EvidenceEventType.PHASE_COMPLETED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            data=extra,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["action"] == "approve"
        assert data["notes"] == "LGTM"
        # Core fields still present
        assert data["run_id"] == str(RUN_ID)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_converts_uuid_values_in_data(self, mock_insert, mock_conn):
        some_id = uuid4()
        await record_phase_evidence(
            run_id=RUN_ID,
            phase_name="review",
            event_type=EvidenceEventType.PHASE_COMPLETED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            data={"related_id": some_id},
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["related_id"] == str(some_id)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_subject_id_passed_through(self, mock_insert, mock_conn):
        await record_phase_evidence(
            run_id=RUN_ID,
            phase_name="hm_approval",
            event_type=EvidenceEventType.PHASE_COMPLETED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.subject_id == SUBJECT_ID

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_subject_id_optional_none(self, mock_insert, mock_conn):
        result = await record_phase_evidence(
            run_id=RUN_ID,
            phase_name="setup",
            event_type=EvidenceEventType.PHASE_ACTIVATED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=None,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.subject_id is None
        # Still returns a valid result
        assert isinstance(result, EvidenceResult)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_no_data_means_no_extra_keys(self, mock_insert, mock_conn):
        await record_phase_evidence(
            run_id=RUN_ID,
            phase_name="check",
            event_type=EvidenceEventType.PHASE_ACTIVATED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        expected_keys = {"run_id", "phase_name", "event_type", "actor_id", "timestamp"}
        assert set(data.keys()) == expected_keys

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_title_set_on_entity(self, mock_insert, mock_conn):
        await record_phase_evidence(
            run_id=RUN_ID,
            phase_name="hm_approval",
            event_type=EvidenceEventType.PHASE_COMPLETED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.title == "Phase 'hm_approval' completed"

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_evidence_type_prefixed_with_runtime(self, mock_insert, mock_conn):
        for event_type in (
            EvidenceEventType.PHASE_ACTIVATED,
            EvidenceEventType.PHASE_FAILED,
            EvidenceEventType.PHASE_SKIPPED,
        ):
            mock_insert.reset_mock()
            result = await record_phase_evidence(
                run_id=RUN_ID,
                phase_name="test",
                event_type=event_type,
                actor_id=USER_ID,
                tenant_id=TENANT_ID,
                conn=mock_conn,
            )
            assert result.evidence_type == f"runtime.{event_type.value}"
            evidence = mock_insert.call_args[0][0]
            assert evidence.content.evidence_type == f"runtime.{event_type.value}"


# ===========================================================================
# record_grant_evidence
# ===========================================================================


class TestRecordGrantEvidence:
    """Test grant evidence recording with mocked insert_entity."""

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_returns_evidence_result(self, mock_insert, mock_conn):
        result = await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_ISSUED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        assert isinstance(result, EvidenceResult)
        assert result.evidence_type == "runtime.grant.issued"

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_entity_uses_token_as_source(self, mock_insert, mock_conn):
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_ISSUED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.source == "canon.runtime.grants"
        assert evidence.content.source_id == str(TOKEN_ID)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_evidence_data_contains_token_and_subject(self, mock_insert, mock_conn):
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_REVOKED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["token_id"] == str(TOKEN_ID)
        assert data["subject_id"] == str(SUBJECT_ID)
        assert data["event_type"] == "grant.revoked"
        assert data["actor_id"] == str(USER_ID)
        assert "timestamp" in data

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_optional_run_id_included_when_provided(self, mock_insert, mock_conn):
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_ISSUED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            run_id=RUN_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["run_id"] == str(RUN_ID)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_optional_phase_name_included_when_provided(self, mock_insert, mock_conn):
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_ISSUED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            phase_name="hm_approval",
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["phase_name"] == "hm_approval"

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_run_id_and_phase_absent_when_not_provided(self, mock_insert, mock_conn):
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_ISSUED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert "run_id" not in data
        assert "phase_name" not in data

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_merges_additional_data(self, mock_insert, mock_conn):
        grantee_id = uuid4()
        extra = {"document_type": "resume", "grantee_id": str(grantee_id)}
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_ISSUED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            data=extra,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["document_type"] == "resume"
        assert data["grantee_id"] == str(grantee_id)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_converts_uuid_values_in_data(self, mock_insert, mock_conn):
        grantee_uuid = uuid4()
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_TRANSFERRED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            data={"new_grantee_id": grantee_uuid},
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["new_grantee_id"] == str(grantee_uuid)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_title_uses_document_type_from_data(self, mock_insert, mock_conn):
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_ISSUED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            data={"document_type": "resume"},
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.title == "Access granted to 'resume'"

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_title_defaults_to_document_when_no_type(self, mock_insert, mock_conn):
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_REVOKED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.title == "Access to 'document' revoked"

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_tenant_id_and_subject_id_on_entity(self, mock_insert, mock_conn):
        await record_grant_evidence(
            token_id=TOKEN_ID,
            event_type=EvidenceEventType.GRANT_ISSUED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.tenant_id == TENANT_ID
        assert evidence.content.subject_id == SUBJECT_ID


# ===========================================================================
# record_workflow_evidence
# ===========================================================================


class TestRecordWorkflowEvidence:
    """Test workflow evidence recording with mocked insert_entity."""

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_returns_evidence_result(self, mock_insert, mock_conn):
        result = await record_workflow_evidence(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            event_type=EvidenceEventType.WORKFLOW_STARTED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        assert isinstance(result, EvidenceResult)
        assert result.evidence_type == "runtime.workflow.started"

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_entity_source_is_workflow(self, mock_insert, mock_conn):
        await record_workflow_evidence(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            event_type=EvidenceEventType.WORKFLOW_STARTED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.source == "canon.runtime.workflow"
        assert evidence.content.source_id == str(RUN_ID)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_evidence_data_contains_required_fields(self, mock_insert, mock_conn):
        await record_workflow_evidence(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            event_type=EvidenceEventType.WORKFLOW_COMPLETED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["run_id"] == str(RUN_ID)
        assert data["workflow_name"] == "approval_workflow"
        assert data["event_type"] == "workflow.completed"
        assert data["actor_id"] == str(USER_ID)
        assert data["subject_id"] == str(SUBJECT_ID)
        assert "timestamp" in data

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_merges_additional_data(self, mock_insert, mock_conn):
        extra = {"reason": "all phases passed", "duration_s": 3600}
        await record_workflow_evidence(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            event_type=EvidenceEventType.WORKFLOW_COMPLETED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            data=extra,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        assert data["reason"] == "all phases passed"
        assert data["duration_s"] == 3600

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_converts_uuid_values_in_data(self, mock_insert, mock_conn):
        charter_id = uuid4()
        await record_workflow_evidence(
            run_id=RUN_ID,
            workflow_name="pip_workflow",
            event_type=EvidenceEventType.WORKFLOW_STARTED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            data={"charter_id": charter_id},
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.data["charter_id"] == str(charter_id)

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_no_data_means_no_extra_keys(self, mock_insert, mock_conn):
        await record_workflow_evidence(
            run_id=RUN_ID,
            workflow_name="approval_workflow",
            event_type=EvidenceEventType.WORKFLOW_STARTED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        data = evidence.content.data
        expected_keys = {
            "run_id",
            "workflow_name",
            "event_type",
            "actor_id",
            "subject_id",
            "timestamp",
        }
        assert set(data.keys()) == expected_keys

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_title_set_on_entity(self, mock_insert, mock_conn):
        await record_workflow_evidence(
            run_id=RUN_ID,
            workflow_name="pip_workflow",
            event_type=EvidenceEventType.WORKFLOW_FAILED,
            actor_id=USER_ID,
            tenant_id=TENANT_ID,
            subject_id=SUBJECT_ID,
            conn=mock_conn,
        )
        evidence = mock_insert.call_args[0][0]
        assert evidence.content.title == "Workflow 'pip_workflow' failed"

    @pytest.mark.anyio
    @patch(_PATCH_INSERT, new_callable=AsyncMock)
    async def test_all_workflow_event_types(self, mock_insert, mock_conn):
        """Each workflow event type produces the correct runtime prefix."""
        for event_type in (
            EvidenceEventType.WORKFLOW_STARTED,
            EvidenceEventType.WORKFLOW_COMPLETED,
            EvidenceEventType.WORKFLOW_FAILED,
            EvidenceEventType.WORKFLOW_CANCELLED,
        ):
            mock_insert.reset_mock()
            result = await record_workflow_evidence(
                run_id=RUN_ID,
                workflow_name="test_wf",
                event_type=event_type,
                actor_id=USER_ID,
                tenant_id=TENANT_ID,
                subject_id=SUBJECT_ID,
                conn=mock_conn,
            )
            assert result.evidence_type == f"runtime.{event_type.value}"


# ===========================================================================
# Title formatting helpers
# ===========================================================================


class TestFormatEvidenceTitle:
    """Test _format_evidence_title for phase events."""

    def test_phase_activated(self):
        title = _format_evidence_title(EvidenceEventType.PHASE_ACTIVATED, "initiation")
        assert title == "Phase 'initiation' activated"

    def test_phase_claimed(self):
        title = _format_evidence_title(EvidenceEventType.PHASE_CLAIMED, "hm_approval")
        assert title == "Phase 'hm_approval' claimed"

    def test_phase_completed(self):
        title = _format_evidence_title(EvidenceEventType.PHASE_COMPLETED, "review")
        assert title == "Phase 'review' completed"

    def test_phase_failed(self):
        title = _format_evidence_title(EvidenceEventType.PHASE_FAILED, "check")
        assert title == "Phase 'check' failed"

    def test_phase_skipped(self):
        title = _format_evidence_title(EvidenceEventType.PHASE_SKIPPED, "optional")
        assert title == "Phase 'optional' skipped"

    def test_phase_delegated(self):
        title = _format_evidence_title(EvidenceEventType.PHASE_DELEGATED, "sign_off")
        assert title == "Phase 'sign_off' delegated"

    def test_unknown_event_type_fallback(self):
        """Non-phase event types get fallback format."""
        title = _format_evidence_title(EvidenceEventType.GRANT_ISSUED, "some_phase")
        assert title == "Phase 'some_phase' event: grant.issued"

    def test_all_phase_events_have_specific_titles(self):
        """Every phase event type returns a title WITHOUT 'event:' (no fallback)."""
        phase_events = [e for e in EvidenceEventType if e.value.startswith("phase.")]
        for ev in phase_events:
            title = _format_evidence_title(ev, "test")
            assert "event:" not in title, f"{ev.name} uses fallback title"


class TestFormatGrantEvidenceTitle:
    """Test _format_grant_evidence_title for grant events."""

    def test_grant_issued(self):
        title = _format_grant_evidence_title(EvidenceEventType.GRANT_ISSUED, "resume")
        assert title == "Access granted to 'resume'"

    def test_grant_accessed(self):
        title = _format_grant_evidence_title(EvidenceEventType.GRANT_ACCESSED, "transcript")
        assert title == "Document 'transcript' accessed"

    def test_grant_revoked(self):
        title = _format_grant_evidence_title(EvidenceEventType.GRANT_REVOKED, "background_check")
        assert title == "Access to 'background_check' revoked"

    def test_grant_expired(self):
        title = _format_grant_evidence_title(EvidenceEventType.GRANT_EXPIRED, "offer_letter")
        assert title == "Access to 'offer_letter' expired"

    def test_grant_transferred(self):
        title = _format_grant_evidence_title(EvidenceEventType.GRANT_TRANSFERRED, "resume")
        assert title == "Access to 'resume' transferred"

    def test_unknown_event_type_fallback(self):
        """Non-grant event types get fallback format."""
        title = _format_grant_evidence_title(EvidenceEventType.PHASE_COMPLETED, "doc")
        assert title == "Document access event: phase.completed"

    def test_all_grant_events_have_specific_titles(self):
        """Every grant event type returns a title WITHOUT 'event:' (no fallback)."""
        grant_events = [e for e in EvidenceEventType if e.value.startswith("grant.")]
        for ev in grant_events:
            title = _format_grant_evidence_title(ev, "test")
            assert "event:" not in title, f"{ev.name} uses fallback title"


class TestFormatWorkflowEvidenceTitle:
    """Test _format_workflow_evidence_title for workflow events."""

    def test_workflow_started(self):
        title = _format_workflow_evidence_title(EvidenceEventType.WORKFLOW_STARTED, "hiring")
        assert title == "Workflow 'hiring' started"

    def test_workflow_completed(self):
        title = _format_workflow_evidence_title(EvidenceEventType.WORKFLOW_COMPLETED, "pip")
        assert title == "Workflow 'pip' completed"

    def test_workflow_failed(self):
        title = _format_workflow_evidence_title(EvidenceEventType.WORKFLOW_FAILED, "review")
        assert title == "Workflow 'review' failed"

    def test_workflow_cancelled(self):
        title = _format_workflow_evidence_title(EvidenceEventType.WORKFLOW_CANCELLED, "onboard")
        assert title == "Workflow 'onboard' cancelled"

    def test_unknown_event_type_fallback(self):
        """Non-workflow event types get fallback format."""
        title = _format_workflow_evidence_title(EvidenceEventType.GRANT_ISSUED, "wf")
        assert title == "Workflow event: grant.issued"

    def test_all_workflow_events_have_specific_titles(self):
        """Every workflow event type returns a title WITHOUT 'event:' (no fallback)."""
        wf_events = [e for e in EvidenceEventType if e.value.startswith("workflow.")]
        for ev in wf_events:
            title = _format_workflow_evidence_title(ev, "test")
            assert "event:" not in title, f"{ev.name} uses fallback title"
