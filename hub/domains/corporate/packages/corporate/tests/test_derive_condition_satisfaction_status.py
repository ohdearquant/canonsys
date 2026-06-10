"""Tests for derive_condition_satisfaction_status feature.

This tests the anti-gaming derivation that determines the overall satisfaction
status of closing conditions for M&A transactions.

Regulatory Context:
    - M&A contract law (closing conditions)
    - Shareholder protection requirements
    - Regulatory closing conditions
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import uuid4

import pytest
from canon_vocab_corporate import (
    ConditionSatisfactionStatus,
    ConditionType,
    derive_condition_satisfaction_status,
)

if TYPE_CHECKING:
    from uuid import UUID


class TestDeriveConditionSatisfactionStatus:
    """Tests for derive_condition_satisfaction_status derivation function."""

    @pytest.mark.asyncio
    async def test_all_satisfied_when_all_conditions_satisfied(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """All conditions should be satisfied when all are in satisfied status."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "regulatory_approval",
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids[1],
                "condition_type": "shareholder_approval",
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert isinstance(result, dict)
        assert result["deal_id"] == deal_id
        assert result["all_satisfied"] is True
        assert result["total_conditions"] == 2
        assert result["satisfied_count"] == 2
        assert result["waived_count"] == 0
        assert result["pending_count"] == 0
        assert result["failed_count"] == 0
        assert result["blocking_conditions"] == ()
        assert result["evidence_hash"] is not None
        assert result["derived_at"] is not None

    @pytest.mark.asyncio
    async def test_all_satisfied_when_all_conditions_waived(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """All conditions should be satisfied when all are waived."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "financing",
                "status": "waived",
                "deadline": None,
                "satisfied_at": None,
                "waived_at": datetime.now(UTC),
                "is_material": True,
            },
            {
                "condition_id": condition_ids[1],
                "condition_type": "no_mac",
                "status": "waived",
                "deadline": None,
                "satisfied_at": None,
                "waived_at": datetime.now(UTC),
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["all_satisfied"] is True
        assert result["waived_count"] == 2
        assert result["blocking_conditions"] == ()

    @pytest.mark.asyncio
    async def test_all_satisfied_with_mixed_satisfied_and_waived(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """All satisfied when mix of satisfied and waived conditions."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "regulatory_approval",
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids[1],
                "condition_type": "financing",
                "status": "waived",
                "deadline": None,
                "satisfied_at": None,
                "waived_at": datetime.now(UTC),
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["all_satisfied"] is True
        assert result["satisfied_count"] == 1
        assert result["waived_count"] == 1

    @pytest.mark.asyncio
    async def test_not_satisfied_when_pending_material_conditions(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """Not satisfied when material conditions are pending."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "regulatory_approval",
                "status": "pending",
                "deadline": datetime.now(UTC) + timedelta(days=30),
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids[1],
                "condition_type": "shareholder_approval",
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["all_satisfied"] is False
        assert result["pending_count"] == 1
        assert condition_ids[0] in result["blocking_conditions"]

    @pytest.mark.asyncio
    async def test_not_satisfied_when_in_progress_material_conditions(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """Not satisfied when material conditions are in progress."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "due_diligence",
                "status": "in_progress",
                "deadline": datetime.now(UTC) + timedelta(days=14),
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["all_satisfied"] is False
        assert result["pending_count"] == 1
        assert condition_ids[0] in result["blocking_conditions"]

    @pytest.mark.asyncio
    async def test_non_material_pending_does_not_block(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """Non-material pending conditions should not block closing."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "regulatory_approval",
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids[1],
                "condition_type": "employee_retention",
                "status": "pending",
                "deadline": datetime.now(UTC) + timedelta(days=60),
                "satisfied_at": None,
                "waived_at": None,
                "is_material": False,  # Non-material
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["all_satisfied"] is True
        assert result["pending_count"] == 1
        # Non-material pending should NOT be in blocking
        assert condition_ids[1] not in result["blocking_conditions"]

    @pytest.mark.asyncio
    async def test_not_satisfied_when_failed_conditions(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """Not satisfied when conditions have failed."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "financing",
                "status": "failed",
                "deadline": None,
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["all_satisfied"] is False
        assert result["failed_count"] == 1
        assert condition_ids[0] in result["blocking_conditions"]

    @pytest.mark.asyncio
    async def test_not_satisfied_when_expired_conditions(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """Not satisfied when conditions have expired."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "third_party_consent",
                "status": "expired",
                "deadline": datetime.now(UTC) - timedelta(days=7),
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["all_satisfied"] is False
        assert result["failed_count"] == 1  # Expired counts as failed
        assert condition_ids[0] in result["blocking_conditions"]

    @pytest.mark.asyncio
    async def test_all_satisfied_when_no_conditions(self, mock_ctx, deal_id: UUID):
        """All satisfied (vacuously true) when no conditions defined."""
        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = []
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["all_satisfied"] is True
        assert result["total_conditions"] == 0
        assert result["satisfied_count"] == 0
        assert result["waived_count"] == 0
        assert result["pending_count"] == 0
        assert result["failed_count"] == 0
        assert result["conditions_by_type"] == {}
        assert result["blocking_conditions"] == ()
        assert result["evidence_hash"] is None

    @pytest.mark.asyncio
    async def test_conditions_by_type_tracking(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """Should track condition status by type."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "regulatory_approval",
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids[1],
                "condition_type": "shareholder_approval",
                "status": "pending",
                "deadline": datetime.now(UTC) + timedelta(days=30),
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids[2],
                "condition_type": "financing",
                "status": "waived",
                "deadline": None,
                "satisfied_at": None,
                "waived_at": datetime.now(UTC),
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert ConditionType.REGULATORY_APPROVAL in result["conditions_by_type"]
        assert (
            result["conditions_by_type"][ConditionType.REGULATORY_APPROVAL]
            == ConditionSatisfactionStatus.SATISFIED
        )
        assert ConditionType.SHAREHOLDER_APPROVAL in result["conditions_by_type"]
        assert (
            result["conditions_by_type"][ConditionType.SHAREHOLDER_APPROVAL]
            == ConditionSatisfactionStatus.PENDING
        )
        assert ConditionType.FINANCING in result["conditions_by_type"]
        assert (
            result["conditions_by_type"][ConditionType.FINANCING]
            == ConditionSatisfactionStatus.WAIVED
        )

    @pytest.mark.asyncio
    async def test_conditions_by_type_worst_status_wins(self, mock_ctx, deal_id: UUID):
        """Multiple conditions of same type should report worst status."""
        condition_ids_local = [uuid4() for _ in range(3)]
        mock_rows = [
            {
                "condition_id": condition_ids_local[0],
                "condition_type": "regulatory_approval",
                "status": "satisfied",  # Good
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids_local[1],
                "condition_type": "regulatory_approval",
                "status": "pending",  # Worse
                "deadline": datetime.now(UTC) + timedelta(days=30),
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids_local[2],
                "condition_type": "regulatory_approval",
                "status": "failed",  # Worst
                "deadline": None,
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        # Should report the worst status (failed)
        assert (
            result["conditions_by_type"][ConditionType.REGULATORY_APPROVAL]
            == ConditionSatisfactionStatus.FAILED
        )

    @pytest.mark.asyncio
    async def test_estimated_completion_from_pending_deadlines(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """Should estimate completion from latest pending deadline."""
        early_deadline = datetime.now(UTC) + timedelta(days=14)
        late_deadline = datetime.now(UTC) + timedelta(days=45)

        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "regulatory_approval",
                "status": "pending",
                "deadline": early_deadline,
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids[1],
                "condition_type": "shareholder_approval",
                "status": "in_progress",
                "deadline": late_deadline,
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        # Should be the latest deadline
        assert result["estimated_completion"] == late_deadline

    @pytest.mark.asyncio
    async def test_no_estimated_completion_when_all_satisfied(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """No estimated completion when all conditions satisfied."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "regulatory_approval",
                "status": "satisfied",
                "deadline": datetime.now(UTC) - timedelta(days=7),
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["estimated_completion"] is None

    @pytest.mark.asyncio
    async def test_all_condition_types_supported(self, mock_ctx, deal_id: UUID):
        """Should support all defined condition types."""
        condition_types = [
            "regulatory_approval",
            "shareholder_approval",
            "financing",
            "no_mac",
            "due_diligence",
            "third_party_consent",
            "employee_retention",
            "carve_out",
            "legal_opinion",
            "tax_ruling",
        ]
        condition_ids_local = [uuid4() for _ in condition_types]

        mock_rows = [
            {
                "condition_id": cid,
                "condition_type": ctype,
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            }
            for cid, ctype in zip(condition_ids_local, condition_types)
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["all_satisfied"] is True
        assert result["total_conditions"] == len(condition_types)
        # Verify all types are in conditions_by_type
        assert len(result["conditions_by_type"]) == len(condition_types)

    @pytest.mark.asyncio
    async def test_counts_are_correct(self, mock_ctx, deal_id: UUID):
        """All counts should be correctly tallied."""
        condition_ids_local = [uuid4() for _ in range(6)]
        mock_rows = [
            {
                "condition_id": condition_ids_local[0],
                "condition_type": "regulatory_approval",
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids_local[1],
                "condition_type": "shareholder_approval",
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids_local[2],
                "condition_type": "financing",
                "status": "waived",
                "deadline": None,
                "satisfied_at": None,
                "waived_at": datetime.now(UTC),
                "is_material": True,
            },
            {
                "condition_id": condition_ids_local[3],
                "condition_type": "no_mac",
                "status": "pending",
                "deadline": datetime.now(UTC) + timedelta(days=30),
                "satisfied_at": None,
                "waived_at": None,
                "is_material": False,
            },
            {
                "condition_id": condition_ids_local[4],
                "condition_type": "due_diligence",
                "status": "failed",
                "deadline": None,
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
            {
                "condition_id": condition_ids_local[5],
                "condition_type": "third_party_consent",
                "status": "expired",
                "deadline": datetime.now(UTC) - timedelta(days=7),
                "satisfied_at": None,
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result["total_conditions"] == 6
        assert result["satisfied_count"] == 2
        assert result["waived_count"] == 1
        assert result["pending_count"] == 1  # in_progress also counts as pending
        assert result["failed_count"] == 2  # failed + expired

    @pytest.mark.asyncio
    async def test_evidence_hash_is_deterministic(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """Evidence hash should be deterministic for same data."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "regulatory_approval",
                "status": "satisfied",
                "deadline": None,
                "satisfied_at": datetime.now(UTC),
                "waived_at": None,
                "is_material": True,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result1 = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)
            result2 = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert result1["evidence_hash"] == result2["evidence_hash"]

    @pytest.mark.asyncio
    async def test_result_is_dict(self, mock_ctx, deal_id: UUID):
        """Result should be a dictionary."""
        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = []
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_material_default_is_true(
        self, mock_ctx, deal_id: UUID, condition_ids: list[UUID]
    ):
        """When is_material is not specified, should default to True (blocking)."""
        mock_rows = [
            {
                "condition_id": condition_ids[0],
                "condition_type": "regulatory_approval",
                "status": "pending",
                "deadline": datetime.now(UTC) + timedelta(days=30),
                "satisfied_at": None,
                "waived_at": None,
                # is_material not specified
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_condition_satisfaction_status.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_condition_satisfaction_status({"deal_id": deal_id}, mock_ctx)

        # Should treat as material (blocking)
        assert result["all_satisfied"] is False
        assert condition_ids[0] in result["blocking_conditions"]
