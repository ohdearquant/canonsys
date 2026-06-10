"""Tests for canon.runtime.grants module.

Tests the grant lifecycle management for Charter Runtime:
- GrantResult frozen dataclass and serialization
- document_type_to_purpose mapping
- create_phase_grant (phase-scoped and time-scoped)
- revoke_phase_grants
- transfer_phase_grants
- get_active_grants
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from canon.dsl.ast import GrantNode
from canon.entities.workflows.queue import DocumentAccessPurpose, DocumentAccessStatus
from canon.runtime.grants import (
    PHASE_GRANT_SAFETY_HOURS,
    GrantResult,
    create_phase_grant,
    document_type_to_purpose,
    get_active_grants,
    revoke_phase_grants,
    transfer_phase_grants,
)

from .conftest import OFFER_ID, RUN_ID, SUBJECT_ID, TENANT_ID, USER_ID

# ---------------------------------------------------------------------------
# GrantResult tests
# ---------------------------------------------------------------------------


class TestGrantResult:
    """Test GrantResult frozen dataclass."""

    def test_creation_and_field_access(self):
        token_id = uuid4()
        now = datetime.now(UTC)
        result = GrantResult(
            token_id=token_id,
            document_type="resume",
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            expires_at=now,
            is_phase_scoped=True,
        )
        assert result.token_id == token_id
        assert result.document_type == "resume"
        assert result.grantee_id == USER_ID
        assert result.subject_id == SUBJECT_ID
        assert result.expires_at == now
        assert result.is_phase_scoped is True

    def test_creation_with_no_expires(self):
        result = GrantResult(
            token_id=uuid4(),
            document_type="resume",
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            expires_at=None,
            is_phase_scoped=False,
        )
        assert result.expires_at is None
        assert result.is_phase_scoped is False

    def test_to_dict_serialization(self):
        token_id = uuid4()
        now = datetime(2026, 2, 5, 12, 0, 0, tzinfo=UTC)
        result = GrantResult(
            token_id=token_id,
            document_type="offer_letter",
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            expires_at=now,
            is_phase_scoped=False,
        )
        d = result.to_dict()

        assert d["token_id"] == str(token_id)
        assert d["document_type"] == "offer_letter"
        assert d["grantee_id"] == str(USER_ID)
        assert d["subject_id"] == str(SUBJECT_ID)
        assert d["expires_at"] == now.isoformat()
        assert d["is_phase_scoped"] is False

    def test_to_dict_none_expires(self):
        result = GrantResult(
            token_id=uuid4(),
            document_type="resume",
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            expires_at=None,
            is_phase_scoped=True,
        )
        d = result.to_dict()
        assert d["expires_at"] is None

    def test_frozen_immutability(self):
        result = GrantResult(
            token_id=uuid4(),
            document_type="resume",
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            expires_at=datetime.now(UTC),
            is_phase_scoped=True,
        )
        with pytest.raises(FrozenInstanceError):
            result.document_type = "background_report"  # type: ignore[misc]

        with pytest.raises(FrozenInstanceError):
            result.is_phase_scoped = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# document_type_to_purpose tests
# ---------------------------------------------------------------------------


class TestDocumentTypeToPurpose:
    """Test the document_type -> DocumentAccessPurpose mapping."""

    def test_resume(self):
        assert document_type_to_purpose("resume") == DocumentAccessPurpose.RESUME_REVIEW

    def test_background_report(self):
        assert (
            document_type_to_purpose("background_report") == DocumentAccessPurpose.BACKGROUND_CHECK
        )

    def test_offer_letter(self):
        assert document_type_to_purpose("offer_letter") == DocumentAccessPurpose.OFFER_REVIEW

    def test_offer_letter_draft(self):
        assert document_type_to_purpose("offer_letter_draft") == DocumentAccessPurpose.OFFER_REVIEW

    def test_pip_plan(self):
        assert document_type_to_purpose("pip_plan") == DocumentAccessPurpose.PIP_REVIEW

    def test_performance_report(self):
        assert document_type_to_purpose("performance_report") == DocumentAccessPurpose.PIP_REVIEW

    def test_termination_certificate(self):
        assert (
            document_type_to_purpose("termination_certificate")
            == DocumentAccessPurpose.TERMINATION_REVIEW
        )

    def test_decision_certificate(self):
        assert (
            document_type_to_purpose("decision_certificate")
            == DocumentAccessPurpose.TERMINATION_REVIEW
        )

    def test_separation_agreement(self):
        assert (
            document_type_to_purpose("separation_agreement")
            == DocumentAccessPurpose.TERMINATION_REVIEW
        )

    def test_unknown_type_falls_back_to_resume_review(self):
        assert document_type_to_purpose("unknown_doc") == DocumentAccessPurpose.RESUME_REVIEW
        assert document_type_to_purpose("") == DocumentAccessPurpose.RESUME_REVIEW
        assert document_type_to_purpose("tax_form") == DocumentAccessPurpose.RESUME_REVIEW


# ---------------------------------------------------------------------------
# create_phase_grant tests
# ---------------------------------------------------------------------------


class TestCreatePhaseGrant:
    """Test create_phase_grant with mocked insert_entity."""

    @pytest.mark.anyio
    @patch("canon.runtime.grants.insert_entity", new_callable=AsyncMock)
    @patch("canon.runtime.grants.uuid4")
    async def test_phase_scoped_grant(self, mock_uuid4, mock_insert, mock_conn):
        """Phase-scoped grant (ttl_minutes=None) uses 48h safety window."""
        fixed_token_id = uuid4()
        mock_uuid4.return_value = fixed_token_id

        grant_node = GrantNode(document_type="resume", ttl_minutes=None)
        before = datetime.now(UTC)

        result = await create_phase_grant(
            run_id=RUN_ID,
            phase_name="hm_approval",
            grant=grant_node,
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            tenant_id=TENANT_ID,
            conn=mock_conn,
        )

        after = datetime.now(UTC)

        assert isinstance(result, GrantResult)
        assert result.token_id == fixed_token_id
        assert result.document_type == "resume"
        assert result.grantee_id == USER_ID
        assert result.subject_id == SUBJECT_ID
        assert result.is_phase_scoped is True

        # Expires at ~48 hours from now (safety window)
        expected_min = before + timedelta(hours=PHASE_GRANT_SAFETY_HOURS)
        expected_max = after + timedelta(hours=PHASE_GRANT_SAFETY_HOURS)
        assert expected_min <= result.expires_at <= expected_max

        # insert_entity was called once
        mock_insert.assert_awaited_once()
        token_arg = mock_insert.call_args[0][0]
        assert token_arg.id == fixed_token_id
        assert token_arg.content.subject_id == SUBJECT_ID
        assert token_arg.content.grantee_id == USER_ID
        assert token_arg.content.workflow_instance_id == RUN_ID
        assert token_arg.content.document_type == "resume"
        assert token_arg.content.purpose == DocumentAccessPurpose.RESUME_REVIEW
        assert token_arg.content.status == DocumentAccessStatus.ACTIVE

    @pytest.mark.anyio
    @patch("canon.runtime.grants.insert_entity", new_callable=AsyncMock)
    @patch("canon.runtime.grants.uuid4")
    async def test_time_scoped_grant(self, mock_uuid4, mock_insert, mock_conn):
        """Time-scoped grant (ttl_minutes=5) uses explicit TTL."""
        fixed_token_id = uuid4()
        mock_uuid4.return_value = fixed_token_id

        grant_node = GrantNode(document_type="background_report", ttl_minutes=5)
        before = datetime.now(UTC)

        result = await create_phase_grant(
            run_id=RUN_ID,
            phase_name="review",
            grant=grant_node,
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            tenant_id=TENANT_ID,
            conn=mock_conn,
        )

        after = datetime.now(UTC)

        assert result.is_phase_scoped is False
        assert result.document_type == "background_report"

        # Expires at ~5 minutes from now
        expected_min = before + timedelta(minutes=5)
        expected_max = after + timedelta(minutes=5)
        assert expected_min <= result.expires_at <= expected_max

        # Verify the purpose mapping
        token_arg = mock_insert.call_args[0][0]
        assert token_arg.content.purpose == DocumentAccessPurpose.BACKGROUND_CHECK

    @pytest.mark.anyio
    @patch("canon.runtime.grants.insert_entity", new_callable=AsyncMock)
    @patch("canon.runtime.grants.uuid4")
    async def test_with_phase_execution_id(self, mock_uuid4, mock_insert, mock_conn):
        """Phase execution ID is passed through to workflow_step_id."""
        fixed_token_id = uuid4()
        mock_uuid4.return_value = fixed_token_id
        phase_exec_id = uuid4()

        grant_node = GrantNode(document_type="offer_letter", ttl_minutes=None)

        result = await create_phase_grant(
            run_id=RUN_ID,
            phase_name="offer_review",
            grant=grant_node,
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            tenant_id=TENANT_ID,
            phase_execution_id=phase_exec_id,
            conn=mock_conn,
        )

        assert result.token_id == fixed_token_id

        token_arg = mock_insert.call_args[0][0]
        assert token_arg.content.workflow_step_id == phase_exec_id
        assert token_arg.content.purpose == DocumentAccessPurpose.OFFER_REVIEW

    @pytest.mark.anyio
    @patch("canon.runtime.grants.insert_entity", new_callable=AsyncMock)
    @patch("canon.runtime.grants.uuid4")
    async def test_without_phase_execution_id(self, mock_uuid4, mock_insert, mock_conn):
        """When phase_execution_id is None, workflow_step_id is None."""
        fixed_token_id = uuid4()
        mock_uuid4.return_value = fixed_token_id

        grant_node = GrantNode(document_type="resume", ttl_minutes=None)

        await create_phase_grant(
            run_id=RUN_ID,
            phase_name="initiation",
            grant=grant_node,
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            tenant_id=TENANT_ID,
            phase_execution_id=None,
            conn=mock_conn,
        )

        token_arg = mock_insert.call_args[0][0]
        assert token_arg.content.workflow_step_id is None

    @pytest.mark.anyio
    @patch("canon.runtime.grants.insert_entity", new_callable=AsyncMock)
    @patch("canon.runtime.grants.uuid4")
    async def test_returns_grant_result_fields(self, mock_uuid4, mock_insert, mock_conn):
        """Verify all GrantResult fields match the inputs."""
        fixed_token_id = uuid4()
        mock_uuid4.return_value = fixed_token_id

        grant_node = GrantNode(document_type="pip_plan", ttl_minutes=30)

        result = await create_phase_grant(
            run_id=RUN_ID,
            phase_name="pip_review",
            grant=grant_node,
            grantee_id=USER_ID,
            subject_id=SUBJECT_ID,
            tenant_id=TENANT_ID,
            conn=mock_conn,
        )

        assert result.token_id == fixed_token_id
        assert result.document_type == "pip_plan"
        assert result.grantee_id == USER_ID
        assert result.subject_id == SUBJECT_ID
        assert result.is_phase_scoped is False
        assert result.expires_at is not None


# ---------------------------------------------------------------------------
# revoke_phase_grants tests
# ---------------------------------------------------------------------------


class TestRevokePhaseGrants:
    """Test revoke_phase_grants with mocked fetch."""

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_revokes_active_tokens(self, mock_fetch, mock_conn):
        """Revokes active tokens and returns count."""
        mock_fetch.return_value = [
            {"id": uuid4(), "document_type": "resume", "grantee_id": USER_ID},
            {"id": uuid4(), "document_type": "offer_letter", "grantee_id": USER_ID},
        ]

        count = await revoke_phase_grants(
            run_id=RUN_ID,
            phase_name="hm_approval",
            user_id=USER_ID,
            reason="Phase completed",
            conn=mock_conn,
        )

        assert count == 2
        mock_fetch.assert_awaited_once()

        # Verify the SQL parameters
        args = mock_fetch.call_args
        # First positional arg is the SQL query
        sql = args[0][0]
        assert "UPDATE document_access_tokens" in sql
        assert "status IN ('active', 'used')" in sql
        assert "RETURNING id, document_type, grantee_id" in sql

        # Check parameter values
        assert args[0][1] == DocumentAccessStatus.REVOKED.value  # $1
        # $2 = now (datetime)
        assert args[0][3] == USER_ID  # $3 = revoked_by_id
        assert "hm_approval" in args[0][4]  # $4 = reason includes phase name
        assert args[0][5] == RUN_ID  # $5 = run_id

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_no_tokens_to_revoke(self, mock_fetch, mock_conn):
        """Returns 0 when no active tokens exist."""
        mock_fetch.return_value = []

        count = await revoke_phase_grants(
            run_id=RUN_ID,
            phase_name="initiation",
            user_id=USER_ID,
            reason="Phase completed",
            conn=mock_conn,
        )

        assert count == 0

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_multiple_tokens_revoked(self, mock_fetch, mock_conn):
        """Handles multiple tokens revoked for the same phase."""
        token_ids = [uuid4() for _ in range(5)]
        mock_fetch.return_value = [
            {"id": tid, "document_type": "resume", "grantee_id": USER_ID} for tid in token_ids
        ]

        count = await revoke_phase_grants(
            run_id=RUN_ID,
            phase_name="review_phase",
            user_id=USER_ID,
            reason="Phase approved",
            conn=mock_conn,
        )

        assert count == 5

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_reason_includes_phase_name(self, mock_fetch, mock_conn):
        """Revocation reason includes the phase name for audit trail."""
        mock_fetch.return_value = []

        await revoke_phase_grants(
            run_id=RUN_ID,
            phase_name="ceo_approval",
            user_id=USER_ID,
            reason="Decision made",
            conn=mock_conn,
        )

        args = mock_fetch.call_args
        reason_param = args[0][4]  # $4 = revocation_reason
        assert "ceo_approval" in reason_param
        assert "Decision made" in reason_param


# ---------------------------------------------------------------------------
# transfer_phase_grants tests
# ---------------------------------------------------------------------------


class TestTransferPhaseGrants:
    """Test transfer_phase_grants with mocked insert_entity and fetch."""

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    @patch("canon.runtime.grants.insert_entity", new_callable=AsyncMock)
    @patch("canon.runtime.grants.uuid4")
    async def test_creates_new_grants_then_revokes_old(
        self, mock_uuid4, mock_insert, mock_fetch, mock_conn
    ):
        """Creates grants for to_user first, then revokes from_user grants."""
        from_user = uuid4()
        to_user = uuid4()
        token_id_1 = uuid4()
        token_id_2 = uuid4()

        # uuid4 is called once per grant in create_phase_grant
        mock_uuid4.side_effect = [token_id_1, token_id_2]

        # fetch is called for the revocation query
        mock_fetch.return_value = [
            {"id": uuid4(), "document_type": "resume"},
        ]

        grants = [
            GrantNode(document_type="resume", ttl_minutes=None),
            GrantNode(document_type="offer_letter", ttl_minutes=10),
        ]

        results = await transfer_phase_grants(
            run_id=RUN_ID,
            phase_name="hm_approval",
            grants=grants,
            from_user_id=from_user,
            to_user_id=to_user,
            subject_id=SUBJECT_ID,
            tenant_id=TENANT_ID,
            phase_execution_id=OFFER_ID,
            conn=mock_conn,
        )

        # Two new grants created
        assert len(results) == 2
        assert results[0].token_id == token_id_1
        assert results[0].document_type == "resume"
        assert results[0].grantee_id == to_user
        assert results[0].is_phase_scoped is True

        assert results[1].token_id == token_id_2
        assert results[1].document_type == "offer_letter"
        assert results[1].grantee_id == to_user
        assert results[1].is_phase_scoped is False

        # insert_entity called twice (one per grant)
        assert mock_insert.await_count == 2

        # fetch called once (revocation query)
        mock_fetch.assert_awaited_once()
        revoke_args = mock_fetch.call_args
        sql = revoke_args[0][0]
        assert "UPDATE document_access_tokens" in sql
        assert "grantee_id = $6" in sql  # filters by from_user

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    @patch("canon.runtime.grants.insert_entity", new_callable=AsyncMock)
    @patch("canon.runtime.grants.uuid4")
    async def test_returns_list_of_grant_results(
        self, mock_uuid4, mock_insert, mock_fetch, mock_conn
    ):
        """Returns a list of GrantResult for each new grant."""
        to_user = uuid4()
        from_user = uuid4()
        tid1, tid2, tid3 = uuid4(), uuid4(), uuid4()
        mock_uuid4.side_effect = [tid1, tid2, tid3]
        mock_fetch.return_value = []

        grants = [
            GrantNode(document_type="resume", ttl_minutes=None),
            GrantNode(document_type="pip_plan", ttl_minutes=15),
            GrantNode(document_type="termination_certificate", ttl_minutes=None),
        ]

        results = await transfer_phase_grants(
            run_id=RUN_ID,
            phase_name="review",
            grants=grants,
            from_user_id=from_user,
            to_user_id=to_user,
            subject_id=SUBJECT_ID,
            tenant_id=TENANT_ID,
            phase_execution_id=None,
            conn=mock_conn,
        )

        assert len(results) == 3
        assert all(isinstance(r, GrantResult) for r in results)
        assert [r.token_id for r in results] == [tid1, tid2, tid3]
        assert [r.document_type for r in results] == [
            "resume",
            "pip_plan",
            "termination_certificate",
        ]
        assert all(r.grantee_id == to_user for r in results)

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    @patch("canon.runtime.grants.insert_entity", new_callable=AsyncMock)
    async def test_empty_grants_list(self, mock_insert, mock_fetch, mock_conn):
        """Transferring empty grants list creates nothing and still revokes."""
        mock_fetch.return_value = []

        results = await transfer_phase_grants(
            run_id=RUN_ID,
            phase_name="review",
            grants=[],
            from_user_id=uuid4(),
            to_user_id=uuid4(),
            subject_id=SUBJECT_ID,
            tenant_id=TENANT_ID,
            phase_execution_id=None,
            conn=mock_conn,
        )

        assert results == []
        mock_insert.assert_not_awaited()
        # Revocation still happens
        mock_fetch.assert_awaited_once()

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    @patch("canon.runtime.grants.insert_entity", new_callable=AsyncMock)
    @patch("canon.runtime.grants.uuid4")
    async def test_revoke_targets_from_user_only(
        self, mock_uuid4, mock_insert, mock_fetch, mock_conn
    ):
        """Revocation only targets the from_user's tokens, not all tokens."""
        from_user = uuid4()
        to_user = uuid4()
        mock_uuid4.return_value = uuid4()
        mock_fetch.return_value = []

        await transfer_phase_grants(
            run_id=RUN_ID,
            phase_name="hm_approval",
            grants=[GrantNode(document_type="resume")],
            from_user_id=from_user,
            to_user_id=to_user,
            subject_id=SUBJECT_ID,
            tenant_id=TENANT_ID,
            phase_execution_id=None,
            conn=mock_conn,
        )

        revoke_args = mock_fetch.call_args[0]
        # $5 = run_id, $6 = from_user_id
        assert revoke_args[5] == RUN_ID
        assert revoke_args[6] == from_user


# ---------------------------------------------------------------------------
# get_active_grants tests
# ---------------------------------------------------------------------------


class TestGetActiveGrants:
    """Test get_active_grants with mocked fetch."""

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_returns_list_of_dicts(self, mock_fetch, mock_conn):
        """Returns grant records as list of dicts."""
        row1 = {
            "id": uuid4(),
            "document_type": "resume",
            "grantee_id": USER_ID,
            "subject_id": SUBJECT_ID,
            "purpose": "resume_review",
            "status": "active",
            "issued_at": datetime.now(UTC),
            "expires_at": datetime.now(UTC) + timedelta(hours=48),
            "access_count": 0,
        }
        # Mock rows that behave like asyncpg Records (support dict())
        mock_row = type(
            "Row",
            (),
            {
                "__iter__": lambda s: iter(row1.items()),
                "keys": lambda s: row1.keys(),
                "__getitem__": lambda s, k: row1[k],
            },
        )()
        mock_fetch.return_value = [row1]

        results = await get_active_grants(
            run_id=RUN_ID,
            conn=mock_conn,
        )

        assert len(results) == 1
        assert results[0]["document_type"] == "resume"
        mock_fetch.assert_awaited_once()

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_filters_by_phase_execution_id(self, mock_fetch, mock_conn):
        """Adds workflow_step_id filter when phase_execution_id provided."""
        phase_exec_id = uuid4()
        mock_fetch.return_value = []

        await get_active_grants(
            run_id=RUN_ID,
            phase_execution_id=phase_exec_id,
            conn=mock_conn,
        )

        args = mock_fetch.call_args
        sql = args[0][0]
        assert "workflow_step_id" in sql
        # Parameters: $1=run_id, $2=now, $3=phase_execution_id
        assert args[0][1] == RUN_ID
        # $2 is the datetime (now), $3 is phase_execution_id
        assert args[0][3] == phase_exec_id

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_filters_by_grantee_id(self, mock_fetch, mock_conn):
        """Adds grantee_id filter when provided."""
        mock_fetch.return_value = []

        await get_active_grants(
            run_id=RUN_ID,
            grantee_id=USER_ID,
            conn=mock_conn,
        )

        args = mock_fetch.call_args
        sql = args[0][0]
        assert "grantee_id" in sql
        # Parameters: $1=run_id, $2=now, $3=grantee_id
        assert args[0][3] == USER_ID

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_filters_by_both_phase_and_grantee(self, mock_fetch, mock_conn):
        """Both filters applied with correct parameter numbering."""
        phase_exec_id = uuid4()
        mock_fetch.return_value = []

        await get_active_grants(
            run_id=RUN_ID,
            phase_execution_id=phase_exec_id,
            grantee_id=USER_ID,
            conn=mock_conn,
        )

        args = mock_fetch.call_args
        sql = args[0][0]
        assert "workflow_step_id = $3" in sql
        assert "grantee_id = $4" in sql
        # Parameters: $1=run_id, $2=now, $3=phase_exec_id, $4=grantee_id
        assert args[0][1] == RUN_ID
        assert args[0][3] == phase_exec_id
        assert args[0][4] == USER_ID

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_empty_results(self, mock_fetch, mock_conn):
        """Returns empty list when no active grants exist."""
        mock_fetch.return_value = []

        results = await get_active_grants(
            run_id=RUN_ID,
            conn=mock_conn,
        )

        assert results == []

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_no_optional_filters(self, mock_fetch, mock_conn):
        """Without optional filters, only base conditions are used."""
        mock_fetch.return_value = []

        await get_active_grants(
            run_id=RUN_ID,
            conn=mock_conn,
        )

        args = mock_fetch.call_args
        sql = args[0][0]
        assert "workflow_instance_id = $1" in sql
        assert "status IN ('active', 'used')" in sql
        assert "expires_at > $2" in sql
        # WHERE clause should NOT contain optional filters
        # (grantee_id appears in SELECT but not as a WHERE condition)
        assert "workflow_step_id" not in sql
        assert "grantee_id = $" not in sql

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_query_orders_by_issued_at_desc(self, mock_fetch, mock_conn):
        """Results are ordered by issued_at descending."""
        mock_fetch.return_value = []

        await get_active_grants(
            run_id=RUN_ID,
            conn=mock_conn,
        )

        args = mock_fetch.call_args
        sql = args[0][0]
        assert "ORDER BY issued_at DESC" in sql


# ---------------------------------------------------------------------------
# PHASE_GRANT_SAFETY_HOURS constant test
# ---------------------------------------------------------------------------


class TestConstants:
    """Test module-level constants."""

    def test_phase_grant_safety_hours(self):
        assert PHASE_GRANT_SAFETY_HOURS == 48
