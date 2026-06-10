"""Authorization feature - vertical slice for access control and approval workflows.

This module provides the complete authorization domain implementation:
- Types: ERClearanceStatus, ClearanceLevel, SegregationStatus, ApprovalChainStatus, STANDARD_ROLES
- Phrases: check, require, verify operations
- Exceptions: Domain-specific errors for authorization failures

Regulatory context:
    - SOX Section 404 (Internal controls, segregation of duties)
    - SOC 2 CC5.1, CC6.1 (Control activities, logical access)
    - GDPR Art. 37-39 (DPO requirements)
    - ITAR/EAR (Export controls)
    - NISPOM (Classified information)

Usage:
    from canon_vocab_authorization import (
        # Specs classes
        CheckERClearanceSpecs,
        RequireDistinctIdentitiesSpecs,
        VerifyRoleApprovalSpecs,
        # Phrases
        check_er_clearance,
        require_access_justification,
        require_distinct_identities,
        verify_role_approval,
        # Exceptions
        SoDViolationError,
        # Package metadata
        AUTHORIZATION,
    )
"""

# Exceptions
from .exceptions import (
    ApprovalChainIncompleteError,
    AuthorizationViolation,
    ClearanceInsufficientError,
    DualApprovalRequiredError,
    ERClearanceNotGrantedError,
    JustificationRequiredError,
    RequirementNotMetError,
    RoleApprovalRequiredError,
    SegregationAnalysisRequiredError,
    SoDViolationError,
)

# Package metadata
from .package import AUTHORIZATION

# Phrases
from .phrases import (  # Specs classes; Check phrases; Require phrases; Verify phrases
    CheckERClearanceSpecs,
    RequireAccessJustificationSpecs,
    RequireDistinctIdentitiesSpecs,
    RequireDualApprovalSpecs,
    RequireReleaseClearanceSpecs,
    RequireSegregationAnalysisSpecs,
    VerifyApprovalChainCompleteSpecs,
    VerifyRoleApprovalSpecs,
    check_er_clearance,
    require_access_justification,
    require_distinct_identities,
    require_dual_approval,
    require_release_clearance,
    require_segregation_analysis,
    verify_approval_chain_complete,
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

# Service
from .service import AuthorizationService

# Types
from .types import (
    STANDARD_ROLES,
    ApprovalChainStatus,
    ClearanceLevel,
    ERClearanceResult,
    ERClearanceStatus,
    RequireDistinctIdentitiesResult,
    RequireDualApprovalResult,
    RequireSegregationAnalysisResult,
    RoleApprovalResult,
    SegregationStatus,
    VerifyApprovalChainCompleteResult,
)

__all__ = [
    # Package metadata
    "AUTHORIZATION",
    # Service
    "AuthorizationService",
    # Specs classes (Pydantic BaseModels)
    "CheckERClearanceSpecs",
    "RequireAccessJustificationSpecs",
    "RequireDistinctIdentitiesSpecs",
    "RequireDualApprovalSpecs",
    "RequireReleaseClearanceSpecs",
    "RequireSegregationAnalysisSpecs",
    "VerifyApprovalChainCompleteSpecs",
    "VerifyRoleApprovalSpecs",
    # Types
    "ApprovalChainStatus",
    "ClearanceLevel",
    "ERClearanceResult",
    "ERClearanceStatus",
    "RequireDistinctIdentitiesResult",
    "RequireDualApprovalResult",
    "RequireSegregationAnalysisResult",
    "RoleApprovalResult",
    "STANDARD_ROLES",
    "SegregationStatus",
    "VerifyApprovalChainCompleteResult",
    # Exceptions
    "ApprovalChainIncompleteError",
    "AuthorizationViolation",
    "ClearanceInsufficientError",
    "DualApprovalRequiredError",
    "ERClearanceNotGrantedError",
    "JustificationRequiredError",
    "RequirementNotMetError",
    "RoleApprovalRequiredError",
    "SegregationAnalysisRequiredError",
    "SoDViolationError",
    # Check phrases
    "check_er_clearance",
    # Require phrases
    "require_access_justification",
    "require_distinct_identities",
    "require_dual_approval",
    "require_release_clearance",
    "require_segregation_analysis",
    # Verify phrases
    "verify_approval_chain_complete",
    "verify_board_approval",
    "verify_cfo_approval",
    "verify_ciso_approval",
    "verify_compliance_approval",
    "verify_cto_approval",
    "verify_dpo_approval",
    "verify_executive_approval",
    "verify_gc_approval",
    "verify_hr_approval",
    "verify_role_approval",
]
