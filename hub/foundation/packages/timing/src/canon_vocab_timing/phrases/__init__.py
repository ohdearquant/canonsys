"""Timing domain phrases.

All timing operations as kron phrases:
- Gates: require_minimum_elapsed, require_deadline_not_passed
- Waiting periods: get_waiting_period, check_waiting_period_elapsed, pause/resume
- Notice tracking: get_notice, get_acknowledgment, get_delivery_attempts
- Verification: verify_notice_delivered, verify_sla_met
- Computation: compute_business_days
- Query: get_timing_constraints

Regulatory context:
    - FCRA Section 1681m (Pre-adverse action waiting period)
    - FCRA Section 1681i (Dispute response deadlines)
    - WARN Act (60-day notice requirement)
    - GDPR Article 12 (Response timing)
    - GDPR Article 33 (72-hour breach notification)
    - SOC 2 CC7.4 (Incident response timeliness)
"""

from .check_waiting_period_elapsed import (
    CheckWaitingPeriodElapsedSpecs,
    check_waiting_period_elapsed,
)
from .compute_business_days import ComputeBusinessDaysSpecs, compute_business_days
from .get_acknowledgment import GetAcknowledgmentSpecs, get_acknowledgment
from .get_delivery_attempts import (
    DeliveryStatus,
    GetDeliveryAttemptsSpecs,
    get_delivery_attempts,
)
from .get_notice import GetNoticeSpecs, NoticeType, get_notice
from .get_timing_constraints import (
    ConstraintType,
    GetTimingConstraintsSpecs,
    get_timing_constraints,
)
from .get_waiting_period import (
    EVIDENCE_TYPE_WAITING,
    GetWaitingPeriodSpecs,
    get_waiting_period,
)
from .pause_waiting_period import PauseWaitingPeriodSpecs, pause_waiting_period
from .require_deadline_not_passed import (
    RequireDeadlineNotPassedSpecs,
    require_deadline_not_passed,
)
from .require_minimum_elapsed import RequireMinimumElapsedSpecs, require_minimum_elapsed
from .resume_waiting_period import ResumeWaitingPeriodSpecs, resume_waiting_period
from .verify_notice_delivered import (
    NoticeChannel,
    NoticeDeliveryStatus,
    VerifyNoticeDeliveredSpecs,
    verify_notice_delivered,
)
from .verify_sla_met import SlaType, VerifySlametSpecs, verify_sla_met

__all__ = [
    # Constants
    "EVIDENCE_TYPE_WAITING",
    # Gate - Specs
    "RequireDeadlineNotPassedSpecs",
    "RequireMinimumElapsedSpecs",
    # Waiting Period - Specs
    "CheckWaitingPeriodElapsedSpecs",
    "GetWaitingPeriodSpecs",
    "PauseWaitingPeriodSpecs",
    "ResumeWaitingPeriodSpecs",
    # Notice - Specs
    "GetAcknowledgmentSpecs",
    "GetDeliveryAttemptsSpecs",
    "GetNoticeSpecs",
    # Verification - Specs
    "VerifyNoticeDeliveredSpecs",
    "VerifySlametSpecs",
    # Computation - Specs
    "ComputeBusinessDaysSpecs",
    # Query - Specs
    "GetTimingConstraintsSpecs",
    # Domain types (enums)
    "ConstraintType",
    "DeliveryStatus",
    "NoticeChannel",
    "NoticeDeliveryStatus",
    "NoticeType",
    "SlaType",
    # Gate - Functions
    "require_deadline_not_passed",
    "require_minimum_elapsed",
    # Waiting Period - Functions
    "check_waiting_period_elapsed",
    "get_waiting_period",
    "pause_waiting_period",
    "resume_waiting_period",
    # Notice - Functions
    "get_acknowledgment",
    "get_delivery_attempts",
    "get_notice",
    # Verification - Functions
    "verify_notice_delivered",
    "verify_sla_met",
    # Computation - Functions
    "compute_business_days",
    # Query - Functions
    "get_timing_constraints",
]
