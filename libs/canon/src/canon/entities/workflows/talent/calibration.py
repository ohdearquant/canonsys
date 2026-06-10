"""Calibration workflow entities.

Provides entities for managing evaluator calibration:
    CalibrationResult: Results from evaluator calibration analysis
    EvaluatorProfile: Profile of an evaluator's history and patterns

Regulatory context:
    - NYC LL144: Bias testing for automated decision tools
    - EEOC Guidelines: Consistent evaluation criteria
    - EU AI Act: Human oversight of AI-assisted decisions
"""

from __future__ import annotations

from datetime import datetime

from kron.types import FK, Enum

from ...entity import Entity, register_entity
from ...shared import Person, TenantAware

__all__ = (
    # Enums
    "BiasCategory",
    "CalibrationStatus",
    # Content models
    "CalibrationResultContent",
    "EvaluatorProfileContent",
    # Entities
    "CalibrationResult",
    "EvaluatorProfile",
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BiasCategory(Enum):
    """Categories of potential evaluator bias."""

    NONE_DETECTED = "none_detected"  # No significant bias found
    SEVERITY_BIAS = "severity_bias"  # Consistently harsh or lenient
    RECENCY_BIAS = "recency_bias"  # Over-weighting recent events
    HALO_EFFECT = "halo_effect"  # One trait influencing all ratings
    CENTRAL_TENDENCY = "central_tendency"  # Avoiding extreme ratings
    CONTRAST_EFFECT = "contrast_effect"  # Comparing to recent candidates
    SIMILARITY_BIAS = "similarity_bias"  # Favoring similar backgrounds
    DEMOGRAPHIC_PATTERN = "demographic_pattern"  # Protected class correlation


class CalibrationStatus(Enum):
    """Status of calibration analysis."""

    PENDING = "pending"  # Analysis queued
    IN_PROGRESS = "in_progress"  # Analysis running
    COMPLETED = "completed"  # Analysis finished
    FAILED = "failed"  # Analysis encountered error
    REQUIRES_REVIEW = "requires_review"  # Needs human review
    ACKNOWLEDGED = "acknowledged"  # Results reviewed and acknowledged


# ---------------------------------------------------------------------------
# CalibrationResult
# ---------------------------------------------------------------------------


class CalibrationResultContent(TenantAware):
    """Content for evaluator calibration analysis results.

    Captures the outcome of analyzing an evaluator's rating patterns
    for consistency, bias, and alignment with organizational standards.
    Used to ensure fair and consistent evaluation across candidates.
    """

    # Evaluator identification
    evaluator_id: FK[Person]
    """The evaluator being calibrated."""

    # Analysis scope
    analysis_period_start: datetime
    """Start of the analysis period."""

    analysis_period_end: datetime
    """End of the analysis period."""

    evaluations_analyzed: int
    """Number of evaluations included in analysis."""

    # Calibration scores
    calibration_score: float
    """Overall calibration score (0.0-1.0, higher = better calibrated)."""

    consistency_score: float
    """Internal consistency of ratings (0.0-1.0)."""

    alignment_score: float | None = None
    """Alignment with organizational benchmarks (0.0-1.0)."""

    inter_rater_agreement: float | None = None
    """Agreement with other evaluators on shared candidates (0.0-1.0)."""

    # Bias detection
    bias_flags: list[str]
    """List of detected bias categories (BiasCategory values)."""

    bias_details: dict | None = None
    """Detailed bias analysis by category.

    Dict structure:
        bias_category -> {
            "severity": "low" | "medium" | "high",
            "evidence": str,
            "affected_evaluations": int,
            "statistical_significance": float
        }
    """

    # Statistical analysis
    mean_rating: float | None = None
    """Evaluator's mean rating (for comparison to org mean)."""

    rating_std_dev: float | None = None
    """Standard deviation of ratings."""

    org_mean_rating: float | None = None
    """Organization mean rating for comparison."""

    percentile_rank: int | None = None
    """Evaluator's percentile rank in severity (0-100)."""

    # Analysis summary
    analysis_summary: str
    """Human-readable summary of calibration findings."""

    recommendations: list[str] | None = None
    """Recommended actions for improving calibration."""

    training_suggested: list[str] | None = None
    """Suggested training topics based on findings."""

    # Status and review
    status: CalibrationStatus = CalibrationStatus.PENDING
    """Current status of the calibration analysis."""

    analysis_completed_at: datetime | None = None
    """When the analysis was completed."""

    reviewed_by_id: FK[Person] | None = None
    """Person who reviewed the calibration results."""

    review_notes: str | None = None
    """Notes from human review."""

    acknowledged_at: datetime | None = None
    """When results were acknowledged by evaluator or manager."""


@register_entity("calibration_results")
class CalibrationResult(Entity):
    """Entity representing evaluator calibration analysis results."""

    content: CalibrationResultContent


# ---------------------------------------------------------------------------
# EvaluatorProfile
# ---------------------------------------------------------------------------


class EvaluatorProfileContent(TenantAware):
    """Content for an evaluator's profile and history.

    Tracks an evaluator's evaluation history, calibration status,
    and patterns over time. Used to inform calibration analysis
    and ensure evaluator quality.
    """

    # Evaluator identification
    person_id: FK[Person]
    """The person acting as evaluator."""

    # Evaluation history
    total_evaluations: int = 0
    """Total number of evaluations performed."""

    evaluations_last_90_days: int = 0
    """Evaluations in the last 90 days."""

    evaluations_last_year: int = 0
    """Evaluations in the last 365 days."""

    # Experience
    tenure_months: int = 0
    """Months of tenure as an evaluator."""

    first_evaluation_date: datetime | None = None
    """Date of first recorded evaluation."""

    # Organizational context
    department: str | None = None
    """Evaluator's department."""

    role: str | None = None
    """Evaluator's role (e.g., hiring_manager, recruiter, panel_member)."""

    evaluation_types: list[str] | None = None
    """Types of evaluations performed (e.g., technical, behavioral, cultural)."""

    # Calibration status
    last_calibration_at: datetime | None = None
    """When the evaluator was last calibrated."""

    last_calibration_score: float | None = None
    """Most recent calibration score (0.0-1.0)."""

    calibration_trend: str | None = None
    """Trend in calibration: improving, stable, declining."""

    calibrations_completed: int = 0
    """Number of calibration cycles completed."""

    # Performance metrics
    average_rating_given: float | None = None
    """Average rating given across all evaluations."""

    rating_consistency: float | None = None
    """Consistency of ratings over time (0.0-1.0)."""

    feedback_quality_score: float | None = None
    """Quality of written feedback (0.0-1.0)."""

    # Flags and notes
    requires_recalibration: bool = False
    """Whether evaluator needs recalibration."""

    recalibration_reason: str | None = None
    """Reason for requiring recalibration."""

    active_bias_flags: list[str] | None = None
    """Currently active bias flags from most recent calibration."""

    training_completed: list[str] | None = None
    """Training modules completed."""

    notes: str | None = None
    """Administrative notes about the evaluator."""

    # Status (note: using profile_active to avoid conflict with ContentMeta.is_active)
    profile_active: bool = True
    """Whether evaluator profile is currently active."""

    deactivated_at: datetime | None = None
    """When evaluator was deactivated."""

    deactivation_reason: str | None = None
    """Reason for deactivation."""


@register_entity("evaluator_profiles")
class EvaluatorProfile(Entity):
    """Entity representing an evaluator's profile and history."""

    content: EvaluatorProfileContent
