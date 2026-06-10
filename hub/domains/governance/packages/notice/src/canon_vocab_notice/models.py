"""Notice service models - pre-adverse and adverse action notices.

Notices are a critical part of FCRA compliance:
1. Pre-adverse action notice (before decision is final)
2. Waiting period (typically 5 business days)
3. Adverse action notice (if decision stands)

Each notice and its delivery is tracked as Evidence.
"""

from __future__ import annotations

from enum import Enum
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

from canon.service import Action, RequestModel

# Enums


class NoticeType(str, Enum):
    """Types of compliance notices."""

    # FCRA / Adverse Action
    PRE_ADVERSE_ACTION = "pre_adverse_action"
    ADVERSE_ACTION = "adverse_action"
    FCRA_SUMMARY_OF_RIGHTS = "fcra_summary_of_rights"
    STATE_RIGHTS = "state_rights"
    DISCLOSURE = "disclosure"

    # Performance Improvement Plan
    PIP_SPECIFICATION = "pip_specification"
    PIP_CHECKPOINT = "pip_checkpoint"
    PIP_OUTCOME = "pip_outcome"

    # General Employment
    POLICY_UPDATE = "policy_update"
    HANDBOOK_UPDATE = "handbook_update"


class DeliveryMethod(str, Enum):
    """How notices are delivered."""

    EMAIL = "email"
    SMS = "sms"
    POSTAL = "postal"
    IN_APP = "in_app"
    HAND_DELIVERED = "hand_delivered"


class DeliveryStatus(str, Enum):
    """Delivery tracking states."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


# Payload Models (stored in Evidence.data)


class NoticePayload(BaseModel):
    """Data for a notice (stored in Evidence.data)."""

    notice_type: NoticeType
    jurisdiction: str  # CA, NYC, Federal, etc.
    template_version: str

    # Delivery tracking
    delivery_method: DeliveryMethod
    delivery_address: str  # email, phone, or postal address
    sent_at: str | None = None
    delivered_at: str | None = None
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING

    # Acknowledgment
    acknowledged_at: str | None = None
    acknowledgment_method: str | None = None  # clicked_link, replied, signature

    # Content reference
    content_hash: str | None = None  # Hash of the actual notice content
    document_id: UUID | None = None  # FK to document Evidence if stored


class DeliveryAttempt(BaseModel):
    """Record of a delivery attempt."""

    attempted_at: str
    method: DeliveryMethod
    address: str
    status: DeliveryStatus
    error_message: str | None = None
    provider_response: dict | None = None  # Raw response from email/SMS provider


class WaitingPeriod(BaseModel):
    """Waiting period calculation for adverse action."""

    notice_id: UUID  # Pre-adverse action notice Evidence ID
    started_at: str
    required_days: int  # Usually 5 business days
    jurisdiction: str
    ends_at: str  # Calculated end date
    elapsed: bool = False

    # Pause tracking (disputes pause the clock)
    paused_at: str | None = None
    paused_reason: str | None = None
    resumed_at: str | None = None


# Option Models (must be defined before NoticeAction)


class CreateNoticeOptions(BaseModel):
    """Options for creating a generic notice (PIP, policy, etc.)."""

    notice_type: NoticeType
    subject_id: UUID
    delivery_method: DeliveryMethod
    delivery_address: str
    jurisdiction: str | None = None
    template_version: str | None = None
    content_hash: str | None = None
    collected_by_id: UUID | None = None

    # For PIP notices - reference to case
    case_id: UUID | None = None

    # Plain language content shown to recipient
    title: str | None = None
    summary: str | None = None
    payload: dict | None = None  # Full structured payload


class RecordAcknowledgmentOptions(BaseModel):
    """Options for recording notice acknowledgment."""

    notice_id: UUID
    acknowledged_at: str | None = None  # Defaults to now
    acknowledgment_method: str  # "portal_click", "email_reply", "signature", "in_person"
    employee_response: str | None = None  # Optional written response


class GetNoticeOptions(BaseModel):
    """Options for retrieving a notice."""

    notice_id: UUID


class CreatePreAdverseOptions(BaseModel):
    """Options for creating a pre-adverse action notice."""

    subject_id: UUID
    jurisdiction: str
    delivery_method: DeliveryMethod
    delivery_address: str
    template_version: str
    content_hash: str
    collected_by_id: UUID | None = None


class CreateAdverseOptions(BaseModel):
    """Options for creating an adverse action notice."""

    subject_id: UUID
    pre_adverse_notice_id: UUID  # Must reference the pre-adverse notice
    jurisdiction: str
    delivery_method: DeliveryMethod
    delivery_address: str
    template_version: str
    content_hash: str
    collected_by_id: UUID | None = None


class CheckWaitingOptions(BaseModel):
    """Options for checking a waiting period status."""

    notice_id: UUID


class PauseWaitingOptions(BaseModel):
    """Options for pausing a waiting period (e.g., dispute filed)."""

    notice_id: UUID
    reason: str


class ResumeWaitingOptions(BaseModel):
    """Options for resuming a paused waiting period."""

    notice_id: UUID


class RecordDeliveryOptions(BaseModel):
    """Options for recording a delivery attempt."""

    notice_id: UUID
    delivery_method: DeliveryMethod
    delivery_address: str
    status: DeliveryStatus
    error_message: str | None = None
    provider_response: dict | None = None


class GetWaitingOptions(BaseModel):
    """Options for getting a waiting period."""

    notice_id: UUID


class GetDeliveriesOptions(BaseModel):
    """Options for getting delivery attempts."""

    notice_id: UUID


# Action Enum


class NoticeAction(Action):
    """Actions available on the notice service."""

    # Generic notice actions
    CREATE = "create"
    RECORD_ACKNOWLEDGMENT = "record_acknowledgment"
    GET = "get"

    # FCRA-specific
    CREATE_PRE_ADVERSE = "create_pre_adverse"
    CREATE_ADVERSE = "create_adverse"
    CHECK_WAITING = "check_waiting"
    PAUSE_WAITING = "pause_waiting"
    RESUME_WAITING = "resume_waiting"
    RECORD_DELIVERY = "record_delivery"
    GET_WAITING = "get_waiting"
    GET_DELIVERIES = "get_deliveries"

    @classmethod
    def action_option_map(cls) -> dict[Action, type[BaseModel]]:
        return {
            cls.CREATE: CreateNoticeOptions,
            cls.RECORD_ACKNOWLEDGMENT: RecordAcknowledgmentOptions,
            cls.GET: GetNoticeOptions,
            cls.CREATE_PRE_ADVERSE: CreatePreAdverseOptions,
            cls.CREATE_ADVERSE: CreateAdverseOptions,
            cls.CHECK_WAITING: CheckWaitingOptions,
            cls.PAUSE_WAITING: PauseWaitingOptions,
            cls.RESUME_WAITING: ResumeWaitingOptions,
            cls.RECORD_DELIVERY: RecordDeliveryOptions,
            cls.GET_WAITING: GetWaitingOptions,
            cls.GET_DELIVERIES: GetDeliveriesOptions,
        }


# Request Model


class NoticeRequest(RequestModel):
    """Request model for notice service operations."""

    action_class: ClassVar[type[Action]] = NoticeAction
