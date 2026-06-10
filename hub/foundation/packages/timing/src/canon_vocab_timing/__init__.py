"""Timing feature - vertical slice for timing-based compliance.

This module provides the complete timing domain implementation:
- Types: WaitingPeriodState, NoticeType, DeliveryStatus, NoticeChannel
- Phrases: get_waiting_period, check_waiting_period_elapsed, pause/resume, etc.
- Exceptions: WaitingPeriodNotElapsedError, NoticeNotDeliveredError, etc.
- Service: TimingService

Regulatory basis:
    - FCRA Section 1681b(b)(3): Waiting period requirements
    - FCRA Section 1681m: Pre-adverse action notice timing

Usage:
    from canon_vocab_timing import (
        # Types
        WaitingPeriodState,
        NoticeType,
        DeliveryStatus,
        NoticeChannel,
        # Phrases
        get_waiting_period,
        check_waiting_period_elapsed,
        pause_waiting_period,
        resume_waiting_period,
        # Exceptions
        WaitingPeriodNotElapsedError,
        NoticeNotDeliveredError,
        # Service
        TimingService,
        # Package metadata
        TIMING,
    )
"""

# Exceptions
from .exceptions import (
    NoticeNotDeliveredError,
    NoticeNotFoundError,
    NoticePrecedenceError,
    WaitingPeriodNotElapsedError,
    WaitingPeriodNotFoundError,
    WaitingPeriodPausedError,
)

# Package metadata
from .package import TIMING

# Phrases (all timing operations)
from .phrases import (
    EVIDENCE_TYPE_WAITING,
    CheckWaitingPeriodElapsedSpecs,
    DeliveryStatus,
    GetAcknowledgmentSpecs,
    GetDeliveryAttemptsSpecs,
    GetNoticeSpecs,
    GetWaitingPeriodSpecs,
    NoticeChannel,
    NoticeDeliveryStatus,
    NoticeType,
    PauseWaitingPeriodSpecs,
    ResumeWaitingPeriodSpecs,
    VerifyNoticeDeliveredSpecs,
    check_waiting_period_elapsed,
    get_acknowledgment,
    get_delivery_attempts,
    get_notice,
    get_waiting_period,
    pause_waiting_period,
    resume_waiting_period,
    verify_notice_delivered,
)

# Service
from .service import (  # Request Options (for type hints)
    CheckWaitingPeriodOptions,
    GetAcknowledgmentOptions,
    GetDeliveryAttemptsOptions,
    GetNoticeOptions,
    GetWaitingPeriodOptions,
    PauseWaitingPeriodOptions,
    ResumeWaitingPeriodOptions,
    TimingService,
    VerifyNoticeDeliveredOptions,
)

# Types (domain enums)
from .types import (
    JURISDICTION_WAITING_DAYS,
    AcknowledgmentMethod,
    Jurisdiction,
    WaitingPeriodState,
)

__all__ = [
    # Package metadata
    "TIMING",
    # Constants
    "EVIDENCE_TYPE_WAITING",
    "JURISDICTION_WAITING_DAYS",
    # Domain types (enums)
    "AcknowledgmentMethod",
    "DeliveryStatus",
    "Jurisdiction",
    "NoticeChannel",
    "NoticeDeliveryStatus",
    "NoticeType",
    "WaitingPeriodState",
    # Specs classes (Pydantic BaseModels for phrase typing)
    "CheckWaitingPeriodElapsedSpecs",
    "GetAcknowledgmentSpecs",
    "GetDeliveryAttemptsSpecs",
    "GetNoticeSpecs",
    "GetWaitingPeriodSpecs",
    "PauseWaitingPeriodSpecs",
    "ResumeWaitingPeriodSpecs",
    "VerifyNoticeDeliveredSpecs",
    # Service Request Options (for backward compatibility)
    "CheckWaitingPeriodOptions",
    "GetAcknowledgmentOptions",
    "GetDeliveryAttemptsOptions",
    "GetNoticeOptions",
    "GetWaitingPeriodOptions",
    "PauseWaitingPeriodOptions",
    "ResumeWaitingPeriodOptions",
    "VerifyNoticeDeliveredOptions",
    # Exceptions
    "NoticeNotDeliveredError",
    "NoticeNotFoundError",
    "NoticePrecedenceError",
    "WaitingPeriodNotElapsedError",
    "WaitingPeriodNotFoundError",
    "WaitingPeriodPausedError",
    # Service
    "TimingService",
    # Phrase functions
    "check_waiting_period_elapsed",
    "get_acknowledgment",
    "get_delivery_attempts",
    "get_notice",
    "get_waiting_period",
    "pause_waiting_period",
    "resume_waiting_period",
    "verify_notice_delivered",
]
