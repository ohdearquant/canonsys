"""Freshness domain exceptions.

These exceptions are raised by freshness actions when regulatory
timing or staleness invariants are violated. All inherit from
TimingViolation (the timing domain's base exception).

Regulatory Context:
    - SOX Section 404: Evidence and review freshness
    - FCRA Section 604: Report freshness requirements
    - GDPR Art. 5(1)(d): Data accuracy and currency
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import TimingViolation

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID

__all__ = [
    "CreditReportExpiredError",
    "DataStaleError",
    "DeadlineCriticalError",
    "ReviewOverdueError",
    "TIAExpiredError",
]


class DataStaleError(TimingViolation):
    """Data is older than the allowed freshness window.

    Raised when: check_equity_staleness or similar finds data that
    exceeds the maximum allowed age for compliance purposes.

    Regulatory basis:
    - SOX Section 404: Internal controls require current data
    - SEC guidance: Equity valuations must be reasonably current
    - Pay equity laws: Decisions must be based on current data

    Phrase: data_must_be_fresh
    """

    default_regulation = "SOX Section 404"
    default_message = "Data exceeds freshness requirements"

    __slots__ = ("age_days", "data_type", "max_age_days")

    def __init__(
        self,
        data_type: str,
        age_days: int,
        max_age_days: int,
        **kwargs: Any,
    ) -> None:
        """Initialize data stale error.

        Args:
            data_type: Type of data that is stale (e.g., "equity_analysis").
            age_days: Actual age of the data in days.
            max_age_days: Maximum allowed age in days.
            **kwargs: Additional arguments passed to parent.
        """
        self.data_type = data_type
        self.age_days = age_days
        self.max_age_days = max_age_days
        super().__init__(
            f"{data_type} is {age_days} days old (max allowed: {max_age_days} days)",
            context={
                "data_type": data_type,
                "age_days": age_days,
                "max_age_days": max_age_days,
                "days_overdue": age_days - max_age_days,
            },
            **kwargs,
        )


class ReviewOverdueError(TimingViolation):
    """Periodic review is overdue for a subject.

    Raised when: check_privilege_review finds that recertification
    is required but has not been completed within the required period.

    Regulatory basis:
    - SOX Section 404: Periodic access review requirements
    - SOC 2 CC6.1: Logical access review at defined intervals
    - HIPAA Security Rule: Access authorization review
    - PCI DSS 7.2: Access control systems review

    Phrase: review_must_be_current
    """

    default_regulation = "SOX Section 404"
    default_message = "Periodic review is overdue"

    __slots__ = ("days_overdue", "review_period_days", "review_type", "subject_id")

    def __init__(
        self,
        subject_id: UUID,
        review_type: str,
        days_overdue: int,
        review_period_days: int,
        **kwargs: Any,
    ) -> None:
        """Initialize review overdue error.

        Args:
            subject_id: UUID of the subject requiring review.
            review_type: Type of review (e.g., "privilege", "access").
            days_overdue: Days past the required review date.
            review_period_days: Required review frequency in days.
            **kwargs: Additional arguments passed to parent.
        """
        self.subject_id = subject_id
        self.review_type = review_type
        self.days_overdue = days_overdue
        self.review_period_days = review_period_days
        super().__init__(
            f"{review_type} review for {subject_id} is {days_overdue} days overdue "
            f"(required every {review_period_days} days)",
            context={
                "subject_id": str(subject_id),
                "review_type": review_type,
                "days_overdue": days_overdue,
                "review_period_days": review_period_days,
            },
            **kwargs,
        )


class CreditReportExpiredError(TimingViolation):
    """Credit report is too old for permissible use.

    Raised when: verify_credit_freshness finds a report that
    exceeds the maximum age allowed under FCRA.

    Regulatory basis:
    - FCRA Section 604(b)(3): Report freshness requirements
    - FTC guidance: 30-day standard for employment decisions
    - State laws: California, New York additional requirements

    Phrase: credit_report_must_be_fresh
    """

    default_regulation = "FCRA Section 604(b)(3)"
    default_message = "Credit report exceeds freshness requirements"

    __slots__ = ("age_days", "max_age_days", "report_date")

    def __init__(
        self,
        report_date: date,
        age_days: int,
        max_age_days: int,
        **kwargs: Any,
    ) -> None:
        """Initialize credit report expired error.

        Args:
            report_date: Date when the credit report was obtained.
            age_days: Actual age of the report in days.
            max_age_days: Maximum allowed age in days.
            **kwargs: Additional arguments passed to parent.
        """
        self.report_date = report_date
        self.age_days = age_days
        self.max_age_days = max_age_days
        super().__init__(
            f"Credit report from {report_date.isoformat()} is {age_days} days old "
            f"(max allowed: {max_age_days} days)",
            context={
                "report_date": report_date.isoformat(),
                "age_days": age_days,
                "max_age_days": max_age_days,
                "days_overdue": age_days - max_age_days,
            },
            **kwargs,
        )


class TIAExpiredError(TimingViolation):
    """Transfer Impact Assessment has expired.

    Raised when: check_tia_freshness finds a TIA that exceeds the
    maximum age allowed for international data transfers.

    Regulatory basis:
    - GDPR Art. 46: Appropriate safeguards for transfers
    - Schrems II: TIAs required for adequacy assessment
    - EDPB Recommendations: Annual TIA review recommended

    Phrase: tia_must_be_current
    """

    default_regulation = "GDPR Article 46"
    default_message = "Transfer Impact Assessment has expired"

    __slots__ = ("age_days", "max_age_days", "tia_id")

    def __init__(
        self,
        tia_id: UUID,
        age_days: int,
        max_age_days: int,
        **kwargs: Any,
    ) -> None:
        """Initialize TIA expired error.

        Args:
            tia_id: UUID of the expired TIA.
            age_days: Actual age of the TIA in days.
            max_age_days: Maximum allowed age in days.
            **kwargs: Additional arguments passed to parent.
        """
        self.tia_id = tia_id
        self.age_days = age_days
        self.max_age_days = max_age_days
        super().__init__(
            f"TIA {tia_id} is {age_days} days old (max allowed: {max_age_days} days)",
            context={
                "tia_id": str(tia_id),
                "age_days": age_days,
                "max_age_days": max_age_days,
                "days_overdue": age_days - max_age_days,
            },
            **kwargs,
        )


class DeadlineCriticalError(TimingViolation):
    """Regulatory deadline is in critical threshold.

    Raised when: derive_filing_deadline or derive_quarter_end
    finds the deadline is within the critical threshold requiring urgent action.

    Regulatory basis:
    - SEC Rule 12b-25: Filing deadline requirements
    - SOX Section 302: Quarterly certification timing
    - Various breach notification laws: Time-bound requirements

    Phrase: deadline_must_have_buffer
    """

    default_regulation = "SEC Rule 12b-25"
    default_message = "Deadline is within critical threshold"

    __slots__ = ("critical_threshold_days", "days_remaining", "deadline_type")

    def __init__(
        self,
        deadline_type: str,
        days_remaining: int,
        critical_threshold_days: int,
        **kwargs: Any,
    ) -> None:
        """Initialize deadline critical error.

        Args:
            deadline_type: Type of deadline (e.g., "10-K filing", "quarter end").
            days_remaining: Days until the deadline.
            critical_threshold_days: Critical threshold in days.
            **kwargs: Additional arguments passed to parent.
        """
        self.deadline_type = deadline_type
        self.days_remaining = days_remaining
        self.critical_threshold_days = critical_threshold_days
        super().__init__(
            f"{deadline_type} deadline in {days_remaining} days "
            f"(critical threshold: {critical_threshold_days} days)",
            context={
                "deadline_type": deadline_type,
                "days_remaining": days_remaining,
                "critical_threshold_days": critical_threshold_days,
            },
            **kwargs,
        )
