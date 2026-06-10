"""Legal features for legal compliance management.

Complete vertical slice for legal domain implementation including:
- Types: HoldType, AppealStatus, ProceedingsStatus, NDAStatus, CleanTeamStatus,
  PrivilegedReviewStatus, AppealChannelType, CriteriaLock
- Phrases: lock_*, require_*, verify_*
- Exceptions: LegalViolation, AppealNotExhaustedError, etc.

Regulatory context:
    - SOX Section 802 (Document destruction)
    - FRCP 37(e) (ESI preservation)
    - Hart-Scott-Rodino Act (M&A antitrust)
    - Attorney-Client Privilege
    - Administrative Procedure Act (due process)
    - Defend Trade Secrets Act (DTSA)

Usage:
    from canon_vocab_legal import (
        # Types
        HoldType,
        AppealStatus,
        CriteriaLock,
        # Phrases
        require_deletion_clearance,
        require_appeal_exhausted,
        verify_nda_status,
        # Specs classes
        RequireDeletionClearanceSpecs,
        RequireAppealExhaustedSpecs,
        VerifyNDAStatusSpecs,
        # Exceptions
        LegalHoldViolationError,
        # Package metadata
        LEGAL,
    )
"""

# Exceptions
from .exceptions import (
    AppealNotExhaustedError,
    CleanTeamRequiredError,
    LegalHoldViolationError,
    LegalReviewRequiredError,
    LegalViolation,
    NDARequiredError,
    ProceedingsNotClosedError,
)

# Package metadata
from .package import LEGAL

# Phrases (includes all lock, requirement, and verification phrases)
from .phrases import (
    LockCriteriaSpecs,
    RequireAppealExhaustedSpecs,
    RequireCleanTeamForCompetitiveIntelSpecs,
    RequireDeletionClearanceSpecs,
    RequireLegalReviewCompleteSpecs,
    RequireModificationClearanceSpecs,
    RequireNDAValidSpecs,
    RequireProceedingsClosedSpecs,
    VerifyAppealChannelAvailableSpecs,
    VerifyCleanTeamMembershipSpecs,
    VerifyNDAStatusSpecs,
    VerifyPrivilegedReviewCompleteSpecs,
    lock_criteria,
    require_appeal_exhausted,
    require_clean_team_for_competitive_intel,
    require_deletion_clearance,
    require_legal_review_complete,
    require_modification_clearance,
    require_nda_valid,
    require_proceedings_closed,
    verify_appeal_channel_available,
    verify_clean_team_membership,
    verify_nda_status,
    verify_privileged_review_complete,
)

# Service
from .service import LegalService

# Types
from .types import (
    AppealChannelType,
    AppealStatus,
    CleanTeamStatus,
    CriteriaLock,
    HoldType,
    NDAStatus,
    PrivilegedReviewStatus,
    ProceedingsStatus,
)

__all__ = [
    # Package metadata
    "LEGAL",
    # Service
    "LegalService",
    # Types
    "AppealChannelType",
    "AppealStatus",
    "CleanTeamStatus",
    "CriteriaLock",
    "HoldType",
    "NDAStatus",
    "PrivilegedReviewStatus",
    "ProceedingsStatus",
    # Specs classes (Pydantic BaseModels)
    "LockCriteriaSpecs",
    "RequireAppealExhaustedSpecs",
    "RequireCleanTeamForCompetitiveIntelSpecs",
    "RequireDeletionClearanceSpecs",
    "RequireLegalReviewCompleteSpecs",
    "RequireModificationClearanceSpecs",
    "RequireNDAValidSpecs",
    "RequireProceedingsClosedSpecs",
    "VerifyAppealChannelAvailableSpecs",
    "VerifyCleanTeamMembershipSpecs",
    "VerifyNDAStatusSpecs",
    "VerifyPrivilegedReviewCompleteSpecs",
    # Exceptions
    "AppealNotExhaustedError",
    "CleanTeamRequiredError",
    "LegalHoldViolationError",
    "LegalReviewRequiredError",
    "LegalViolation",
    "NDARequiredError",
    "ProceedingsNotClosedError",
    # Phrase functions
    "lock_criteria",
    "require_appeal_exhausted",
    "require_clean_team_for_competitive_intel",
    "require_deletion_clearance",
    "require_legal_review_complete",
    "require_modification_clearance",
    "require_nda_valid",
    "require_proceedings_closed",
    "verify_appeal_channel_available",
    "verify_clean_team_membership",
    "verify_nda_status",
    "verify_privileged_review_complete",
]
