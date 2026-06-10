"""Tests for pattern detection wrappers.

Tests surface-specific pattern detection functions:
- derive_manager_bypass_count_12m
- derive_manager_salary_exception_count_12m
- check_prior_escalations
- check_prior_exemptions
- check_prior_bypasses
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from canon_vocab_pattern import (
    check_prior_bypasses,
    check_prior_escalations,
    check_prior_exemptions,
    derive_manager_bypass_count_12m,
    derive_manager_salary_exception_count_12m,
)


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    ctx.conn = None
    return ctx


@pytest.fixture
def mock_threshold_result():
    """Factory for threshold result dicts."""

    def _make(entity_id, count=0, threshold=3, exceeded=False, action_type="TEST"):
        return {
            "exceeded": exceeded,
            "count": count,
            "threshold": threshold,
            "entity_id": entity_id,
            "action_type": action_type,
            "lookback_days": 365,
        }

    return _make


@pytest.fixture
def mock_count_result():
    """Factory for count result dicts."""

    def _make(entity_id, count=0, action_type="TEST", days=30):
        now = datetime.now(UTC)
        return {
            "count": count,
            "entity_id": entity_id,
            "action_type": action_type,
            "lookback_days": days,
            "window_start": now,
            "window_end": now,
        }

    return _make


# =============================================================================
# this surface: Manager Posting Bypass Tracking
# =============================================================================


class TestDeriveManagerBypassCount12m:
    """Tests for derive_manager_bypass_count_12m function."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_correct_structure(self, mock_ctx, mock_threshold_result):
        """Should return dict with correct structure."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_bypass_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id, count=0),
        ):
            result = await derive_manager_bypass_count_12m({"manager_id": manager_id}, mock_ctx)

        assert isinstance(result, dict)
        assert result["manager_id"] == manager_id
        assert result["period_months"] == 12

    @pytest.mark.asyncio
    async def test_uses_posting_bypass_action_type(self, mock_ctx, mock_threshold_result):
        """Should query for POSTING_BYPASS action type."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_bypass_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id),
        ) as mock_check:
            await derive_manager_bypass_count_12m({"manager_id": manager_id}, mock_ctx)

        mock_check.assert_called_once()
        call_args = mock_check.call_args[0]
        # First arg is the Specs object
        assert call_args[0].action_type == "POSTING_BYPASS"

    @pytest.mark.asyncio
    async def test_uses_365_day_lookback(self, mock_ctx, mock_threshold_result):
        """Should use 365 days for 12-month period."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_bypass_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id),
        ) as mock_check:
            await derive_manager_bypass_count_12m({"manager_id": manager_id}, mock_ctx)

        call_args = mock_check.call_args[0]
        assert call_args[0].lookback_days == 365

    @pytest.mark.asyncio
    async def test_default_threshold_is_3(self, mock_ctx, mock_threshold_result):
        """Default threshold should be 3."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_bypass_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id),
        ) as mock_check:
            await derive_manager_bypass_count_12m({"manager_id": manager_id}, mock_ctx)

        call_args = mock_check.call_args[0]
        assert call_args[0].threshold == 3

    @pytest.mark.asyncio
    async def test_custom_threshold(self, mock_ctx, mock_threshold_result):
        """Should accept custom threshold."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_bypass_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id, threshold=5),
        ) as mock_check:
            result = await derive_manager_bypass_count_12m(
                {"manager_id": manager_id, "threshold": 5}, mock_ctx
            )

        call_args = mock_check.call_args[0]
        assert call_args[0].threshold == 5
        assert result["threshold"] == 5

    @pytest.mark.asyncio
    async def test_count_below_threshold(self, mock_ctx, mock_threshold_result):
        """Should report not exceeded when count < threshold."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_bypass_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id, count=2, exceeded=False),
        ):
            result = await derive_manager_bypass_count_12m({"manager_id": manager_id}, mock_ctx)

        assert result["count"] == 2
        assert result["exceeds_threshold"] is False

    @pytest.mark.asyncio
    async def test_count_at_threshold(self, mock_ctx, mock_threshold_result):
        """Should report exceeded when count == threshold."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_bypass_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id, count=3, exceeded=True),
        ):
            result = await derive_manager_bypass_count_12m({"manager_id": manager_id}, mock_ctx)

        assert result["count"] == 3
        assert result["exceeds_threshold"] is True

    @pytest.mark.asyncio
    async def test_count_above_threshold(self, mock_ctx, mock_threshold_result):
        """Should report exceeded when count > threshold."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_bypass_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id, count=5, exceeded=True),
        ):
            result = await derive_manager_bypass_count_12m({"manager_id": manager_id}, mock_ctx)

        assert result["count"] == 5
        assert result["exceeds_threshold"] is True

    @pytest.mark.asyncio
    async def test_zero_bypasses(self, mock_ctx, mock_threshold_result):
        """Should handle zero bypasses correctly."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_bypass_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id, count=0, exceeded=False),
        ):
            result = await derive_manager_bypass_count_12m({"manager_id": manager_id}, mock_ctx)

        assert result["count"] == 0
        assert result["exceeds_threshold"] is False


# =============================================================================
# this surface: Manager Salary Exception Tracking
# =============================================================================


class TestDeriveManagerSalaryExceptionCount12m:
    """Tests for derive_manager_salary_exception_count_12m function."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_correct_structure(self, mock_ctx, mock_threshold_result):
        """Should return dict with correct structure."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_salary_exception_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id, count=0),
        ):
            result = await derive_manager_salary_exception_count_12m(
                {"manager_id": manager_id}, mock_ctx
            )

        assert isinstance(result, dict)
        assert result["manager_id"] == manager_id
        assert result["period_months"] == 12

    @pytest.mark.asyncio
    async def test_uses_salary_exception_action_type(self, mock_ctx, mock_threshold_result):
        """Should query for SALARY_EXCEPTION action type."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_salary_exception_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id),
        ) as mock_check:
            await derive_manager_salary_exception_count_12m({"manager_id": manager_id}, mock_ctx)

        call_args = mock_check.call_args[0]
        assert call_args[0].action_type == "SALARY_EXCEPTION"

    @pytest.mark.asyncio
    async def test_uses_365_day_lookback(self, mock_ctx, mock_threshold_result):
        """Should use 365 days for 12-month period."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_salary_exception_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id),
        ) as mock_check:
            await derive_manager_salary_exception_count_12m({"manager_id": manager_id}, mock_ctx)

        call_args = mock_check.call_args[0]
        assert call_args[0].lookback_days == 365

    @pytest.mark.asyncio
    async def test_default_threshold_is_3(self, mock_ctx, mock_threshold_result):
        """Default threshold should be 3."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_salary_exception_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id),
        ) as mock_check:
            await derive_manager_salary_exception_count_12m({"manager_id": manager_id}, mock_ctx)

        call_args = mock_check.call_args[0]
        assert call_args[0].threshold == 3

    @pytest.mark.asyncio
    async def test_custom_threshold(self, mock_ctx, mock_threshold_result):
        """Should accept custom threshold."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_salary_exception_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id, threshold=5),
        ) as mock_check:
            result = await derive_manager_salary_exception_count_12m(
                {"manager_id": manager_id, "threshold": 5}, mock_ctx
            )

        call_args = mock_check.call_args[0]
        assert call_args[0].threshold == 5
        assert result["threshold"] == 5

    @pytest.mark.asyncio
    async def test_pay_equity_scenario_threshold_exceeded(self, mock_ctx, mock_threshold_result):
        """Test pay equity scenario: 3+ exceptions triggers review."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_manager_salary_exception_count_12m.check_pattern_threshold",
            new_callable=AsyncMock,
            return_value=mock_threshold_result(manager_id, count=4, exceeded=True),
        ):
            result = await derive_manager_salary_exception_count_12m(
                {"manager_id": manager_id}, mock_ctx
            )

        # Manager has 4 salary exceptions in 12 months - needs review
        assert result["count"] == 4
        assert result["exceeds_threshold"] is True
        # This would trigger compensation committee review


# =============================================================================
# this surface: Prior Privilege Escalation Tracking
# =============================================================================


class TestCheckPriorEscalations:
    """Tests for check_prior_escalations function."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_correct_structure(self, mock_ctx, mock_count_result):
        """Should return dict with correct structure."""
        subject_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_escalations.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=0),
        ):
            result = await check_prior_escalations({"subject_id": subject_id, "days": 90}, mock_ctx)

        assert isinstance(result, dict)
        assert result["subject_id"] == subject_id

    @pytest.mark.asyncio
    async def test_uses_privilege_escalation_action_type(self, mock_ctx, mock_count_result):
        """Should query for PRIVILEGE_ESCALATION action type."""
        subject_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_escalations.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, action_type="PRIVILEGE_ESCALATION"),
        ) as mock_count:
            await check_prior_escalations({"subject_id": subject_id, "days": 90}, mock_ctx)

        call_args = mock_count.call_args[0]
        assert call_args[0].action_type == "PRIVILEGE_ESCALATION"

    @pytest.mark.asyncio
    async def test_uses_provided_lookback_days(self, mock_ctx, mock_count_result):
        """Should use provided days parameter."""
        subject_id = uuid4()
        lookback_days = 180

        with patch(
            "canon_vocab_pattern.phrases.check_prior_escalations.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, days=lookback_days),
        ) as mock_count:
            await check_prior_escalations(
                {"subject_id": subject_id, "days": lookback_days}, mock_ctx
            )

        call_args = mock_count.call_args[0]
        assert call_args[0].lookback_days == lookback_days

    @pytest.mark.asyncio
    async def test_zero_escalations(self, mock_ctx, mock_count_result):
        """Should handle zero escalations."""
        subject_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_escalations.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=0),
        ):
            result = await check_prior_escalations({"subject_id": subject_id, "days": 90}, mock_ctx)

        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_multiple_escalations(self, mock_ctx, mock_count_result):
        """Should report multiple escalations."""
        subject_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_escalations.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=3),
        ):
            result = await check_prior_escalations({"subject_id": subject_id, "days": 90}, mock_ctx)

        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_access_control_abuse_scenario(self, mock_ctx, mock_count_result):
        """Test access control scenario: frequent escalations suggest permanent grant needed."""
        subject_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_escalations.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=5),
        ):
            result = await check_prior_escalations({"subject_id": subject_id, "days": 90}, mock_ctx)

        # 5 escalations in 90 days - should consider permanent permission
        assert result["count"] >= 2


# =============================================================================
# this surface: Prior MFA Exemption Tracking
# =============================================================================


class TestCheckPriorExemptions:
    """Tests for check_prior_exemptions function."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_correct_structure(self, mock_ctx, mock_count_result):
        """Should return dict with correct structure."""
        subject_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_exemptions.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=0),
        ):
            result = await check_prior_exemptions({"subject_id": subject_id, "days": 30}, mock_ctx)

        assert isinstance(result, dict)
        assert result["subject_id"] == subject_id

    @pytest.mark.asyncio
    async def test_uses_mfa_exemption_action_type(self, mock_ctx, mock_count_result):
        """Should query for MFA_EXEMPTION action type."""
        subject_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_exemptions.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, action_type="MFA_EXEMPTION"),
        ) as mock_count:
            await check_prior_exemptions({"subject_id": subject_id, "days": 30}, mock_ctx)

        call_args = mock_count.call_args[0]
        assert call_args[0].action_type == "MFA_EXEMPTION"

    @pytest.mark.asyncio
    async def test_uses_provided_lookback_days(self, mock_ctx, mock_count_result):
        """Should use provided days parameter."""
        subject_id = uuid4()
        lookback_days = 60

        with patch(
            "canon_vocab_pattern.phrases.check_prior_exemptions.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, days=lookback_days),
        ) as mock_count:
            await check_prior_exemptions(
                {"subject_id": subject_id, "days": lookback_days}, mock_ctx
            )

        call_args = mock_count.call_args[0]
        assert call_args[0].lookback_days == lookback_days

    @pytest.mark.asyncio
    async def test_zero_exemptions(self, mock_ctx, mock_count_result):
        """Should handle zero exemptions."""
        subject_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_exemptions.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=0),
        ):
            result = await check_prior_exemptions({"subject_id": subject_id, "days": 30}, mock_ctx)

        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_mfa_abuse_scenario(self, mock_ctx, mock_count_result):
        """Test MFA scenario: multiple exemptions may indicate device issues or social engineering."""
        subject_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_exemptions.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=3),
        ):
            result = await check_prior_exemptions({"subject_id": subject_id, "days": 30}, mock_ctx)

        # 3 MFA exemptions in 30 days - suspicious pattern
        assert result["count"] >= 2


# =============================================================================
# this surface: Prior Application Bypass Tracking
# =============================================================================


class TestCheckPriorBypasses:
    """Tests for check_prior_bypasses function."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_correct_structure(self, mock_ctx, mock_count_result):
        """Should return dict with correct structure."""
        subject_id = uuid4()
        app_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_bypasses.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=0),
        ):
            result = await check_prior_bypasses(
                {"subject_id": subject_id, "app_id": app_id, "days": 30}, mock_ctx
            )

        assert isinstance(result, dict)
        assert result["subject_id"] == subject_id

    @pytest.mark.asyncio
    async def test_encodes_app_id_in_action_type(self, mock_ctx, mock_count_result):
        """Should encode app_id in action_type for app-scoped detection."""
        subject_id = uuid4()
        app_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_bypasses.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, action_type=f"APP_BYPASS:{app_id}"),
        ) as mock_count:
            await check_prior_bypasses(
                {"subject_id": subject_id, "app_id": app_id, "days": 30}, mock_ctx
            )

        call_args = mock_count.call_args[0]
        assert call_args[0].action_type == f"APP_BYPASS:{app_id}"

    @pytest.mark.asyncio
    async def test_uses_provided_lookback_days(self, mock_ctx, mock_count_result):
        """Should use provided days parameter."""
        subject_id = uuid4()
        app_id = uuid4()
        lookback_days = 45

        with patch(
            "canon_vocab_pattern.phrases.check_prior_bypasses.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, days=lookback_days),
        ) as mock_count:
            await check_prior_bypasses(
                {"subject_id": subject_id, "app_id": app_id, "days": lookback_days},
                mock_ctx,
            )

        call_args = mock_count.call_args[0]
        assert call_args[0].lookback_days == lookback_days

    @pytest.mark.asyncio
    async def test_zero_bypasses(self, mock_ctx, mock_count_result):
        """Should handle zero bypasses."""
        subject_id = uuid4()
        app_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_bypasses.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=0),
        ):
            result = await check_prior_bypasses(
                {"subject_id": subject_id, "app_id": app_id, "days": 30}, mock_ctx
            )

        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_app_scoped_bypass_detection(self, mock_ctx, mock_count_result):
        """Test app-scoped bypass: patterns isolated to specific apps."""
        subject_id = uuid4()
        salesforce_app_id = uuid4()
        workday_app_id = uuid4()

        # Each app has its own bypass pattern detection
        with patch(
            "canon_vocab_pattern.phrases.check_prior_bypasses.derive_prior_action_count",
            new_callable=AsyncMock,
        ) as mock_count:
            # Salesforce bypasses
            mock_count.return_value = mock_count_result(
                subject_id, count=2, action_type=f"APP_BYPASS:{salesforce_app_id}"
            )
            sf_result = await check_prior_bypasses(
                {"subject_id": subject_id, "app_id": salesforce_app_id, "days": 30},
                mock_ctx,
            )

            # Workday bypasses
            mock_count.return_value = mock_count_result(
                subject_id, count=0, action_type=f"APP_BYPASS:{workday_app_id}"
            )
            wd_result = await check_prior_bypasses(
                {"subject_id": subject_id, "app_id": workday_app_id, "days": 30},
                mock_ctx,
            )

        # Different apps have different bypass counts
        assert sf_result["count"] == 2
        assert wd_result["count"] == 0

    @pytest.mark.asyncio
    async def test_bypass_abuse_scenario(self, mock_ctx, mock_count_result):
        """Test bypass abuse: multiple bypasses for same app suggest improper access needs."""
        subject_id = uuid4()
        app_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_prior_bypasses.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(subject_id, count=4),
        ):
            result = await check_prior_bypasses(
                {"subject_id": subject_id, "app_id": app_id, "days": 30}, mock_ctx
            )

        # 4 bypasses in 30 days for same app - needs security review
        assert result["count"] >= 2
