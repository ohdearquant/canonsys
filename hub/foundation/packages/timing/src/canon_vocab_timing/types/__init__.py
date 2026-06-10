"""Timing feature types.

Domain types for timing-based compliance features including
waiting periods, notice delivery, and acknowledgment tracking.

Types:
    - WaitingPeriodState: Active/Paused/Elapsed states
    - Jurisdiction: Federal, California, NYC, NY State
    - NoticeType: Pre-adverse, adverse, PIP, policy, etc.
    - DeliveryStatus: Sent/Delivered/Bounced/Failed
    - NoticeDeliveryStatus: Overall delivery status
    - NoticeChannel: Email/Postal/In-app/SMS
    - AcknowledgmentMethod: How recipient acknowledged notice
    - ConstraintType: Types of timing constraints
    - SlaType: Types of SLAs
"""

from __future__ import annotations

from enum import StrEnum

from canon_vocab_timing.phrases.get_timing_constraints import ConstraintType
from canon_vocab_timing.phrases.verify_sla_met import SlaType
from kron.types import Enum

__all__ = [
    "JURISDICTION_WAITING_DAYS",
    "AcknowledgmentMethod",
    "ConstraintType",
    "DeliveryStatus",
    "Jurisdiction",
    "NoticeChannel",
    "NoticeDeliveryStatus",
    "NoticeType",
    "SlaType",
    "WaitingPeriodState",
]


# =============================================================================
# Waiting Period Types
# =============================================================================


class WaitingPeriodState(Enum):
    """Logical state of a waiting period.

    Waiting periods transition through these states:
        ACTIVE -> PAUSED (dispute filed)
        PAUSED -> ACTIVE (dispute resolved, time extended)
        ACTIVE -> ELAPSED (time passed, not paused)

    The state is derived from the combination of:
        - elapsed: bool (has time passed?)
        - paused_at: datetime | None (is it paused?)
        - resumed_at: datetime | None (was it resumed?)
    """

    ACTIVE = "active"  # Clock is running
    PAUSED = "paused"  # Clock stopped (dispute filed)
    ELAPSED = "elapsed"  # Required time has passed


class Jurisdiction(Enum):
    """Jurisdictions with specific waiting period requirements.

    Different jurisdictions have different FCRA waiting period requirements.
    The federal default is 5 business days, but some states require more.
    """

    FEDERAL = "federal"  # 5 business days (default)
    CALIFORNIA = "california"  # 7 business days
    NYC = "nyc"  # 5 business days (matches federal)
    NEW_YORK_STATE = "new_york_state"  # State-level requirements


# Jurisdiction waiting period days mapping
JURISDICTION_WAITING_DAYS: dict[str, int] = {
    Jurisdiction.FEDERAL: 5,
    Jurisdiction.CALIFORNIA: 7,
    Jurisdiction.NYC: 5,
    Jurisdiction.NEW_YORK_STATE: 5,
    "default": 5,
}


# =============================================================================
# Notice Types
# =============================================================================


class NoticeType(Enum):
    """Types of compliance notices.

    Different notice types have different regulatory requirements
    for content, timing, and delivery confirmation.
    """

    # FCRA adverse action flow
    PRE_ADVERSE_ACTION = "pre_adverse_action"  # Before final decision
    ADVERSE_ACTION = "adverse_action"  # Final adverse decision

    # HR/Employment notices
    PIP_SPECIFICATION = "pip_specification"  # Performance improvement plan
    POLICY_UPDATE = "policy_update"  # Policy change notification
    TERMINATION = "termination"  # Termination notice

    # AI/AEDT notices
    AEDT_DISCLOSURE = "aedt_disclosure"  # NYC LL144 candidate notice

    # General purpose
    GENERIC = "generic"


class DeliveryStatus(Enum):
    """Delivery attempt status.

    Tracks the outcome of each delivery attempt.
    Multiple attempts may be made for a single notice.
    """

    SENT = "sent"  # Dispatched but not confirmed
    DELIVERED = "delivered"  # Confirmed receipt
    BOUNCED = "bounced"  # Delivery failed (email bounce, return to sender)
    FAILED = "failed"  # Technical failure in sending


class NoticeDeliveryStatus(StrEnum):
    """Overall notice delivery status.

    Higher-level status for the notice as a whole,
    across all delivery attempts and channels.
    """

    DELIVERED = "delivered"  # Successfully delivered via at least one channel
    PENDING = "pending"  # Delivery in progress
    FAILED = "failed"  # All delivery attempts failed
    BOUNCED = "bounced"  # Delivery bounced
    NOT_SENT = "not_sent"  # Notice has not been sent yet


class NoticeChannel(StrEnum):
    """Delivery channels for notices.

    Different channels may be required for different regulations.
    FCRA typically requires postal mail, while AEDT notices
    may be delivered electronically.
    """

    EMAIL = "email"
    POSTAL = "postal"
    IN_APP = "in_app"  # Portal/application notification
    SMS = "sms"


class AcknowledgmentMethod(Enum):
    """Methods of notice acknowledgment.

    How the recipient acknowledged receipt of the notice.
    Important for proving notice was received.
    """

    PORTAL_CLICK = "portal_click"  # Clicked acknowledgment in portal
    EMAIL_REPLY = "email_reply"  # Replied to email
    SIGNATURE = "signature"  # Physical or electronic signature
    IN_PERSON = "in_person"  # Acknowledged in person (meeting)
    SMS_REPLY = "sms_reply"  # Replied to SMS
    CERTIFIED_MAIL = "certified_mail"  # Certified mail receipt
