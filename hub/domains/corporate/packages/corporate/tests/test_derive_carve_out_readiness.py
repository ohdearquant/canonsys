"""Tests for derive_carve_out_readiness feature.

This tests the anti-gaming derivation that determines whether regulatory
carve-out requirements are ready for closing.

Regulatory Context:
    - FTC/DOJ divestiture requirements
    - Regulatory approval conditions
    - Competition law remedies
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from canon_vocab_corporate import CarveOutStatus, derive_carve_out_readiness

if TYPE_CHECKING:
    from uuid import UUID


class TestDeriveCarveOutReadiness:
    """Tests for derive_carve_out_readiness derivation function."""

    @pytest.mark.asyncio
    async def test_carve_out_ready_when_all_components_approved(
        self, mock_ctx, deal_id: UUID, carve_out_id: UUID
    ):
        """Carve-out should be ready when all components are approved."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "it_systems_separation",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "employee_transition_plan",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "customer_contract_assignment",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "supplier_contract_assignment",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "intellectual_property_allocation",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "regulatory_licenses_transfer",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "real_estate_allocation",
                "component_status": "approved",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert isinstance(result, dict)
        assert result["deal_id"] == deal_id
        assert result["ready"] is True
        assert result["status"] == CarveOutStatus.APPROVED
        assert result["missing_components"] == ()
        assert result["blocking_issues"] == ()
        assert result["evidence_hash"] is not None
        assert result["derived_at"] is not None

    @pytest.mark.asyncio
    async def test_carve_out_ready_with_not_applicable_components(
        self, mock_ctx, deal_id: UUID, carve_out_id: UUID
    ):
        """Carve-out should be ready when components are approved or not_applicable."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "it_systems_separation",
                "component_status": "not_applicable",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "employee_transition_plan",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "customer_contract_assignment",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "supplier_contract_assignment",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "intellectual_property_allocation",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "regulatory_licenses_transfer",
                "component_status": "not_applicable",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "real_estate_allocation",
                "component_status": "approved",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result["ready"] is True
        assert "it_systems_separation" in result["ready_components"]
        assert "regulatory_licenses_transfer" in result["ready_components"]

    @pytest.mark.asyncio
    async def test_carve_out_not_ready_when_components_in_progress(
        self, mock_ctx, deal_id: UUID, carve_out_id: UUID
    ):
        """Carve-out should NOT be ready when components are in progress."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "in_progress",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "in_progress",
                "regulatory_deadline": None,
                "component_name": "it_systems_separation",
                "component_status": "in_progress",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result["ready"] is False
        assert "it_systems_separation" in result["missing_components"]

    @pytest.mark.asyncio
    async def test_carve_out_not_ready_when_components_not_started(
        self, mock_ctx, deal_id: UUID, carve_out_id: UUID
    ):
        """Carve-out should NOT be ready when components not started."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "planning",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "not_started",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result["ready"] is False
        assert "standalone_financials" in result["missing_components"]

    @pytest.mark.asyncio
    async def test_carve_out_not_ready_when_components_ready_for_review(
        self, mock_ctx, deal_id: UUID, carve_out_id: UUID
    ):
        """Carve-out should NOT be ready when components pending review."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "ready_for_review",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "ready_for_review",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result["ready"] is False
        assert "standalone_financials" in result["missing_components"]

    @pytest.mark.asyncio
    async def test_carve_out_not_ready_when_components_blocked(
        self, mock_ctx, deal_id: UUID, carve_out_id: UUID
    ):
        """Carve-out should NOT be ready when components are blocked."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "blocked",
                "regulatory_deadline": None,
                "component_name": "it_systems_separation",
                "component_status": "blocked",
                "blocking_issues": ["Vendor contract dispute"],
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result["ready"] is False
        assert result["status"] == CarveOutStatus.BLOCKED
        assert "Vendor contract dispute" in result["blocking_issues"]

    @pytest.mark.asyncio
    async def test_carve_out_not_required_when_deal_does_not_require(self, mock_ctx, deal_id: UUID):
        """Carve-out should be ready (N/A) when deal doesn't require carve-out."""
        mock_deal_rows = [{"requires_carve_out": False}]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            # First call returns empty carve-out rows, second returns deal info
            mock_fetch.side_effect = [[], mock_deal_rows]
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result["ready"] is True
        assert result["status"] == CarveOutStatus.NOT_APPLICABLE
        assert result["required_components"] == ()
        assert result["missing_components"] == ()

    @pytest.mark.asyncio
    async def test_carve_out_not_started_when_required_but_no_records(
        self, mock_ctx, deal_id: UUID
    ):
        """Carve-out should not be ready when required but not initiated."""
        mock_deal_rows = [{"requires_carve_out": True}]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            # First call returns empty carve-out rows, second returns deal info
            mock_fetch.side_effect = [[], mock_deal_rows]
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result["ready"] is False
        assert result["status"] == CarveOutStatus.NOT_STARTED
        # Should list all standard required components
        assert "standalone_financials" in result["required_components"]
        assert "it_systems_separation" in result["required_components"]
        assert "employee_transition_plan" in result["required_components"]
        assert "Carve-out not initiated" in result["blocking_issues"]

    @pytest.mark.asyncio
    async def test_missing_standard_components_detected(
        self, mock_ctx, deal_id: UUID, carve_out_id: UUID
    ):
        """Should detect missing standard components not in database."""
        # Only include some of the 8 standard components
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "in_progress",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "in_progress",
                "regulatory_deadline": None,
                "component_name": "it_systems_separation",
                "component_status": "approved",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result["ready"] is False
        # Missing standard components should be detected
        assert "employee_transition_plan" in result["missing_components"]
        assert "customer_contract_assignment" in result["missing_components"]
        assert "supplier_contract_assignment" in result["missing_components"]
        assert "intellectual_property_allocation" in result["missing_components"]
        assert "regulatory_licenses_transfer" in result["missing_components"]
        assert "real_estate_allocation" in result["missing_components"]

    @pytest.mark.asyncio
    async def test_regulatory_deadline_captured(self, mock_ctx, deal_id: UUID, carve_out_id: UUID):
        """Should capture regulatory deadline from carve-out record."""
        deadline = datetime(2025, 6, 30, tzinfo=UTC)
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "in_progress",
                "regulatory_deadline": deadline,
                "component_name": "standalone_financials",
                "component_status": "approved",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result["regulatory_deadline"] == deadline

    @pytest.mark.asyncio
    async def test_blocking_issues_as_list(self, mock_ctx, deal_id: UUID, carve_out_id: UUID):
        """Should handle blocking_issues as a list."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "blocked",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "blocked",
                "blocking_issues": ["Issue 1", "Issue 2"],
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert "Issue 1" in result["blocking_issues"]
        assert "Issue 2" in result["blocking_issues"]

    @pytest.mark.asyncio
    async def test_blocking_issues_as_string(self, mock_ctx, deal_id: UUID, carve_out_id: UUID):
        """Should handle blocking_issues as a string."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "blocked",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "blocked",
                "blocking_issues": "Single issue string",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert "Single issue string" in result["blocking_issues"]

    @pytest.mark.asyncio
    async def test_components_are_sorted_and_unique(
        self, mock_ctx, deal_id: UUID, carve_out_id: UUID
    ):
        """Components should be sorted and deduplicated."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "zebra_component",
                "component_status": "approved",
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "alpha_component",
                "component_status": "approved",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        # Verify ready_components are sorted
        ready_list = list(result["ready_components"])
        assert ready_list == sorted(ready_list)

    @pytest.mark.asyncio
    async def test_evidence_hash_is_deterministic(
        self, mock_ctx, deal_id: UUID, carve_out_id: UUID
    ):
        """Evidence hash should be deterministic for same data."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "approved",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "approved",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result1 = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)
            result2 = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert result1["evidence_hash"] == result2["evidence_hash"]

    @pytest.mark.asyncio
    async def test_result_is_dict(self, mock_ctx, deal_id: UUID):
        """Result should be a dictionary."""
        mock_deal_rows = [{"requires_carve_out": False}]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.side_effect = [[], mock_deal_rows]
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_handles_null_component_name(self, mock_ctx, deal_id: UUID, carve_out_id: UUID):
        """Should handle rows with null component_name gracefully."""
        mock_rows = [
            {
                "carve_out_id": carve_out_id,
                "overall_status": "in_progress",
                "regulatory_deadline": None,
                "component_name": None,  # Null component
                "component_status": None,
                "blocking_issues": None,
            },
            {
                "carve_out_id": carve_out_id,
                "overall_status": "in_progress",
                "regulatory_deadline": None,
                "component_name": "standalone_financials",
                "component_status": "approved",
                "blocking_issues": None,
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_carve_out_readiness.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_carve_out_readiness({"deal_id": deal_id}, mock_ctx)

        # Should not crash and should include the valid component
        assert "standalone_financials" in result["ready_components"]
