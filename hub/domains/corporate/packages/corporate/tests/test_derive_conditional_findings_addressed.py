"""Tests for derive_conditional_findings_addressed feature.

This tests the anti-gaming derivation that determines whether all conditional
findings from due diligence have been properly addressed.

Regulatory Context:
    - SEC M&A disclosure rules (material findings)
    - Fiduciary duty requirements (due diligence)
    - Due diligence best practices
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import uuid4

import pytest
from canon_vocab_corporate import derive_conditional_findings_addressed

if TYPE_CHECKING:
    from uuid import UUID


class TestDeriveConditionalFindingsAddressed:
    """Tests for derive_conditional_findings_addressed derivation function."""

    @pytest.mark.asyncio
    async def test_findings_addressed_when_all_remediated(
        self, mock_ctx, deal_id: UUID, finding_ids: list[UUID]
    ):
        """Findings should be addressed when all are remediated."""
        mock_rows = [
            {
                "finding_id": finding_ids[0],
                "status": "remediated",
                "severity": "high",
                "is_blocking": False,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids[1],
                "status": "remediated",
                "severity": "medium",
                "is_blocking": False,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert isinstance(result, dict)
        assert result["deal_id"] == deal_id
        assert result["addressed"] is True
        assert result["total_findings"] == 2
        assert result["remediated_count"] == 2
        assert result["open_count"] == 0
        assert result["blocking_findings"] == ()
        assert result["evidence_hash"] is not None
        assert result["derived_at"] is not None

    @pytest.mark.asyncio
    async def test_findings_addressed_when_all_waived(
        self, mock_ctx, deal_id: UUID, finding_ids: list[UUID]
    ):
        """Findings should be addressed when all are waived."""
        mock_rows = [
            {
                "finding_id": finding_ids[0],
                "status": "waived",
                "severity": "low",
                "is_blocking": False,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids[1],
                "status": "waived",
                "severity": "low",
                "is_blocking": False,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result["addressed"] is True
        assert result["waived_count"] == 2
        assert result["blocking_findings"] == ()

    @pytest.mark.asyncio
    async def test_findings_addressed_when_all_deferred_to_closing(
        self, mock_ctx, deal_id: UUID, finding_ids: list[UUID]
    ):
        """Findings should be addressed when all are deferred to closing."""
        mock_rows = [
            {
                "finding_id": finding_ids[0],
                "status": "deferred_to_closing",
                "severity": "medium",
                "is_blocking": False,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result["addressed"] is True
        assert result["deferred_count"] == 1
        assert result["blocking_findings"] == ()

    @pytest.mark.asyncio
    async def test_findings_addressed_with_mixed_resolved_statuses(
        self, mock_ctx, deal_id: UUID, finding_ids: list[UUID]
    ):
        """Findings should be addressed when mix of remediated/waived/deferred."""
        mock_rows = [
            {
                "finding_id": finding_ids[0],
                "status": "remediated",
                "severity": "high",
                "is_blocking": False,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids[1],
                "status": "waived",
                "severity": "low",
                "is_blocking": False,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids[2],
                "status": "deferred_to_closing",
                "severity": "medium",
                "is_blocking": False,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result["addressed"] is True
        assert result["remediated_count"] == 1
        assert result["waived_count"] == 1
        assert result["deferred_count"] == 1
        assert result["blocking_findings"] == ()

    @pytest.mark.asyncio
    async def test_findings_not_addressed_when_open_items_exist(
        self, mock_ctx, deal_id: UUID, finding_ids: list[UUID]
    ):
        """Findings should NOT be addressed when open items exist."""
        mock_rows = [
            {
                "finding_id": finding_ids[0],
                "status": "open",
                "severity": "high",
                "is_blocking": True,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids[1],
                "status": "remediated",
                "severity": "medium",
                "is_blocking": False,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result["addressed"] is False
        assert result["open_count"] == 1
        assert result["remediated_count"] == 1
        assert finding_ids[0] in result["blocking_findings"]

    @pytest.mark.asyncio
    async def test_findings_not_addressed_when_in_progress_items_exist(
        self, mock_ctx, deal_id: UUID, finding_ids: list[UUID]
    ):
        """Findings should NOT be addressed when in_progress items exist."""
        mock_rows = [
            {
                "finding_id": finding_ids[0],
                "status": "in_progress",
                "severity": "medium",
                "is_blocking": False,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids[1],
                "status": "waived",
                "severity": "low",
                "is_blocking": False,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result["addressed"] is False
        assert result["in_progress_count"] == 1
        assert finding_ids[0] in result["blocking_findings"]

    @pytest.mark.asyncio
    async def test_findings_not_addressed_when_blocked_items_exist(
        self, mock_ctx, deal_id: UUID, finding_ids: list[UUID]
    ):
        """Findings should NOT be addressed when blocked items exist."""
        mock_rows = [
            {
                "finding_id": finding_ids[0],
                "status": "blocked",
                "severity": "critical",
                "is_blocking": True,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids[1],
                "status": "remediated",
                "severity": "high",
                "is_blocking": False,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result["addressed"] is False
        assert result["blocked_count"] == 1
        assert finding_ids[0] in result["blocking_findings"]

    @pytest.mark.asyncio
    async def test_findings_addressed_when_no_findings_exist(self, mock_ctx, deal_id: UUID):
        """Findings should be addressed (vacuously true) when no findings exist."""
        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = []
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result["addressed"] is True
        assert result["total_findings"] == 0
        assert result["open_count"] == 0
        assert result["in_progress_count"] == 0
        assert result["remediated_count"] == 0
        assert result["waived_count"] == 0
        assert result["blocked_count"] == 0
        assert result["deferred_count"] == 0
        assert result["blocking_findings"] == ()
        assert result["evidence_hash"] is None

    @pytest.mark.asyncio
    async def test_multiple_blocking_findings_all_tracked(
        self, mock_ctx, deal_id: UUID, finding_ids: list[UUID]
    ):
        """All blocking findings should be tracked."""
        mock_rows = [
            {
                "finding_id": finding_ids[0],
                "status": "open",
                "severity": "high",
                "is_blocking": True,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids[1],
                "status": "in_progress",
                "severity": "medium",
                "is_blocking": False,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids[2],
                "status": "blocked",
                "severity": "critical",
                "is_blocking": True,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result["addressed"] is False
        assert len(result["blocking_findings"]) == 3
        assert finding_ids[0] in result["blocking_findings"]
        assert finding_ids[1] in result["blocking_findings"]
        assert finding_ids[2] in result["blocking_findings"]

    @pytest.mark.asyncio
    async def test_counts_are_correct_for_all_statuses(self, mock_ctx, deal_id: UUID):
        """All status counts should be correctly tallied."""
        finding_ids_local = [uuid4() for _ in range(6)]
        mock_rows = [
            {
                "finding_id": finding_ids_local[0],
                "status": "open",
                "severity": "high",
                "is_blocking": True,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids_local[1],
                "status": "in_progress",
                "severity": "medium",
                "is_blocking": False,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids_local[2],
                "status": "remediated",
                "severity": "low",
                "is_blocking": False,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids_local[3],
                "status": "waived",
                "severity": "low",
                "is_blocking": False,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids_local[4],
                "status": "blocked",
                "severity": "critical",
                "is_blocking": True,
                "updated_at": None,
            },
            {
                "finding_id": finding_ids_local[5],
                "status": "deferred_to_closing",
                "severity": "medium",
                "is_blocking": False,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result["total_findings"] == 6
        assert result["open_count"] == 1
        assert result["in_progress_count"] == 1
        assert result["remediated_count"] == 1
        assert result["waived_count"] == 1
        assert result["blocked_count"] == 1
        assert result["deferred_count"] == 1

    @pytest.mark.asyncio
    async def test_evidence_hash_is_deterministic(
        self, mock_ctx, deal_id: UUID, finding_ids: list[UUID]
    ):
        """Evidence hash should be deterministic for same data."""
        mock_rows = [
            {
                "finding_id": finding_ids[0],
                "status": "remediated",
                "severity": "high",
                "is_blocking": False,
                "updated_at": None,
            },
        ]

        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = mock_rows
            result1 = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)
            result2 = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert result1["evidence_hash"] == result2["evidence_hash"]

    @pytest.mark.asyncio
    async def test_result_is_dict(self, mock_ctx, deal_id: UUID):
        """Result should be a dictionary."""
        with patch(
            "canon_vocab_corporate.phrases.derive_conditional_findings_addressed.fetch"
        ) as mock_fetch:
            mock_fetch.return_value = []
            result = await derive_conditional_findings_addressed({"deal_id": deal_id}, mock_ctx)

        assert isinstance(result, dict)
