"""Tests for derive_clean_team_required feature.

This tests the anti-gaming derivation that determines whether clean team
access controls are required based on data categories present in a deal.

Regulatory Context:
    - Hart-Scott-Rodino Act (HSR) - antitrust filing/waiting
    - Sherman Act Section 1 - information sharing restrictions
    - FTC/DOJ Merger Guidelines - gun-jumping prevention
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from canon_vocab_corporate import CleanTeamReason, derive_clean_team_required

if TYPE_CHECKING:
    from uuid import UUID


class TestDeriveCleanTeamRequired:
    """Tests for derive_clean_team_required derivation function."""

    @pytest.mark.asyncio
    async def test_clean_team_required_when_competitive_pricing_present(
        self, mock_ctx, deal_id: UUID
    ):
        """Clean team should be required when competitive pricing data present.

        Competitive pricing is the most severe trigger (direct price-fixing risk).
        """
        mock_rows = [
            {
                "category_name": "competitive_pricing",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
            {
                "category_name": "general_info",
                "sensitivity_level": "confidential",
                "document_id": "doc-2",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert isinstance(result, dict)
        assert result["deal_id"] == deal_id
        assert result["required"] is True
        assert result["reason"] == CleanTeamReason.COMPETITIVE_PRICING
        assert "competitive_pricing" in result["sensitivity_triggers"]
        assert result["evidence_hash"] is not None
        assert result["derived_at"] is not None

    @pytest.mark.asyncio
    async def test_clean_team_required_when_customer_lists_present(self, mock_ctx, deal_id: UUID):
        """Clean team should be required when customer lists present.

        Customer lists carry market allocation risk (Sherman Act).
        """
        mock_rows = [
            {
                "category_name": "customer_lists",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        assert result["reason"] == CleanTeamReason.CUSTOMER_LISTS
        assert "customer_lists" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_clean_team_required_when_strategic_roadmap_present(
        self, mock_ctx, deal_id: UUID
    ):
        """Clean team should be required when strategic roadmap present.

        Strategic roadmap creates coordination risk.
        """
        mock_rows = [
            {
                "category_name": "strategic_roadmap",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        assert result["reason"] == CleanTeamReason.STRATEGIC_ROADMAP
        assert "strategic_roadmap" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_clean_team_required_when_supplier_terms_present(self, mock_ctx, deal_id: UUID):
        """Clean team should be required when supplier terms present."""
        mock_rows = [
            {
                "category_name": "supplier_terms",
                "sensitivity_level": "highly_confidential",
                "document_id": "doc-1",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        assert result["reason"] == CleanTeamReason.SUPPLIER_TERMS
        assert "supplier_terms" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_clean_team_required_when_product_margins_present(self, mock_ctx, deal_id: UUID):
        """Clean team should be required when product margins present."""
        mock_rows = [
            {
                "category_name": "product_margins",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        assert result["reason"] == CleanTeamReason.PRODUCT_MARGINS
        assert "product_margins" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_clean_team_required_when_market_strategy_present(self, mock_ctx, deal_id: UUID):
        """Clean team should be required when market strategy present."""
        mock_rows = [
            {
                "category_name": "market_strategy",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        assert result["reason"] == CleanTeamReason.MARKET_STRATEGY
        assert "market_strategy" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_clean_team_required_for_bidding_history(self, mock_ctx, deal_id: UUID):
        """Clean team should be required when bidding history present."""
        mock_rows = [
            {
                "category_name": "bidding_history",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        assert "bidding_history" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_clean_team_required_for_cost_structures(self, mock_ctx, deal_id: UUID):
        """Clean team should be required when cost structures present."""
        mock_rows = [
            {
                "category_name": "cost_structures",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        assert "cost_structures" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_clean_team_required_for_capacity_plans(self, mock_ctx, deal_id: UUID):
        """Clean team should be required when capacity plans present."""
        mock_rows = [
            {
                "category_name": "capacity_plans",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        assert "capacity_plans" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_clean_team_not_required_for_non_sensitive_data(self, mock_ctx, deal_id: UUID):
        """Clean team should NOT be required for non-sensitive data categories."""
        mock_rows = [
            {
                "category_name": "general_corporate_info",
                "sensitivity_level": "confidential",
                "document_id": "doc-1",
            },
            {
                "category_name": "public_filings",
                "sensitivity_level": "public",
                "document_id": "doc-2",
            },
            {
                "category_name": "organizational_charts",
                "sensitivity_level": "confidential",
                "document_id": "doc-3",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is False
        assert result["reason"] == CleanTeamReason.NOT_REQUIRED
        assert result["sensitivity_triggers"] == ()
        assert len(result["data_categories"]) == 3
        assert result["evidence_hash"] is not None

    @pytest.mark.asyncio
    async def test_clean_team_not_required_when_no_data_categories(self, mock_ctx, deal_id: UUID):
        """Clean team should NOT be required when no data categories exist."""
        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = []
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is False
        assert result["reason"] == CleanTeamReason.NOT_REQUIRED
        assert result["data_categories"] == ()
        assert result["sensitivity_triggers"] == ()
        assert result["evidence_hash"] is None

    @pytest.mark.asyncio
    async def test_employee_compensation_triggers_in_cross_competitor_deal(
        self, mock_ctx, deal_id: UUID
    ):
        """Employee compensation should trigger clean team in cross-competitor deals."""
        mock_data_rows = [
            {
                "category_name": "employee_compensation",
                "sensitivity_level": "highly_confidential",
                "document_id": "doc-1",
            },
        ]
        mock_deal_rows = [{"is_cross_competitor": True}]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            # First call returns data categories, second returns deal info
            mock_fetch.side_effect = [mock_data_rows, mock_deal_rows]
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        assert result["reason"] == CleanTeamReason.EMPLOYEE_COMPENSATION
        assert "employee_compensation" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_employee_compensation_not_trigger_in_non_competitor_deal(
        self, mock_ctx, deal_id: UUID
    ):
        """Employee compensation should NOT trigger clean team in non-competitor deals."""
        mock_data_rows = [
            {
                "category_name": "employee_compensation",
                "sensitivity_level": "highly_confidential",
                "document_id": "doc-1",
            },
        ]
        mock_deal_rows = [{"is_cross_competitor": False}]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.side_effect = [mock_data_rows, mock_deal_rows]
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is False
        assert result["reason"] == CleanTeamReason.NOT_REQUIRED
        assert "employee_compensation" not in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_multiple_triggers_returns_highest_priority_reason(self, mock_ctx, deal_id: UUID):
        """When multiple triggers present, highest priority reason should be returned.

        Priority: competitive_pricing > customer_lists > strategic_roadmap > others
        """
        mock_rows = [
            {
                "category_name": "customer_lists",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
            {
                "category_name": "competitive_pricing",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-2",
            },
            {
                "category_name": "strategic_roadmap",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-3",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["required"] is True
        # Competitive pricing has highest priority
        assert result["reason"] == CleanTeamReason.COMPETITIVE_PRICING
        # All triggers should be included
        assert "competitive_pricing" in result["sensitivity_triggers"]
        assert "customer_lists" in result["sensitivity_triggers"]
        assert "strategic_roadmap" in result["sensitivity_triggers"]

    @pytest.mark.asyncio
    async def test_evidence_hash_is_deterministic(self, mock_ctx, deal_id: UUID):
        """Evidence hash should be deterministic for same data."""
        mock_rows = [
            {
                "category_name": "competitive_pricing",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result1 = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)
            result2 = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result1["evidence_hash"] == result2["evidence_hash"]

    @pytest.mark.asyncio
    async def test_evidence_hash_differs_for_different_data(self, mock_ctx, deal_id: UUID):
        """Evidence hash should differ when data changes."""
        mock_rows_1 = [
            {
                "category_name": "competitive_pricing",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-1",
            },
        ]
        mock_rows_2 = [
            {
                "category_name": "customer_lists",
                "sensitivity_level": "competitively_sensitive",
                "document_id": "doc-2",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows_1
            result1 = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

            mock_fetch.return_value = mock_rows_2
            result2 = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result1["evidence_hash"] != result2["evidence_hash"]

    @pytest.mark.asyncio
    async def test_data_categories_are_sorted_and_unique(self, mock_ctx, deal_id: UUID):
        """Data categories should be sorted and deduplicated."""
        mock_rows = [
            {
                "category_name": "zebra_data",
                "sensitivity_level": "confidential",
                "document_id": "doc-1",
            },
            {
                "category_name": "alpha_data",
                "sensitivity_level": "confidential",
                "document_id": "doc-2",
            },
            {
                "category_name": "alpha_data",  # duplicate
                "sensitivity_level": "confidential",
                "document_id": "doc-3",
            },
        ]

        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = mock_rows
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert result["data_categories"] == ("alpha_data", "zebra_data")

    @pytest.mark.asyncio
    async def test_result_is_dict(self, mock_ctx, deal_id: UUID):
        """Result should be a dictionary."""
        with patch("canon_vocab_corporate.phrases.derive_clean_team_required.fetch") as mock_fetch:
            mock_fetch.return_value = []
            result = await derive_clean_team_required({"deal_id": deal_id}, mock_ctx)

        assert isinstance(result, dict)
