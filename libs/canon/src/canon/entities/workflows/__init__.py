"""Workflow-specific entities.

Submodules:
    talent/: Domain entities for hiring workflows (Brief, Interview, Job, etc.)
    employee/: Domain entities for employee workflows (PIP)
    document_access: DocumentAccessToken (JIT document access)
    queue: WorkflowStatus, StepStatus, ActionType enums
"""

from .document_access import DocumentAccessToken, DocumentAccessTokenContent
from .employee.pip import (
    GoalStatus,
    PIPCheckpoint,
    PIPCheckpointContent,
    PIPDecision,
    PIPDecisionContent,
    PIPOutcome,
    PIPOutcomeRecommendation,
    PIPOutcomeRecommendationContent,
    PIPPhase,
    PIPPlan,
    PIPPlanContent,
    PIPStatus,
    RiskFlag,
)
from .queue import (
    ActionType,
    DocumentAccessPurpose,
    DocumentAccessStatus,
    StepStatus,
    WorkflowStatus,
)
from .talent.brief import (
    HiringBrief,
    HiringBriefContent,
    MarketContext,
    MarketContextContent,
)
from .talent.calibration import (
    BiasCategory,
    CalibrationResult,
    CalibrationResultContent,
    CalibrationStatus,
    EvaluatorProfile,
    EvaluatorProfileContent,
)
from .talent.exception_offer import (
    NEXT_STATUS_ON_APPROVAL,
    STATUS_TO_APPROVER_ROLE,
    ApprovalStatus,
    ApproverRole,
    ExceptionOffer,
    ExceptionOfferContent,
    OfferApproval,
    OfferApprovalContent,
    OfferStatus,
)
from .talent.interview import (
    BiasAnalysis,
    BiasAnalysisContent,
    BiasFlag,
    CompetencyAssessment,
    CompetencyAssessmentContent,
    Interview,
    InterviewContent,
    InterviewStatus,
    Recommendation,
    Scorecard,
    ScorecardContent,
)
from .talent.job import (
    Candidacy,
    CandidacyContent,
    CandidacyStatus,
    Job,
    JobContent,
    JobStatus,
    WorkplaceModel,
)
from .talent.market import (
    MarketAnalysis,
    MarketAnalysisContent,
    MarketMap,
    MarketMapContent,
)
from .talent.outreach import (
    AIDisclosure,
    AIDisclosureContent,
    OutreachMessage,
    OutreachMessageContent,
)
from .talent.signal import (
    CandidateStory,
    CandidateStoryContent,
    SignalResult,
    SignalResultContent,
    SkillInference,
    SkillInferenceContent,
    StorySection,
    StorySectionContent,
)

__all__ = (
    # Generic workflow enums
    "WorkflowStatus",
    "StepStatus",
    "ActionType",
    "DocumentAccessPurpose",
    "DocumentAccessStatus",
    # Interview enums
    "BiasFlag",
    "InterviewStatus",
    "Recommendation",
    # PIP enums
    "GoalStatus",
    "PIPOutcome",
    "PIPPhase",
    "PIPStatus",
    "RiskFlag",
    # Calibration enums
    "BiasCategory",
    "CalibrationStatus",
    # Job enums
    "CandidacyStatus",
    "JobStatus",
    "WorkplaceModel",
    # Exception offer enums and constants
    "ApprovalStatus",
    "ApproverRole",
    "OfferStatus",
    "NEXT_STATUS_ON_APPROVAL",
    "STATUS_TO_APPROVER_ROLE",
    # Framework workflow entities
    "DocumentAccessToken",
    "DocumentAccessTokenContent",
    # Brief workflow
    "HiringBrief",
    "HiringBriefContent",
    "MarketContext",
    "MarketContextContent",
    # Calibration workflow
    "CalibrationResult",
    "CalibrationResultContent",
    "EvaluatorProfile",
    "EvaluatorProfileContent",
    # Interview workflow
    "BiasAnalysis",
    "BiasAnalysisContent",
    "CompetencyAssessment",
    "CompetencyAssessmentContent",
    "Interview",
    "InterviewContent",
    "Scorecard",
    "ScorecardContent",
    # Market workflow
    "MarketAnalysis",
    "MarketAnalysisContent",
    "MarketMap",
    "MarketMapContent",
    # Outreach workflow
    "AIDisclosure",
    "AIDisclosureContent",
    "OutreachMessage",
    "OutreachMessageContent",
    # PIP workflow
    "PIPCheckpoint",
    "PIPCheckpointContent",
    "PIPDecision",
    "PIPDecisionContent",
    "PIPOutcomeRecommendation",
    "PIPOutcomeRecommendationContent",
    "PIPPlan",
    "PIPPlanContent",
    # Signal workflow (includes CandidateStory and StorySection)
    "CandidateStory",
    "CandidateStoryContent",
    "SignalResult",
    "SignalResultContent",
    "SkillInference",
    "SkillInferenceContent",
    "StorySection",
    "StorySectionContent",
    # Job workflow
    "Candidacy",
    "CandidacyContent",
    "Job",
    "JobContent",
    # Exception offer workflow
    "ExceptionOffer",
    "ExceptionOfferContent",
    "OfferApproval",
    "OfferApprovalContent",
)
