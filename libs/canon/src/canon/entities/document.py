"""Document entity - cross-cutting provenance layer for charter workflow outputs.

Every charter workflow that produces a structured artifact (hiring brief, PIP report,
calibration analysis) gets a Document record that answers: "what workflow produced this,
what evidence supports it, is it certified?"

Architecture:
    CharterRun (workflow instance)
      +-- PhaseExecution[] (each phase)
      |     +-- Evidence[] (what happened at each step)
      +-- Document (the output artifact)
            +-- source_entity_type -> "hiring_brief" | "pip_plan" | ...
            +-- source_entity_id -> HiringBrief.id (domain content)
            +-- evidence_ids -> [Evidence.id, ...] (supporting evidence)
            +-- certificate_id -> DecisionCertificate.id (if certified)
            +-- status -> draft | finalized | certified

Domain entities (HiringBrief, PIPPlan) hold typed business content.
Document is the audit layer that provides provenance and certification tracking.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from kron.types import FK

from .charter.run import CharterRun
from .entity import Entity, register_entity
from .shared import OptSubjectAware, TenantAware, User

__all__ = (
    "Document",
    "DocumentContent",
    "DocumentStatus",
)


class DocumentStatus:
    """Document lifecycle states."""

    DRAFT = "draft"
    """Initial state - workflow in progress or output not yet reviewed."""

    FINALIZED = "finalized"
    """Output reviewed and accepted, evidence chain complete."""

    CERTIFIED = "certified"
    """DecisionCertificate minted (only for charters with `certify immutable`)."""


class DocumentContent(TenantAware, OptSubjectAware):
    """Content for workflow output documents.

    Links a domain entity (the business content) to its provenance:
    which workflow produced it, what evidence backs it, and whether
    it's been certified.
    """

    document_type: str
    """Domain type key: 'hiring_brief', 'pip_report', 'calibration', etc."""

    title: str
    """Human-readable title for display."""

    # Workflow provenance
    charter_run_id: FK[CharterRun] | None = None
    """Which charter workflow execution produced this document."""

    # Polymorphic source entity reference
    source_entity_type: str | None = None
    """Table name of the domain entity (e.g., 'hiring_briefs')."""

    source_entity_id: UUID | None = None
    """ID of the domain entity holding the business content."""

    # Evidence binding
    evidence_ids: list[UUID] = Field(default_factory=list)
    """Evidence records supporting this document (one per phase)."""

    # Certification (only for charters with `certify immutable`)
    certificate_id: UUID | None = None
    """DecisionCertificate ID if this document has been certified."""

    # Status
    status: str = DocumentStatus.DRAFT
    """Lifecycle status: draft -> finalized -> certified."""

    # Quality
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    """AI quality assessment score (0-1), from quality_gate phase."""

    # Generation metadata
    generation_metadata: dict | None = None
    """Model versions, timing, token usage, etc."""

    # Finalization
    finalized_at: datetime | None = None
    """When the document was finalized."""

    finalized_by_id: FK[User] | None = None
    """Who finalized (user or system)."""

    # Certification
    certified_at: datetime | None = None
    """When the document was certified (DecisionCertificate minted)."""

    certified_by_id: FK[User] | None = None
    """Who certified (user or system)."""


@register_entity("documents")
class Document(Entity):
    """Cross-cutting provenance entity for charter workflow outputs.

    Every charter workflow that produces a structured artifact gets a
    Document record for audit trail, evidence binding, and optional
    certification.
    """

    content: DocumentContent

    _indexes = [
        {"columns": ["tenant_id", "document_type"]},
        {"columns": ["charter_run_id"]},
        {"columns": ["source_entity_type", "source_entity_id"]},
        {"columns": ["certificate_id"]},
    ]
