"""Job requisition and candidacy workflow entities.

Entities for tracking job postings and candidate applications with
compliance evidence chain support.

Business context:
    - Job represents an open position/requisition
    - Candidacy links a Person to a Job (M:N with status tracking)
    - FK to HiringBrief for requirements traceability
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field

from kron.types import FK
from kron.utils import now_utc

from ...entity import Entity, register_entity
from ...shared import OptSubjectAware, TenantAware, User
from .brief import HiringBrief

__all__ = (
    "Candidacy",
    "CandidacyContent",
    "CandidacyStatus",
    "Job",
    "JobContent",
    "JobStatus",
    "WorkplaceModel",
)


class JobStatus(str, Enum):
    """Job requisition lifecycle states."""

    DRAFT = "draft"
    OPEN = "open"
    ON_HOLD = "on_hold"
    FILLED = "filled"
    CANCELLED = "cancelled"


class WorkplaceModel(str, Enum):
    """Work location classification for jurisdiction mapping."""

    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class JobContent(TenantAware):
    """Content for job requisitions.

    A Job is an open position that candidates can be considered for.
    Links to HiringBrief for requirements and compliance traceability.

    Compliance note:
        NYC LL144 requires disclosure when AI is used in hiring decisions.
        Evidence links track AI involvement for audit.
    """

    title: str
    """Job title."""

    department: str | None = None
    """Department or team."""

    location: str | None = None
    """Work location (city, state, or "Remote")."""

    workplace_model: WorkplaceModel = WorkplaceModel.ONSITE
    """Remote, hybrid, or onsite."""

    # Linkage to requirements
    brief_id: FK[HiringBrief] | None = None
    """Optional link to the hiring brief that defines requirements."""

    # Status
    status: JobStatus = JobStatus.DRAFT
    opened_at: datetime | None = None
    closed_at: datetime | None = None

    # Headcount
    headcount: int = 1
    """Number of positions to fill."""

    filled_count: int = 0
    """Number of positions filled so far."""

    # Compensation (in cents to avoid float issues)
    compensation_min: int | None = None
    compensation_max: int | None = None
    compensation_currency: str = "USD"

    # Description
    description: str | None = None
    """Job description/requirements."""

    seniority_level: str | None = None
    """Seniority level (e.g. junior, mid, senior, staff, principal)."""

    requirements: list[str] | None = None
    """Structured list of job requirements."""

    # Metadata
    external_job_id: str | None = None
    """External ATS/HRIS job ID for integration."""

    evidence_ids: list[UUID] | None = None
    """IDs of Evidence records (AI disclosures, compliance attestations)."""


@register_entity("jobs")
class Job(Entity):
    """Entity representing a job requisition."""

    content: JobContent


class CandidacyStatus(str, Enum):
    """Candidacy lifecycle states.

    Tracks progression through hiring funnel.
    Each transition should emit Evidence for audit trail.
    """

    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFER_PENDING = "offer_pending"
    OFFER_EXTENDED = "offer_extended"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class CandidacyContent(TenantAware, OptSubjectAware):
    """Content for candidacy records.

    Junction entity linking a Person (candidate) to a Job.
    Tracks progression through hiring funnel with evidence chain.

    Compliance notes:
        - FCRA: Consent required before background check (verify_consent)
        - NYC LL144: AI scoring disclosure required (AI_SCORING consent scope)
        - EEOC: Rejection reasons must be documented for adverse impact analysis

    The subject_id (FK[Person]) comes from OptSubjectAware mixin.
    """

    job_id: FK[Job]
    """The job this candidacy is for."""

    # Status tracking
    status: CandidacyStatus = CandidacyStatus.APPLIED
    applied_at: datetime = Field(default_factory=now_utc)
    status_changed_at: datetime = Field(default_factory=now_utc)
    status_changed_by_id: FK[User] | None = None

    # Source tracking
    source: str | None = None
    """How candidate was sourced: referral, linkedin, careers_page, agency."""

    source_detail: str | None = None
    """Additional source info (referrer name, agency name, etc.)."""

    # Rejection/withdrawal (for compliance documentation)
    rejection_reason: str | None = None
    """Documented reason if rejected (for EEOC compliance)."""

    withdrawal_reason: str | None = None
    """Reason if candidate withdrew."""

    # Evidence chain
    evidence_ids: list[UUID] | None = None
    """IDs of Evidence records for this candidacy."""

    # AI involvement tracking (NYC LL144)
    ai_scoring_used: bool = False
    """Whether AI/automated scoring was used."""

    ai_disclosure_sent_at: datetime | None = None
    """When AI disclosure was sent to candidate."""


@register_entity("candidacies")
class Candidacy(Entity):
    """Entity representing a candidacy (Person applied to Job)."""

    content: CandidacyContent
