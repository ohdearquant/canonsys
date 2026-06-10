"""Interview and Scorecard workflow entities.

Provides entities for structured interview workflows with AI-assisted
scoring and mandatory bias analysis for employment decisions.

Regulatory basis:
    - NYC LL144 (Local Law 144): Automated Employment Decision Tools (AEDT)
      requiring bias audits and candidate notification
    - EEOC Uniform Guidelines: Adverse impact analysis, job-relatedness
    - FCRA: Consent requirements before background investigations
    - GDPR Art. 22: Automated individual decision-making rights
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from kron.types import FK
from kron.utils import now_utc

from ...consent import ConsentToken
from ...entity import Entity, register_entity
from ...shared import Person, TenantAware, User

__all__ = (
    # Enums
    "InterviewStatus",
    "BiasFlag",
    "Recommendation",
    # Interview
    "InterviewContent",
    "Interview",
    # Scorecard
    "ScorecardContent",
    "Scorecard",
    # Bias Analysis
    "BiasAnalysisContent",
    "BiasAnalysis",
    # Competency Assessment
    "CompetencyAssessmentContent",
    "CompetencyAssessment",
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class InterviewStatus(StrEnum):
    """Interview lifecycle states.

    Flow: PENDING_CONSENT -> READY -> IN_PROGRESS -> SCORED -> COMPLETED

    PENDING_CONSENT: Awaiting required consent (AI scoring, recording)
    READY: Consent obtained, interview can begin
    IN_PROGRESS: Interview is actively occurring
    SCORED: AI scoring complete, awaiting review
    COMPLETED: All scoring and review finalized
    """

    PENDING_CONSENT = "pending_consent"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    SCORED = "scored"
    COMPLETED = "completed"


class BiasFlag(StrEnum):
    """Bias severity levels from automated analysis.

    NYC LL144 requires bias audits for AEDTs. Severity determines
    required actions:

    NONE: No significant bias detected
    LOW: Minor disparities within acceptable thresholds
    MODERATE: Significant disparities requiring human review
    CRITICAL: Severe disparities - must not use for decision
    """

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    CRITICAL = "critical"


class Recommendation(StrEnum):
    """Hiring recommendation from scorecard evaluation.

    Maps to standard hiring funnel outcomes:

    STRONG_YES: Exceptional candidate, prioritize hiring
    YES: Meets criteria, recommend proceeding
    MAYBE: Mixed signals, requires additional evaluation
    NO: Does not meet criteria, do not proceed
    STRONG_NO: Significant concerns, immediate rejection
    """

    STRONG_YES = "strong_yes"
    YES = "yes"
    MAYBE = "maybe"
    NO = "no"
    STRONG_NO = "strong_no"


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------


class InterviewContent(TenantAware):
    """Content for interview records.

    Tracks a scheduled or completed interview session between a candidate
    and interviewer. Links to consent tokens for AI scoring/recording.

    Consent Requirements (FCRA, NYC LL144):
        - AI_SCORING consent required before AI evaluation
        - INTERVIEW_RECORDING consent required before recording
        - Consent must be active at interview time

    NYC LL144 Compliance:
        - Must notify candidate of AEDT use >= 10 days before
        - Must provide alternative assessment option if requested
    """

    # Participants
    candidate_id: FK[Person]
    """The candidate being interviewed (data subject)."""

    interviewer_id: FK[Person]
    """The person conducting the interview."""

    # Scheduling
    scheduled_at: datetime | None = None
    """Planned interview time. None for unscheduled."""

    started_at: datetime | None = None
    """Actual interview start time."""

    ended_at: datetime | None = None
    """Actual interview end time."""

    # Status tracking
    status: InterviewStatus = InterviewStatus.PENDING_CONSENT
    """Current interview lifecycle state."""

    # Consent linkage
    consent_token_id: FK[ConsentToken] | None = None
    """Primary consent token (e.g., AI_SCORING). Additional consents tracked separately."""

    # Content references
    transcript_ref: str | None = None
    """Reference to transcript storage (S3 key, blob path, etc.)."""

    recording_ref: str | None = None
    """Reference to recording storage (if consent granted)."""

    # Interview metadata
    interview_type: str | None = None
    """Interview type: technical, behavioral, culture, panel, etc."""

    job_requisition_id: str | None = None
    """Link to job posting/requisition being interviewed for."""

    notes: str | None = None
    """Interviewer notes (free text, not used for scoring)."""


@register_entity("interviews")
class Interview(Entity):
    """Entity representing a candidate interview session.

    Captures the interview event with participant tracking, consent
    verification, and content references. Scorecards link back to
    interviews for evaluation.
    """

    content: InterviewContent


# ---------------------------------------------------------------------------
# Scorecard
# ---------------------------------------------------------------------------


class ScorecardContent(TenantAware):
    """Content for interview scorecards.

    Structured evaluation of interview performance with competency
    ratings and hiring recommendation. May be human-generated or
    AI-assisted (requires consent + bias analysis).

    AI Scoring Requirements (NYC LL144):
        - Candidate must consent to AI evaluation
        - Bias analysis must be performed and documented
        - Human review required if bias_flag >= MODERATE

    Evidence Requirements:
        - All evidence supporting the score must be linked
        - Evidence must be sealed before decision certificate
    """

    # Link to interview
    interview_id: FK[Interview]
    """The interview being evaluated."""

    # Evaluator
    evaluator_id: FK[Person] | None = None
    """Person who completed/approved the scorecard. None if AI-only."""

    is_ai_generated: bool = False
    """True if scorecard was generated by AI (requires consent)."""

    # Competency ratings
    competency_ratings: dict[str, int] = Field(default_factory=dict)
    """Competency name -> rating (typically 1-5 scale).
    Example: {"technical_skills": 4, "communication": 3, "leadership": 5}
    """

    # Overall assessment
    overall_score: float | None = None
    """Aggregate score (0.0-1.0 or 1-5 scale per org policy)."""

    recommendation: Recommendation | None = None
    """Hiring recommendation based on evaluation."""

    # Confidence metrics
    confidence_score: float | None = None
    """AI confidence in scoring (0.0-1.0). None for human-only scorecards."""

    # Evidence linkage
    evidence_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of Evidence records supporting this evaluation."""

    # Timestamps
    scored_at: datetime = Field(default_factory=now_utc)
    """When the scorecard was completed."""

    reviewed_at: datetime | None = None
    """When human review was completed (if applicable)."""

    reviewed_by_id: FK[User] | None = None
    """User who performed human review."""

    # Additional context
    strengths: list[str] = Field(default_factory=list)
    """Key strengths identified."""

    areas_for_improvement: list[str] = Field(default_factory=list)
    """Areas where candidate could improve."""

    notes: str | None = None
    """Additional evaluator notes."""


@register_entity("scorecards")
class Scorecard(Entity):
    """Entity representing an interview evaluation scorecard.

    Contains structured competency ratings, overall assessment,
    and hiring recommendation. Links to evidence for audit trail.
    """

    content: ScorecardContent


# ---------------------------------------------------------------------------
# Bias Analysis
# ---------------------------------------------------------------------------


class BiasAnalysisContent(TenantAware):
    """Content for bias analysis of scorecards.

    Mandatory for AI-generated scorecards per NYC LL144. Evaluates
    potential adverse impact across protected groups.

    NYC LL144 Requirements:
        - Annual bias audit by independent auditor
        - Impact ratio analysis for selection rates
        - Public disclosure of audit results

    EEOC Four-Fifths Rule:
        Selection rate for protected group must be >= 80% of
        highest group's rate. Below threshold = adverse impact.
    """

    # Link to scorecard
    scorecard_id: FK[Scorecard]
    """The scorecard being analyzed for bias."""

    # Analysis results
    bias_flag: BiasFlag = BiasFlag.NONE
    """Overall bias severity determination."""

    bias_type: str | None = None
    """Type of bias detected: gender, race, age, disability, etc."""

    # Affected groups
    affected_groups: list[str] = Field(default_factory=list)
    """Protected groups potentially affected.
    Example: ["women", "candidates over 40", "Hispanic"]
    """

    # Statistical analysis
    impact_ratios: dict[str, float] = Field(default_factory=dict)
    """Group -> impact ratio. Below 0.8 indicates adverse impact.
    Example: {"women": 0.75, "candidates_over_40": 0.82}
    """

    sample_size: int | None = None
    """Number of scorecards in analysis cohort."""

    # Recommendations
    recommendations: list[str] = Field(default_factory=list)
    """Recommended actions to address bias.
    Example: ["Re-evaluate criteria weighting", "Increase sample diversity"]
    """

    # Review requirements
    reviewer_required: bool = False
    """True if bias severity requires human review before decision."""

    reviewed_by_id: FK[User] | None = None
    """User who reviewed bias analysis (if reviewer_required)."""

    reviewed_at: datetime | None = None
    """When bias review was completed."""

    review_notes: str | None = None
    """Notes from bias review."""

    # Analysis metadata
    analyzed_at: datetime = Field(default_factory=now_utc)
    """When analysis was performed."""

    analysis_model_version: str | None = None
    """Version of bias detection model used."""

    methodology: str | None = None
    """Description of analysis methodology."""


@register_entity("bias_analyses")
class BiasAnalysis(Entity):
    """Entity representing bias analysis of a scorecard.

    Required for AI-assisted scoring decisions. Documents potential
    adverse impact and required remediation actions.
    """

    content: BiasAnalysisContent


# ---------------------------------------------------------------------------
# Competency Assessment
# ---------------------------------------------------------------------------


class CompetencyAssessmentContent(TenantAware):
    """Content for individual competency assessments.

    Detailed evaluation of a single competency within a scorecard.
    Provides granular evidence and confidence for each dimension.

    EEOC Job-Relatedness:
        Competencies must be demonstrably related to job requirements.
        Evidence excerpts should map to specific job criteria.
    """

    # Link to scorecard
    scorecard_id: FK[Scorecard]
    """The parent scorecard containing this assessment."""

    # Competency identification
    competency_name: str
    """Name of competency: technical_skills, communication, leadership, etc."""

    competency_definition: str | None = None
    """What this competency measures (for audit clarity)."""

    # Rating
    rating: int
    """Competency rating (scale defined by org, typically 1-5)."""

    max_rating: int = 5
    """Maximum possible rating for normalization."""

    # Evidence
    evidence_excerpts: list[str] = Field(default_factory=list)
    """Direct quotes or observations supporting the rating.
    Example: ["Explained distributed systems clearly", "Asked clarifying questions"]
    """

    evidence_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of Evidence records supporting this assessment."""

    # Confidence
    confidence: float | None = None
    """Confidence in assessment (0.0-1.0). None for human assessments."""

    # Assessment metadata
    assessed_at: datetime = Field(default_factory=now_utc)
    """When assessment was made."""

    assessed_by_id: FK[Person] | None = None
    """Person who made this assessment. None if AI-generated."""

    is_ai_generated: bool = False
    """True if assessment was AI-generated."""

    # Job relatedness (EEOC compliance)
    job_criteria_ref: str | None = None
    """Reference to job criteria this competency maps to."""


@register_entity("competency_assessments")
class CompetencyAssessment(Entity):
    """Entity representing assessment of a single competency.

    Provides granular evaluation with evidence and confidence
    for audit trail and bias analysis.
    """

    content: CompetencyAssessmentContent
