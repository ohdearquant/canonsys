"""AI Governance feature - vertical slice for AI/ML compliance.

This module provides the complete AI governance domain implementation:
- Types: RiskLevel, BiasAssessmentStatus, HumanReviewStatus
- Phrases: require_*, verify_* operations
- Exceptions: AIGovernanceViolation and related errors
- Service: AIGovernanceService with action operations

Regulatory context:
- NYC LL144 (AEDT bias audits)
- EU AI Act (High-risk AI requirements)
- Colorado SB24-205 (Consumer AI protections)
- GDPR Article 22 (Automated decision-making)

Usage:
    from canon_vocab_ai_governance import (
        # Types
        RiskLevel,
        BiasAssessmentStatus,
        HumanReviewStatus,
        # Specs
        RequireHumanReviewForHighRiskSpecs,
        VerifySameToolSpecs,
        # Phrases
        require_human_review_for_high_risk,
        verify_bias_assessment_complete,
        verify_human_review_complete,
        verify_same_tool,
        # Service
        AIGovernanceService,
        # Package metadata
        AI_GOVERNANCE,
    )
"""

# Exceptions
from .exceptions import (
    AIGovernanceViolation,
    BiasAssessmentMissingError,
    DisclosureMissingError,
    HumanReviewMissingError,
    ToolConfigMismatchError,
)

# Package metadata
from .package import AI_GOVERNANCE

# Phrases (includes requirement and verification features)
from .phrases import (  # Specs classes; Phrase functions - Requirements; Phrase functions - Verification
    RequireBiasAssessmentDocumentedSpecs,
    RequireHumanReviewForHighRiskSpecs,
    RequireHumanReviewPresentSpecs,
    VerifyBiasAssessmentCompleteSpecs,
    VerifyHumanReviewCompleteSpecs,
    VerifySameToolSpecs,
    require_bias_assessment_documented,
    require_human_review_for_high_risk,
    require_human_review_present,
    verify_bias_assessment_complete,
    verify_human_review_complete,
    verify_same_tool,
)

# Service
from .service import AIGovernanceService

# Types
from .types import BiasAssessmentStatus, HumanReviewStatus, RiskLevel

__all__ = [
    # Package metadata
    "AI_GOVERNANCE",
    # Service
    "AIGovernanceService",
    # Exceptions
    "AIGovernanceViolation",
    "BiasAssessmentMissingError",
    "BiasAssessmentStatus",
    "DisclosureMissingError",
    "HumanReviewMissingError",
    "HumanReviewStatus",
    # Specs classes
    "RequireBiasAssessmentDocumentedSpecs",
    "RequireHumanReviewForHighRiskSpecs",
    "RequireHumanReviewPresentSpecs",
    # Types
    "RiskLevel",
    "ToolConfigMismatchError",
    "VerifyBiasAssessmentCompleteSpecs",
    "VerifyHumanReviewCompleteSpecs",
    "VerifySameToolSpecs",
    # Phrases - Require
    "require_bias_assessment_documented",
    "require_human_review_for_high_risk",
    "require_human_review_present",
    # Phrases - Verify
    "verify_bias_assessment_complete",
    "verify_human_review_complete",
    "verify_same_tool",
]
