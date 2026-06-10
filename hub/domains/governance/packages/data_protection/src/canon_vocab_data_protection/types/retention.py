"""Retention types for data protection domain.

Defines retention status for data lifecycle management.

Regulatory context:
    - GDPR Art. 5(1)(e): Storage limitation
    - CCPA Section 1798.105: Right to deletion
    - SOX Section 802: Document retention
"""

from __future__ import annotations

from enum import StrEnum


class RetentionStatus(StrEnum):
    """Retention status for data lifecycle management."""

    WITHIN_SCHEDULE = "within_schedule"
    BEYOND_SCHEDULE = "beyond_schedule"
    UNDER_HOLD = "under_hold"
    EXEMPT = "exempt"
