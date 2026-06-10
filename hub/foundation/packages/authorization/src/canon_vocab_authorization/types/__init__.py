"""Authorization domain types.

Enumerations, constants, and result dataclasses for authorization features.
"""

from .results import (
    ERClearanceResult,
    RequireDistinctIdentitiesResult,
    RequireDualApprovalResult,
    RequireSegregationAnalysisResult,
    RoleApprovalResult,
    VerifyApprovalChainCompleteResult,
)
from .roles import STANDARD_ROLES
from .status import (
    ApprovalChainStatus,
    ApproverStatus,
    ClearanceLevel,
    ERClearanceStatus,
    SegregationStatus,
)

__all__ = [
    # Role constants
    "STANDARD_ROLES",
    # Status enums
    "ApprovalChainStatus",
    "ApproverStatus",
    "ClearanceLevel",
    "ERClearanceStatus",
    "SegregationStatus",
    # Check results
    "ERClearanceResult",
    # Require results
    "RequireDistinctIdentitiesResult",
    "RequireDualApprovalResult",
    "RequireSegregationAnalysisResult",
    "RoleApprovalResult",
    # Verify results
    "VerifyApprovalChainCompleteResult",
]
