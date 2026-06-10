"""Signal and Story workflow entities.

Provides entities for candidate signal extraction and narrative
story generation from interview and assessment data.

Entities:
    SignalResult: Extracted candidate signals from data sources
    SkillInference: Higher-level skill assessment from signals
    CandidateStory: Narrative representation of a candidate
    StorySection: Individual sections within a candidate story

Regulatory basis:
    - EEOC Uniform Guidelines: Job-related criteria validation
    - NYC LL144: Transparency in automated decision criteria
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from kron.types import FK
from kron.utils import now_utc

from ...entity import Entity, register_entity
from ...shared import Person, TenantAware

__all__ = (
    # Signal Result
    "SignalResultContent",
    "SignalResult",
    # Skill Inference
    "SkillInferenceContent",
    "SkillInference",
    # Candidate Story
    "CandidateStoryContent",
    "CandidateStory",
    # Story Section
    "StorySectionContent",
    "StorySection",
)


# ---------------------------------------------------------------------------
# Signal Result
# ---------------------------------------------------------------------------


class SignalResultContent(TenantAware):
    """Content for signal extraction results.

    Captures structured signals extracted from candidate data
    (resumes, interviews, assessments) for evaluation.
    """

    # Subject
    candidate_id: FK[Person]
    """The candidate this signal is about."""

    # Signal identification
    signal_type: str
    """Type of signal: skill, experience, education, certification, etc."""

    signal_name: str
    """Specific signal name: python, leadership, aws_certified, etc."""

    # Extracted value
    signal_value: str | None = None
    """Extracted value or indicator."""

    confidence: float | None = None
    """Confidence in extraction (0.0-1.0)."""

    # Source tracking
    source_type: str | None = None
    """Where signal was extracted from: resume, interview, assessment, etc."""

    source_ref: str | None = None
    """Reference to source document/record."""

    evidence_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of Evidence records supporting this signal."""

    # Extraction metadata
    extracted_at: datetime = Field(default_factory=now_utc)
    """When signal was extracted."""

    model_version: str | None = None
    """Version of extraction model used."""


@register_entity("signal_results")
class SignalResult(Entity):
    """Entity representing an extracted candidate signal.

    Captures structured data points extracted from candidate
    materials for use in evaluation and matching.
    """

    content: SignalResultContent


# ---------------------------------------------------------------------------
# Skill Inference
# ---------------------------------------------------------------------------


class SkillInferenceContent(TenantAware):
    """Content for skill inference from signals.

    Higher-level skill assessment derived from multiple signals.
    Maps extracted signals to job-relevant competencies.
    """

    # Subject
    candidate_id: FK[Person]
    """The candidate this inference is about."""

    # Skill identification
    skill_name: str
    """Name of inferred skill: distributed_systems, team_leadership, etc."""

    skill_category: str | None = None
    """Category: technical, soft_skill, domain_knowledge, etc."""

    # Assessment
    proficiency_level: str | None = None
    """Proficiency: novice, intermediate, advanced, expert."""

    years_experience: float | None = None
    """Estimated years of experience with this skill."""

    confidence: float | None = None
    """Confidence in inference (0.0-1.0)."""

    # Supporting signals
    signal_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of SignalResult records supporting this inference."""

    evidence_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of Evidence records supporting this inference."""

    # Inference metadata
    inferred_at: datetime = Field(default_factory=now_utc)
    """When inference was made."""

    model_version: str | None = None
    """Version of inference model used."""

    # Job relevance (EEOC compliance)
    job_requisition_id: str | None = None
    """Job this skill is being assessed for."""

    relevance_score: float | None = None
    """How relevant this skill is to the job (0.0-1.0)."""


@register_entity("skill_inferences")
class SkillInference(Entity):
    """Entity representing inferred candidate skill.

    Higher-level assessment derived from multiple signals,
    mapped to job-relevant competencies.
    """

    content: SkillInferenceContent


# ---------------------------------------------------------------------------
# Candidate Story
# ---------------------------------------------------------------------------


class CandidateStoryContent(TenantAware):
    """Content for candidate narrative stories.

    Generates a structured narrative from signals and inferences
    for human-readable candidate summaries.
    """

    # Subject
    candidate_id: FK[Person]
    """The candidate this story is about."""

    # Story content
    title: str | None = None
    """Story title/headline."""

    summary: str | None = None
    """Executive summary of candidate profile."""

    # Source data
    signal_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of SignalResult records used to generate story."""

    inference_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of SkillInference records used to generate story."""

    evidence_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of Evidence records referenced in story."""

    # Generation metadata
    generated_at: datetime = Field(default_factory=now_utc)
    """When story was generated."""

    model_version: str | None = None
    """Version of generation model used."""

    # Context
    job_requisition_id: str | None = None
    """Job this story is tailored for (if any)."""

    story_type: str | None = None
    """Type: general_profile, job_match, interview_summary, etc."""


@register_entity("candidate_stories")
class CandidateStory(Entity):
    """Entity representing a candidate narrative story.

    Human-readable summary generated from structured signals
    and inferences for hiring team consumption.
    """

    content: CandidateStoryContent


# ---------------------------------------------------------------------------
# Story Section
# ---------------------------------------------------------------------------


class StorySectionContent(TenantAware):
    """Content for individual story sections.

    Granular sections within a candidate story for
    modular display and editing.
    """

    # Parent story
    story_id: FK[CandidateStory]
    """The parent story this section belongs to."""

    # Section identification
    section_type: str
    """Type: experience, skills, education, achievements, etc."""

    section_title: str | None = None
    """Display title for section."""

    section_order: int = 0
    """Order within story (0-indexed)."""

    # Content
    content_text: str | None = None
    """Main narrative content."""

    bullet_points: list[str] = Field(default_factory=list)
    """Key points in bullet form."""

    # Supporting data
    signal_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of SignalResult records supporting this section."""

    evidence_ids: list[UUID] = Field(default_factory=list)
    """UUIDs of Evidence records referenced in this section."""

    # Metadata
    generated_at: datetime = Field(default_factory=now_utc)
    """When section was generated."""

    is_editable: bool = True
    """Whether section can be manually edited."""


@register_entity("story_sections")
class StorySection(Entity):
    """Entity representing a section within a candidate story.

    Modular story component for granular display and editing.
    """

    content: StorySectionContent
