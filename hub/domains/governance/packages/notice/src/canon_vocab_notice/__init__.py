"""Notice service - formal compliance notices (FCRA, adverse action).

This package provides:
- Models for notice types, delivery methods, and waiting periods
- NoticeService for managing FCRA-compliant notice workflows
- Endpoints for email (Resend) and SMS (Twilio) delivery

Architecture Note:
    Unlike phrase-based packages, the notice service implements multi-step
    FCRA workflows with waiting period state management. It extends BaseService
    (not CanonService) because notice operations involve delivery orchestration
    and stateful waiting periods that don't fit the declarative phrase pattern.
    Features map to NoticeService._handle_* methods rather than phrase functions.
"""

from .models import (  # Request/Option models; Payload models; Enums
    CheckWaitingOptions,
    CreateAdverseOptions,
    CreateNoticeOptions,
    CreatePreAdverseOptions,
    DeliveryAttempt,
    DeliveryMethod,
    DeliveryStatus,
    GetDeliveriesOptions,
    GetNoticeOptions,
    GetWaitingOptions,
    NoticeAction,
    NoticePayload,
    NoticeRequest,
    NoticeType,
    PauseWaitingOptions,
    RecordAcknowledgmentOptions,
    RecordDeliveryOptions,
    ResumeWaitingOptions,
    WaitingPeriod,
)
from .package import NOTICE
from .phrases import (
    RequireNoticeDeliveredSpecs,
    require_notice_delivered,
)
from .service import (
    EVIDENCE_TYPE_ACKNOWLEDGMENT,
    EVIDENCE_TYPE_DELIVERY,
    EVIDENCE_TYPE_NOTICE,
    EVIDENCE_TYPE_WAITING,
    WAITING_PERIODS,
    NoticeService,
    get_notice_service,
)

__all__ = [
    # Evidence types
    "EVIDENCE_TYPE_ACKNOWLEDGMENT",
    "EVIDENCE_TYPE_DELIVERY",
    "EVIDENCE_TYPE_NOTICE",
    "EVIDENCE_TYPE_WAITING",
    # Package metadata
    "NOTICE",
    # Config
    "WAITING_PERIODS",
    # Option models
    "CheckWaitingOptions",
    "CreateAdverseOptions",
    "CreateNoticeOptions",
    "CreatePreAdverseOptions",
    # Payload models
    "DeliveryAttempt",
    # Enums
    "DeliveryMethod",
    "DeliveryStatus",
    "GetDeliveriesOptions",
    "GetNoticeOptions",
    "GetWaitingOptions",
    "NoticeAction",
    "NoticePayload",
    # Request model
    "NoticeRequest",
    # Service
    "NoticeService",
    "NoticeType",
    "PauseWaitingOptions",
    "RecordAcknowledgmentOptions",
    "RecordDeliveryOptions",
    # Phrase specs
    "RequireNoticeDeliveredSpecs",
    "ResumeWaitingOptions",
    "WaitingPeriod",
    "get_notice_service",
    # Phrases
    "require_notice_delivered",
]
