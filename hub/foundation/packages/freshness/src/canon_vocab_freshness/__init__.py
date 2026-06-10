"""Freshness feature - vertical slice for timing and staleness management.

This module provides the complete freshness domain implementation:
- Types: FreshnessStatus
- Phrases: check_*, derive_*, verify_*
- Exceptions: DataStaleError, ReviewOverdueError, etc.

Regulatory Context:
    - SOX Section 302/404: Quarterly certifications and internal controls
    - GDPR Art. 5(1)(d): Data accuracy
    - FCRA Section 604: Report freshness requirements
    - PCI DSS 7.2: Access control systems review
    - Breach notification laws: 72h GDPR, varies by state

Usage:
    from canon_vocab_freshness import (
        # Types
        FreshnessStatus,
        # Check phrases
        check_equity_staleness,
        CheckEquityStalenessSpecs,
        check_privilege_review,
        CheckPrivilegeReviewSpecs,
        # Derive phrases
        derive_quarter_end,
        DeriveQuarterEndSpecs,
        # Verify phrases
        verify_credit_freshness,
        VerifyCreditFreshnessSpecs,
        # Exceptions
        DataStaleError,
        CreditReportExpiredError,
        # Package metadata
        FRESHNESS,
    )
"""

# Exceptions
from .exceptions import (
    CreditReportExpiredError,
    DataStaleError,
    DeadlineCriticalError,
    ReviewOverdueError,
    TIAExpiredError,
)

# Package metadata
from .package import FRESHNESS

# Phrases (all check, derive, verify operations)
from .phrases import (
    CheckEquityStalenessSpecs,
    CheckLegalReviewSpecs,
    CheckPrivilegeReviewSpecs,
    CheckReceiptFreshnessSpecs,
    CheckTIAFreshnessSpecs,
    DeriveExtensionDaysSpecs,
    DeriveFilingDeadlineSpecs,
    DeriveQuarterEndSpecs,
    DeriveRegulatoryDeadlineSpecs,
    VerifyCreditFreshnessSpecs,
    check_equity_staleness,
    check_legal_review_freshness,
    check_privilege_review,
    check_receipt_freshness,
    check_tia_freshness,
    derive_extension_days,
    derive_filing_deadline,
    derive_quarter_end,
    derive_regulatory_deadline,
    verify_credit_freshness,
)

# Service
from .service import FreshnessService

# Types
from .types import FreshnessStatus

__all__ = [
    # Package metadata
    "FRESHNESS",
    # Service
    "FreshnessService",
    # Types
    "FreshnessStatus",
    # Specs classes (Pydantic BaseModels)
    "CheckEquityStalenessSpecs",
    "CheckLegalReviewSpecs",
    "CheckPrivilegeReviewSpecs",
    "CheckReceiptFreshnessSpecs",
    "CheckTIAFreshnessSpecs",
    "DeriveExtensionDaysSpecs",
    "DeriveFilingDeadlineSpecs",
    "DeriveQuarterEndSpecs",
    "DeriveRegulatoryDeadlineSpecs",
    "VerifyCreditFreshnessSpecs",
    # Exceptions
    "CreditReportExpiredError",
    "DataStaleError",
    "DeadlineCriticalError",
    "ReviewOverdueError",
    "TIAExpiredError",
    # Check phrases
    "check_equity_staleness",
    "check_legal_review_freshness",
    "check_privilege_review",
    "check_receipt_freshness",
    "check_tia_freshness",
    # Derivation phrases
    "derive_extension_days",
    "derive_filing_deadline",
    "derive_quarter_end",
    "derive_regulatory_deadline",
    # Verification phrases
    "verify_credit_freshness",
]
