"""Timing service - thin wrapper over timing phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

Regulatory basis:
    - FCRA Section 1681b(b)(3): Waiting period requirements
    - FCRA Section 1681m: Pre-adverse action notice timing
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    check_waiting_period_elapsed,
    get_acknowledgment,
    get_delivery_attempts,
    get_notice,
    get_waiting_period,
    pause_waiting_period,
    resume_waiting_period,
    verify_notice_delivered,
)
from .types import NoticeChannel

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = [
    "CheckWaitingPeriodOptions",
    "GetAcknowledgmentOptions",
    "GetDeliveryAttemptsOptions",
    "GetNoticeOptions",
    "GetWaitingPeriodOptions",
    "PauseWaitingPeriodOptions",
    "ResumeWaitingPeriodOptions",
    "TimingService",
    "VerifyNoticeDeliveredOptions",
]


# =============================================================================
# Request Options
# =============================================================================


class GetWaitingPeriodOptions(BaseModel):
    """Options for getting waiting period state."""

    notice_id: UUID


class CheckWaitingPeriodOptions(BaseModel):
    """Options for checking waiting period elapsed."""

    notice_id: UUID
    auto_mark_elapsed: bool = True


class PauseWaitingPeriodOptions(BaseModel):
    """Options for pausing waiting period."""

    notice_id: UUID
    reason: str


class ResumeWaitingPeriodOptions(BaseModel):
    """Options for resuming waiting period."""

    notice_id: UUID


class GetNoticeOptions(BaseModel):
    """Options for getting notice."""

    notice_id: UUID
    include_acknowledgment: bool = False


class GetDeliveryAttemptsOptions(BaseModel):
    """Options for getting delivery attempts."""

    notice_id: UUID


class GetAcknowledgmentOptions(BaseModel):
    """Options for getting acknowledgment."""

    notice_id: UUID


class VerifyNoticeDeliveredOptions(BaseModel):
    """Options for verifying notice delivery."""

    recipient_id: UUID
    notice_type: str
    required_channel: NoticeChannel | None = None


# =============================================================================
# Timing Service
# =============================================================================


class TimingService(CanonService):
    """Timing service - manages waiting periods and notice timing.

    Thin wrapper that delegates to phrase functions.

    Operations:
    - Waiting period: get, check, pause, resume
    - Notice: get, get_deliveries, get_acknowledgment, verify_delivered
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="timing")

    # -------------------------------------------------------------------------
    # Waiting Period Operations
    # -------------------------------------------------------------------------

    @action(skip_evidence=True)
    async def get_waiting_period(self, payload: dict, ctx: RequestContext) -> dict:
        """Get waiting period state for a notice."""
        options = GetWaitingPeriodOptions(**payload)
        result = await get_waiting_period({"notice_id": options.notice_id}, ctx)
        return result

    @action(evidence_type="timing.check_waiting")
    async def check_waiting_period(self, payload: dict, ctx: RequestContext) -> dict:
        """Check if waiting period has elapsed.

        If auto_mark_elapsed is True and period has elapsed,
        emits evidence marking it as elapsed.
        """
        options = CheckWaitingPeriodOptions(**payload)
        result = await check_waiting_period_elapsed(
            {
                "notice_id": options.notice_id,
                "auto_mark_elapsed": options.auto_mark_elapsed,
            },
            ctx,
        )
        return result

    @action(evidence_type="timing.pause_waiting")
    async def pause_waiting_period(self, payload: dict, ctx: RequestContext) -> dict:
        """Pause waiting period clock.

        Used when a dispute is filed and the clock must stop.
        """
        options = PauseWaitingPeriodOptions(**payload)
        result = await pause_waiting_period(
            {
                "notice_id": options.notice_id,
                "reason": options.reason,
            },
            ctx,
        )
        return result

    @action(evidence_type="timing.resume_waiting")
    async def resume_waiting_period(self, payload: dict, ctx: RequestContext) -> dict:
        """Resume paused waiting period.

        Extends ends_at by the pause duration.
        """
        options = ResumeWaitingPeriodOptions(**payload)
        result = await resume_waiting_period({"notice_id": options.notice_id}, ctx)
        return result

    # -------------------------------------------------------------------------
    # Notice Operations
    # -------------------------------------------------------------------------

    @action(skip_evidence=True)
    async def get_notice(self, payload: dict, ctx: RequestContext) -> dict:
        """Get notice by ID with optional acknowledgment."""
        options = GetNoticeOptions(**payload)
        result = await get_notice(
            {
                "notice_id": options.notice_id,
                "include_acknowledgment": options.include_acknowledgment,
            },
            ctx,
        )
        return result

    @action(skip_evidence=True)
    async def get_delivery_attempts(self, payload: dict, ctx: RequestContext) -> dict:
        """Get delivery attempts for a notice."""
        options = GetDeliveryAttemptsOptions(**payload)
        result = await get_delivery_attempts({"notice_id": options.notice_id}, ctx)
        return result

    @action(skip_evidence=True)
    async def get_acknowledgment(self, payload: dict, ctx: RequestContext) -> dict:
        """Get acknowledgment for a notice."""
        options = GetAcknowledgmentOptions(**payload)
        result = await get_acknowledgment({"notice_id": options.notice_id}, ctx)
        return result

    @action(skip_evidence=True)
    async def verify_notice_delivered(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify notice has been delivered to recipient."""
        options = VerifyNoticeDeliveredOptions(**payload)
        result = await verify_notice_delivered(
            {
                "recipient_id": options.recipient_id,
                "notice_type": options.notice_type,
                "required_channel": options.required_channel,
            },
            ctx,
        )
        return result
