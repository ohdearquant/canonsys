"""Requirements-related type definitions.

Types for requirement checks including alternative reviews, fraud screening,
provenance documentation, and SOX compliance reviews.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = [
    "AlternativeReviewStatus",
    "FraudScreeningResult",
    "RequireAlternativeReviewedResult",
    "RequireFraudScreeningPassResult",
    "RequireProvenanceDocumentedResult",
    "RequireSOXComplianceReviewResult",
    "SOXReviewStatus",
]


class AlternativeReviewStatus(StrEnum):
    """Status of an alternative review."""

    REVIEWED = "reviewed"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"
    WAIVED = "waived"


@dataclass(frozen=True, slots=True)
class RequireAlternativeReviewedResult:
    """Result of alternative review requirement check.

    Regulatory:
        - EEOC UGESP Section 3B (Less discriminatory alternatives)
        - EU AI Act Art. 9 (Risk management alternatives)
        - ADA 42 USC 12112 (Reasonable accommodation)
    """

    satisfied: bool
    resource_id: UUID
    alternative_type: str
    review_id: UUID | None = None
    reviewer_id: UUID | None = None
    reviewed_at: datetime | None = None
    conclusion: str | None = None
    reason: str | None = None


class FraudScreeningResult(StrEnum):
    """Result status of fraud screening."""

    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class RequireFraudScreeningPassResult:
    """Result of fraud screening requirement check.

    Regulatory:
        - BSA/AML (Bank Secrecy Act)
        - PCI DSS v4.0 Req. 11 (Fraud monitoring)
        - FFIEC (Fraud detection)
    """

    satisfied: bool
    transaction_id: UUID
    screening_id: UUID | None = None
    result: FraudScreeningResult | None = None
    score: float | None = None
    screened_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RequireProvenanceDocumentedResult:
    """Result of provenance documentation requirement check.

    Regulatory:
        - EU AI Act Art. 12 (Record-keeping)
        - FDA 21 CFR Part 11 (Electronic records)
        - ISO 27001 A.12.4 (Logging and monitoring)
    """

    satisfied: bool
    artifact_id: UUID
    provenance_id: UUID | None = None
    source_documented: bool = False
    transformation_documented: bool = False
    documented_at: datetime | None = None
    reason: str | None = None


class SOXReviewStatus(StrEnum):
    """Status of a SOX compliance review."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING = "pending"
    REMEDIATION = "remediation"


@dataclass(frozen=True, slots=True)
class RequireSOXComplianceReviewResult:
    """Result of SOX compliance review requirement check.

    Regulatory:
        - SOX Section 302 (Corporate responsibility)
        - SOX Section 404 (Internal control assessment)
        - PCAOB AS 2201 (Auditing internal control)
    """

    satisfied: bool
    control_id: UUID
    status: SOXReviewStatus
    review_id: UUID | None = None
    reviewer_id: UUID | None = None
    reviewed_at: datetime | None = None
    findings_count: int = 0
    reason: str | None = None
