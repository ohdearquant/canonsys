"""Timing domain exceptions.

These exceptions are raised by timing features when invariants are violated.
All inherit from TimingViolation (the domain's base exception).

Regulatory basis:
    - FCRA Section 1681b(b)(3): Waiting period requirements
    - FCRA Section 1681m: Pre-adverse action notice timing
    - WARN Act: Notice timing for mass layoffs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import TimingViolation

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = [
    "NoticeNotDeliveredError",
    "NoticeNotFoundError",
    "NoticePrecedenceError",
    "WaitingPeriodNotElapsedError",
    "WaitingPeriodNotFoundError",
    "WaitingPeriodPausedError",
]


class WaitingPeriodNotElapsedError(TimingViolation):
    """Required waiting period has not yet elapsed.

    Raised when: check_waiting_period_elapsed determines the dispute window
    or other required waiting period has not completed.

    Regulatory basis:
    - FCRA Section 1681b(b)(3): "reasonable period" (typically 5 business days)
    - State law variations (California, New York waiting periods)

    Phrase: waiting_period_must_be_elapsed
    """

    default_regulation = "FCRA Section 1681b(b)(3)"
    default_message = "Waiting period has not elapsed"

    __slots__ = ("elapsed_days", "notice_id", "required_days")

    def __init__(
        self,
        notice_id: UUID,
        required_days: int,
        elapsed_days: int,
        **kwargs: Any,
    ) -> None:
        """Initialize waiting period not elapsed error.

        Args:
            notice_id: UUID of the notice that started the waiting period.
            required_days: Number of days required to wait.
            elapsed_days: Number of days that have actually elapsed.
            **kwargs: Additional arguments passed to parent.
        """
        self.notice_id = notice_id
        self.required_days = required_days
        self.elapsed_days = elapsed_days
        remaining = required_days - elapsed_days
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "notice_id": str(notice_id),
            "required_days": required_days,
            "elapsed_days": elapsed_days,
            "remaining_days": remaining,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Waiting period not elapsed: {elapsed_days}/{required_days} days "
            f"({remaining} days remaining)",
            context=merged_context,
            **kwargs,
        )


class WaitingPeriodPausedError(TimingViolation):
    """Action blocked because waiting period is paused.

    Raised when: An action requiring an active waiting period is attempted
    while the period is paused (e.g., due to dispute).

    Regulatory basis:
    - FCRA dispute handling: clock must pause during dispute resolution

    Phrase: waiting_period_must_not_be_paused
    """

    default_regulation = "FCRA Section 1681i"
    default_message = "Waiting period is paused"

    __slots__ = ("notice_id", "paused_at", "paused_reason")

    def __init__(
        self,
        notice_id: UUID,
        paused_at: datetime,
        paused_reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize waiting period paused error.

        Args:
            notice_id: UUID of the notice with paused waiting period.
            paused_at: When the waiting period was paused.
            paused_reason: Reason for pause (e.g., "Dispute filed").
            **kwargs: Additional arguments passed to parent.
        """
        self.notice_id = notice_id
        self.paused_at = paused_at
        self.paused_reason = paused_reason
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "notice_id": str(notice_id),
            "paused_at": paused_at.isoformat(),
            "paused_reason": paused_reason,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Waiting period for notice {notice_id} is paused since {paused_at.isoformat()}"
            + (f": {paused_reason}" if paused_reason else ""),
            context=merged_context,
            **kwargs,
        )


class WaitingPeriodNotFoundError(TimingViolation):
    """No waiting period exists for the specified notice.

    Raised when: get_waiting_period or check_waiting_period_elapsed
    cannot find a waiting period record for the given notice.

    Regulatory basis:
    - FCRA compliance requires waiting period to exist before adverse action
    """

    default_regulation = "FCRA Section 1681b(b)(3)"
    default_message = "Waiting period not found"

    __slots__ = ("notice_id",)

    def __init__(
        self,
        notice_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize waiting period not found error.

        Args:
            notice_id: UUID of the notice missing a waiting period.
            **kwargs: Additional arguments passed to parent.
        """
        self.notice_id = notice_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"notice_id": str(notice_id)}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"No waiting period found for notice: {notice_id}",
            context=merged_context,
            **kwargs,
        )


class NoticeNotDeliveredError(TimingViolation):
    """Required notice was not delivered.

    Raised when: verify_notice_delivered confirms the notice has not
    been successfully delivered to the recipient.

    Regulatory basis:
    - FCRA Section 1681m: Notice must be delivered before adverse action
    - NYC LL144: AEDT candidate notice must be delivered before screening
    """

    default_regulation = "FCRA Section 1681m"
    default_message = "Notice not delivered"

    __slots__ = ("delivery_status", "notice_id", "notice_type", "recipient_id")

    def __init__(
        self,
        notice_id: UUID,
        recipient_id: UUID,
        notice_type: str,
        delivery_status: str,
        **kwargs: Any,
    ) -> None:
        """Initialize notice not delivered error.

        Args:
            notice_id: UUID of the notice that was not delivered.
            recipient_id: UUID of the intended recipient.
            notice_type: Type of notice (e.g., "pre_adverse_action").
            delivery_status: Current delivery status.
            **kwargs: Additional arguments passed to parent.
        """
        self.notice_id = notice_id
        self.recipient_id = recipient_id
        self.notice_type = notice_type
        self.delivery_status = delivery_status
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "notice_id": str(notice_id),
            "recipient_id": str(recipient_id),
            "notice_type": notice_type,
            "delivery_status": delivery_status,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Notice '{notice_type}' to recipient {recipient_id} not delivered "
            f"(status: {delivery_status})",
            context=merged_context,
            **kwargs,
        )


class NoticeNotFoundError(TimingViolation):
    """Notice record does not exist.

    Raised when: get_notice cannot find the specified notice.
    """

    default_regulation = "FCRA Section 1681m"
    default_message = "Notice not found"

    __slots__ = ("notice_id",)

    def __init__(
        self,
        notice_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize notice not found error.

        Args:
            notice_id: UUID of the notice that was not found.
            **kwargs: Additional arguments passed to parent.
        """
        self.notice_id = notice_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"notice_id": str(notice_id)}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Notice not found: {notice_id}",
            context=merged_context,
            **kwargs,
        )


class NoticePrecedenceError(TimingViolation):
    """Required notice was not delivered before the action.

    Raised when: An action requiring prior notice is attempted without the
    notice having been sent/delivered.

    Regulatory basis:
    - FCRA Section 1681m: Pre-adverse action notice must precede adverse action
    - WARN Act: 60-day notice for mass layoffs
    - State WARN variations (California, New York)

    Phrase: notice_must_precede_action
    """

    default_regulation = "FCRA Section 1681m"
    default_message = "Notice must precede action"

    __slots__ = ("action_type", "notice_required", "notice_status")

    def __init__(
        self,
        action_type: str,
        notice_required: str,
        notice_status: str,
        **kwargs: Any,
    ) -> None:
        """Initialize notice precedence error.

        Args:
            action_type: Type of action being attempted.
            notice_required: Type of notice required before action.
            notice_status: Current status of the required notice.
            **kwargs: Additional arguments passed to parent.
        """
        self.action_type = action_type
        self.notice_required = notice_required
        self.notice_status = notice_status
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "action_type": action_type,
            "notice_required": notice_required,
            "notice_status": notice_status,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Action '{action_type}' requires '{notice_required}' notice "
            f"(current status: {notice_status})",
            context=merged_context,
            **kwargs,
        )
