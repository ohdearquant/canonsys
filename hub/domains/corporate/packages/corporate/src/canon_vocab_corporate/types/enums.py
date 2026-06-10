"""Corporate domain enums.

Status enums for M&A deals, clean team requirements, conditional
findings, carve-out readiness, and condition satisfaction.

Regulatory Context:
    - Hart-Scott-Rodino Act (HSR) - antitrust filing/waiting
    - Sherman Act Section 1 - information sharing restrictions
    - FTC/DOJ Merger Guidelines - gun-jumping prevention
    - SEC M&A disclosure rules
"""

from enum import StrEnum
from typing import Literal

__all__ = [
    "CarveOutStatus",
    "CleanTeamReason",
    "ConditionSatisfactionStatus",
    "ConditionType",
    "DataSensitivityLevel",
    "DealPhase",
    "FindingStatus",
    "SensitiveDataCategory",
]


class DealPhase(StrEnum):
    """Phase of M&A deal lifecycle."""

    PRE_LOI = "pre_loi"
    LOI_SIGNED = "loi_signed"
    DUE_DILIGENCE = "due_diligence"
    DEFINITIVE_AGREEMENT = "definitive_agreement"
    HSR_FILING = "hsr_filing"
    REGULATORY_REVIEW = "regulatory_review"
    CLOSING_CONDITIONS = "closing_conditions"
    CLOSED = "closed"
    TERMINATED = "terminated"


class DataSensitivityLevel(StrEnum):
    """Sensitivity level of deal-related data.

    Determines whether clean team access controls are required.
    """

    PUBLIC = "public"
    CONFIDENTIAL = "confidential"
    HIGHLY_CONFIDENTIAL = "highly_confidential"
    COMPETITIVELY_SENSITIVE = "competitively_sensitive"
    ANTITRUST_SENSITIVE = "antitrust_sensitive"


class CleanTeamReason(StrEnum):
    """Reason why clean team is required.

    Anti-gaming: Derived from data categories, not user-asserted.
    """

    COMPETITIVE_PRICING = "competitive_pricing"
    CUSTOMER_LISTS = "customer_lists"
    STRATEGIC_ROADMAP = "strategic_roadmap"
    SUPPLIER_TERMS = "supplier_terms"
    EMPLOYEE_COMPENSATION = "employee_compensation"
    PRODUCT_MARGINS = "product_margins"
    MARKET_STRATEGY = "market_strategy"
    NOT_REQUIRED = "not_required"


class FindingStatus(StrEnum):
    """Status of conditional findings in M&A due diligence."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    REMEDIATED = "remediated"
    WAIVED = "waived"
    BLOCKED = "blocked"
    DEFERRED_TO_CLOSING = "deferred_to_closing"


class CarveOutStatus(StrEnum):
    """Readiness status for regulatory carve-out requirements."""

    NOT_STARTED = "not_started"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class ConditionType(StrEnum):
    """Type of closing condition in M&A transaction."""

    REGULATORY_APPROVAL = "regulatory_approval"
    SHAREHOLDER_APPROVAL = "shareholder_approval"
    FINANCING = "financing"
    NO_MAC = "no_mac"  # No Material Adverse Change
    DUE_DILIGENCE = "due_diligence"
    THIRD_PARTY_CONSENT = "third_party_consent"
    EMPLOYEE_RETENTION = "employee_retention"
    CARVE_OUT = "carve_out"
    LEGAL_OPINION = "legal_opinion"
    TAX_RULING = "tax_ruling"


class ConditionSatisfactionStatus(StrEnum):
    """Satisfaction status for closing conditions."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SATISFIED = "satisfied"
    WAIVED = "waived"
    FAILED = "failed"
    EXPIRED = "expired"


# Literal types for validation
SensitiveDataCategory = Literal[
    "competitive_pricing",
    "customer_lists",
    "supplier_terms",
    "strategic_roadmap",
    "employee_compensation",
    "product_margins",
    "market_strategy",
    "cost_structures",
    "capacity_plans",
    "bidding_history",
]
"""Data categories that trigger clean team requirements under HSR Act."""
