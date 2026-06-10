"""Legal domain phrases.

All legal operations in one place:
- Lock phrases: lock_criteria
- Clearance requirement phrases: require_deletion_clearance, require_modification_clearance
- Requirement phrases: require_appeal_exhausted, require_clean_team_for_competitive_intel,
  require_legal_review_complete, require_nda_valid, require_proceedings_closed
- Verification phrases: verify_appeal_channel_available, verify_clean_team_membership,
  verify_nda_status, verify_privileged_review_complete

Regulatory context:
    - SOX Section 802 (Document destruction)
    - FRCP 37(e) (ESI preservation)
    - Hart-Scott-Rodino Act (M&A antitrust)
    - Attorney-Client Privilege
    - Administrative Procedure Act (due process)
    - Defend Trade Secrets Act (DTSA)
"""

# Lock phrases
from .lock_criteria import LockCriteriaSpecs, lock_criteria

# Requirement phrases
from .require_appeal_exhausted import (
    RequireAppealExhaustedSpecs,
    require_appeal_exhausted,
)
from .require_clean_team_for_competitive_intel import (
    RequireCleanTeamForCompetitiveIntelSpecs,
    require_clean_team_for_competitive_intel,
)

# Clearance requirement phrases
from .require_deletion_clearance import (
    RequireDeletionClearanceSpecs,
    require_deletion_clearance,
)
from .require_legal_hold_active import (
    RequireLegalHoldActiveSpecs,
    require_legal_hold_active,
)
from .require_legal_review_complete import (
    RequireLegalReviewCompleteSpecs,
    require_legal_review_complete,
)
from .require_modification_clearance import (
    RequireModificationClearanceSpecs,
    require_modification_clearance,
)
from .require_nda_valid import RequireNDAValidSpecs, require_nda_valid
from .require_proceedings_closed import (
    RequireProceedingsClosedSpecs,
    require_proceedings_closed,
)

# Verification phrases
from .verify_appeal_channel_available import (
    VerifyAppealChannelAvailableSpecs,
    verify_appeal_channel_available,
)
from .verify_clean_team_membership import (
    VerifyCleanTeamMembershipSpecs,
    verify_clean_team_membership,
)
from .verify_nda_status import VerifyNDAStatusSpecs, verify_nda_status
from .verify_privileged_review_complete import (
    VerifyPrivilegedReviewCompleteSpecs,
    verify_privileged_review_complete,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "LockCriteriaSpecs",
    "RequireAppealExhaustedSpecs",
    "RequireCleanTeamForCompetitiveIntelSpecs",
    "RequireDeletionClearanceSpecs",
    "RequireLegalHoldActiveSpecs",
    "RequireLegalReviewCompleteSpecs",
    "RequireModificationClearanceSpecs",
    "RequireNDAValidSpecs",
    "RequireProceedingsClosedSpecs",
    "VerifyAppealChannelAvailableSpecs",
    "VerifyCleanTeamMembershipSpecs",
    "VerifyNDAStatusSpecs",
    "VerifyPrivilegedReviewCompleteSpecs",
    # Phrase functions
    "lock_criteria",
    "require_appeal_exhausted",
    "require_clean_team_for_competitive_intel",
    "require_deletion_clearance",
    "require_legal_hold_active",
    "require_legal_review_complete",
    "require_modification_clearance",
    "require_nda_valid",
    "require_proceedings_closed",
    "verify_appeal_channel_available",
    "verify_clean_team_membership",
    "verify_nda_status",
    "verify_privileged_review_complete",
]
