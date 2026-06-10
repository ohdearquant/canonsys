"""AI Governance domain phrases.

All AI governance operations in one place:
- Requirement phrases: require_bias_assessment_documented, require_human_review_present,
  require_human_review_for_high_risk
- Verification phrases: verify_bias_assessment_complete, verify_human_review_complete,
  verify_same_tool

Regulatory context:
    - NYC LL144 (AEDT bias audits)
    - EU AI Act (High-risk AI requirements)
    - Colorado SB24-205 (Consumer AI protections)
    - GDPR Article 22 (Automated decision-making)
"""

from .require_bias_assessment_documented import (
    RequireBiasAssessmentDocumentedSpecs,
    require_bias_assessment_documented,
)
from .require_human_review_for_high_risk import (
    RequireHumanReviewForHighRiskSpecs,
    require_human_review_for_high_risk,
)
from .require_human_review_present import (
    RequireHumanReviewPresentSpecs,
    require_human_review_present,
)
from .verify_bias_assessment_complete import (
    VerifyBiasAssessmentCompleteSpecs,
    verify_bias_assessment_complete,
)
from .verify_human_review_complete import (
    VerifyHumanReviewCompleteSpecs,
    verify_human_review_complete,
)
from .verify_same_tool import VerifySameToolSpecs, verify_same_tool

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "RequireBiasAssessmentDocumentedSpecs",
    "RequireHumanReviewForHighRiskSpecs",
    "RequireHumanReviewPresentSpecs",
    "VerifyBiasAssessmentCompleteSpecs",
    "VerifyHumanReviewCompleteSpecs",
    "VerifySameToolSpecs",
    # Phrase functions - Requirements
    "require_bias_assessment_documented",
    "require_human_review_for_high_risk",
    "require_human_review_present",
    # Phrase functions - Verification
    "verify_bias_assessment_complete",
    "verify_human_review_complete",
    "verify_same_tool",
]
