"""PIP (Performance Improvement Plan) workflow entities.

Provides entities for managing performance improvement plans:
    PIPPlan: The improvement plan with goals and timeline
    PIPCheckpoint: Progress checkpoints during the PIP period
    PIPOutcomeRecommendation: Final outcome recommendation based on progress

Regulatory context:
    - Employment law: Documentation of performance management
    - ADA: Reasonable accommodation tracking in goal setting
    - ADEA: Age-neutral performance criteria
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from kron.types import FK, Enum

from ...entity import Entity, register_entity
from ...shared import Person, SubjectAware, TenantAware

__all__ = (
    # Enums
    "PIPPhase",
    "PIPStatus",
    "PIPOutcome",
    "GoalStatus",
    "RiskFlag",
    # Content models
    "PIPPlanContent",
    "PIPCheckpointContent",
    "PIPOutcomeRecommendationContent",
    "PIPDecisionContent",
    # Entities
    "PIPPlan",
    "PIPCheckpoint",
    "PIPOutcomeRecommendation",
    "PIPDecision",
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PIPPhase(Enum):
    """PIP lifecycle phases."""

    DRAFT = "draft"  # Plan being created
    ACTIVE = "active"  # Plan in progress
    REVIEW = "review"  # Under final review
    COMPLETED = "completed"  # Plan concluded
    CANCELLED = "cancelled"  # Plan terminated early


class PIPStatus(Enum):
    """Status of a PIP plan."""

    PENDING = "pending"  # Awaiting start
    IN_PROGRESS = "in_progress"  # Active PIP period
    EXTENDED = "extended"  # Duration extended
    COMPLETED_SUCCESS = "completed_success"  # Goals met
    COMPLETED_PARTIAL = "completed_partial"  # Some goals met
    COMPLETED_FAILURE = "completed_failure"  # Goals not met
    CANCELLED = "cancelled"  # Terminated early


class PIPOutcome(Enum):
    """Recommended outcomes for PIP completion."""

    CONTINUE_EMPLOYMENT = "continue_employment"  # Return to good standing
    EXTEND_PIP = "extend_pip"  # Additional improvement period
    ROLE_CHANGE = "role_change"  # Transfer to different role
    SEPARATION = "separation"  # Employment termination
    PENDING_REVIEW = "pending_review"  # Needs further assessment


class GoalStatus(Enum):
    """Status of individual PIP goals."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    MET = "met"
    PARTIALLY_MET = "partially_met"
    NOT_MET = "not_met"


class RiskFlag(Enum):
    """Risk flags that trigger legal review requirement for termination decisions."""

    PROTECTED_CLASS = "protected_class"
    """Employee is in a protected class (requires legal review)."""

    ON_LEAVE = "on_leave"
    """Employee is currently on leave (requires legal review)."""

    ACTIVE_COMPLAINT = "active_complaint"
    """Employee has filed a complaint (requires legal review)."""

    UNDER_INVESTIGATION = "under_investigation"
    """Employee is under investigation (requires legal review)."""


# ---------------------------------------------------------------------------
# PIPPlan
# ---------------------------------------------------------------------------


class PIPGoal(TenantAware):
    """Individual goal within a PIP plan."""

    goal_id: str
    """Unique identifier within the plan."""

    description: str
    """Clear, measurable goal description."""

    success_criteria: str
    """Specific criteria for determining goal completion."""

    target_date: datetime | None = None
    """Target completion date for this goal."""

    status: GoalStatus = GoalStatus.NOT_STARTED
    """Current status of the goal."""

    weight: float = 1.0
    """Relative importance weight (1.0 = standard)."""

    notes: str | None = None
    """Additional context or notes."""


class PIPPlanContent(TenantAware, SubjectAware):
    """Content for a Performance Improvement Plan.

    The PIP plan defines improvement goals, timeline, and success criteria
    for an employee. Used as the basis for checkpoint evaluations and
    final outcome recommendations.

    subject_id references the employee on the PIP.
    """

    # Plan identification
    plan_name: str
    """Descriptive name for the PIP (e.g., "Q1 2026 Performance Plan")."""

    # Timeline
    start_date: datetime
    """When the PIP period begins."""

    end_date: datetime
    """Expected end date of the PIP period."""

    recommended_duration_days: int
    """AI-recommended duration based on goal complexity."""

    # Goals and criteria
    goals: list[dict]
    """List of improvement goals with success criteria.

    Each goal dict contains:
        - goal_id: str
        - description: str
        - success_criteria: str
        - target_date: datetime | None
        - weight: float (default 1.0)
    """

    # Manager/supervisor
    manager_id: FK[Person] | None = None
    """Person responsible for overseeing the PIP."""

    hr_contact_id: FK[Person] | None = None
    """HR representative assigned to the case."""

    # AI analysis
    confidence_score: float | None = None
    """AI confidence in plan appropriateness (0.0-1.0)."""

    analysis_summary: str | None = None
    """AI-generated summary of performance analysis."""

    risk_factors: list[str] | None = None
    """Identified risk factors for plan success."""

    # Status
    phase: PIPPhase = PIPPhase.DRAFT
    """Current phase of the PIP workflow."""

    status: PIPStatus = PIPStatus.PENDING
    """Overall status of the PIP."""

    # Extensions
    original_end_date: datetime | None = None
    """Original end date if plan was extended."""

    extension_reason: str | None = None
    """Reason for extension if applicable."""


@register_entity("pip_plans")
class PIPPlan(Entity):
    """Entity representing a Performance Improvement Plan."""

    content: PIPPlanContent


# ---------------------------------------------------------------------------
# PIPCheckpoint
# ---------------------------------------------------------------------------


class PIPCheckpointContent(TenantAware):
    """Content for a PIP progress checkpoint.

    Checkpoints are periodic reviews during the PIP period to assess
    progress toward goals. Each checkpoint captures current status,
    observations, and any adjustments needed.
    """

    # Relationship
    pip_plan_id: FK[PIPPlan]
    """The PIP plan this checkpoint belongs to."""

    # Checkpoint identification
    checkpoint_number: int
    """Sequential checkpoint number (1, 2, 3, ...)."""

    scheduled_date: datetime
    """When this checkpoint was scheduled."""

    completed_date: datetime | None = None
    """When the checkpoint review was completed."""

    # Assessment
    status: str = "scheduled"
    """Checkpoint status: scheduled, completed, skipped."""

    overall_progress: str | None = None
    """Overall progress assessment: on_track, at_risk, off_track."""

    # Goal progress
    goal_progress: dict | None = None
    """Progress by goal_id.

    Dict structure:
        goal_id -> {
            "status": GoalStatus value,
            "progress_percentage": int (0-100),
            "observations": str,
            "evidence": list[str]  # Evidence IDs
        }
    """

    # Observations
    progress_observations: str | None = None
    """Manager/HR observations on progress."""

    employee_feedback: str | None = None
    """Employee's self-assessment and feedback."""

    obstacles_identified: list[str] | None = None
    """Obstacles or blockers identified."""

    support_provided: list[str] | None = None
    """Support or resources provided to employee."""

    # Recommendations
    recommendations: str | None = None
    """Recommendations for next period."""

    adjustments_needed: str | None = None
    """Any adjustments to goals or timeline."""

    # Review participants
    reviewer_id: FK[Person] | None = None
    """Person who conducted the checkpoint review."""


@register_entity("pip_checkpoints")
class PIPCheckpoint(Entity):
    """Entity representing a PIP checkpoint review."""

    content: PIPCheckpointContent


# ---------------------------------------------------------------------------
# PIPOutcomeRecommendation
# ---------------------------------------------------------------------------


class PIPOutcomeRecommendationContent(TenantAware):
    """Content for a PIP outcome recommendation.

    Generated after the PIP period concludes or when a decision is needed.
    Provides AI-assisted analysis of progress and recommended next steps.
    """

    # Relationship
    pip_plan_id: FK[PIPPlan]
    """The PIP plan this recommendation is for."""

    # Recommendation
    recommended_outcome: PIPOutcome
    """AI-recommended outcome based on progress analysis."""

    outcome_rationale: str
    """Detailed rationale for the recommendation."""

    # Analysis metrics
    overall_improvement: float | None = None
    """Overall improvement score (0.0-1.0)."""

    goal_completion_rate: float | None = None
    """Percentage of goals fully met (0.0-1.0)."""

    consistency_score: float | None = None
    """Consistency of improvement over time (0.0-1.0)."""

    confidence_score: float
    """AI confidence in recommendation (0.0-1.0)."""

    # Goal-level analysis
    goal_outcomes: dict | None = None
    """Final status by goal_id.

    Dict structure:
        goal_id -> {
            "final_status": GoalStatus value,
            "improvement_trajectory": "improving" | "stable" | "declining",
            "evidence_ids": list[str]
        }
    """

    # Risk assessment
    risk_factors: list[str] | None = None
    """Risk factors considered in recommendation."""

    mitigating_factors: list[str] | None = None
    """Factors that support positive outcome."""

    # Contextual factors
    external_factors: str | None = None
    """External factors affecting performance."""

    accommodation_compliance: bool | None = None
    """Whether any required accommodations were provided."""

    # Review metadata
    analysis_date: datetime = Field(default_factory=datetime.utcnow)
    """When this analysis was generated."""

    reviewed_by_id: FK[Person] | None = None
    """HR/Manager who reviewed the recommendation."""

    review_notes: str | None = None
    """Notes from human review of AI recommendation."""

    # Decision
    final_decision: PIPOutcome | None = None
    """Actual decision made (may differ from recommendation)."""

    decision_date: datetime | None = None
    """When the final decision was made."""

    decision_by_id: FK[Person] | None = None
    """Person who made the final decision."""


@register_entity("pip_recommendations")
class PIPOutcomeRecommendation(Entity):
    """Entity representing a PIP outcome recommendation."""

    content: PIPOutcomeRecommendationContent


# ---------------------------------------------------------------------------
# PIPDecision (Immutable)
# ---------------------------------------------------------------------------


class PIPDecisionContent(TenantAware):
    """Content for a PIP terminal decision.

    Immutable record of the final employment decision following a PIP.
    Includes approval chain and legal review status for terminations.

    Gate conditions:
        - Termination requires HR Director/CHRO approval
        - Legal review required if risk flags present (protected class, etc.)
    """

    # Relationship
    pip_plan_id: FK[PIPPlan]
    """The PIP plan this decision concludes."""

    subject_id: FK[Person]
    """The employee subject of this decision."""

    # Decision
    decision: PIPOutcome
    """Final decision: continue_employment, extend_pip, role_change, or separation."""

    rationale: str
    """Detailed rationale for the decision."""

    # Approval chain (required for termination)
    decided_by_id: FK[Person]
    """Person who made the final decision."""

    hr_approved_by_id: FK[Person] | None = None
    """HR Director/CHRO who approved (required for separation)."""

    # Legal review (required if risk flags present)
    legal_reviewed: bool = False
    """Whether legal counsel reviewed this decision."""

    legal_reviewed_by_id: FK[Person] | None = None
    """Legal counsel who reviewed (if applicable)."""

    # Risk assessment
    risk_flags: list[str] | None = None
    """Risk flags identified (protected_class, on_leave, etc.)."""

    # Evidence chain
    evidence_ids: list[str] | None = None
    """IDs of evidence artifacts supporting this decision."""


@register_entity("pip_decisions", immutable=True)
class PIPDecision(Entity):
    """Immutable entity representing a PIP terminal decision.

    Once recorded, decisions cannot be modified - corrections
    require supersession (new decision referencing the original).
    """

    content: PIPDecisionContent
