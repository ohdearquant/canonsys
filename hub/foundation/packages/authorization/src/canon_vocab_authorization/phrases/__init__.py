"""Authorization domain phrases.

All authorization operations in one place:
- Check phrases: check_er_clearance
- Get phrases: get_approval_chain
- Require phrases: require_access_justification, require_distinct_identities,
  require_dual_approval, require_release_clearance, require_role_authorized,
  require_segregation_analysis, require_separation_of_duties, require_time_bounded_access
- Verify phrases: verify_approval_chain_complete, verify_delegation_valid,
  verify_role_approval, verify_*_approval
"""

from .check_er_clearance import CheckERClearanceSpecs, check_er_clearance
from .get_approval_chain import (
    ApproverStatus,
    GetApprovalChainSpecs,
    get_approval_chain,
)
from .require_access_justification import (
    RequireAccessJustificationSpecs,
    require_access_justification,
)
from .require_distinct_identities import (
    RequireDistinctIdentitiesSpecs,
    require_distinct_identities,
)
from .require_dual_approval import RequireDualApprovalSpecs, require_dual_approval
from .require_release_clearance import (
    RequireReleaseClearanceSpecs,
    require_release_clearance,
)
from .require_role_authorized import RequireRoleAuthorizedSpecs, require_role_authorized
from .require_segregation_analysis import (
    RequireSegregationAnalysisSpecs,
    require_segregation_analysis,
)
from .require_separation_of_duties import (
    RequireSeparationOfDutiesSpecs,
    require_separation_of_duties,
)
from .require_time_bounded_access import (
    RequireTimeBoundedAccessSpecs,
    require_time_bounded_access,
)
from .verify_approval_chain_complete import (
    VerifyApprovalChainCompleteSpecs,
    verify_approval_chain_complete,
)
from .verify_delegation_valid import VerifyDelegationValidSpecs, verify_delegation_valid
from .verify_role_approval import (
    VerifyRoleApprovalSpecs,
    verify_board_approval,
    verify_cfo_approval,
    verify_ciso_approval,
    verify_compliance_approval,
    verify_cto_approval,
    verify_dpo_approval,
    verify_executive_approval,
    verify_gc_approval,
    verify_hr_approval,
    verify_role_approval,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "CheckERClearanceSpecs",
    "GetApprovalChainSpecs",
    "RequireAccessJustificationSpecs",
    "RequireDistinctIdentitiesSpecs",
    "RequireDualApprovalSpecs",
    "RequireReleaseClearanceSpecs",
    "RequireRoleAuthorizedSpecs",
    "RequireSegregationAnalysisSpecs",
    "RequireSeparationOfDutiesSpecs",
    "RequireTimeBoundedAccessSpecs",
    "VerifyApprovalChainCompleteSpecs",
    "VerifyDelegationValidSpecs",
    "VerifyRoleApprovalSpecs",
    # Enums
    "ApproverStatus",
    # Check phrases
    "check_er_clearance",
    # Get phrases
    "get_approval_chain",
    # Require phrases
    "require_access_justification",
    "require_distinct_identities",
    "require_dual_approval",
    "require_release_clearance",
    "require_role_authorized",
    "require_segregation_analysis",
    "require_separation_of_duties",
    "require_time_bounded_access",
    # Verify phrases
    "verify_approval_chain_complete",
    "verify_board_approval",
    "verify_cfo_approval",
    "verify_ciso_approval",
    "verify_compliance_approval",
    "verify_cto_approval",
    "verify_delegation_valid",
    "verify_dpo_approval",
    "verify_executive_approval",
    "verify_gc_approval",
    "verify_hr_approval",
    "verify_role_approval",
]
