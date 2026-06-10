"""Evidence entity - immutable audit artifacts."""

from __future__ import annotations

from datetime import datetime

from kron.types import FK

from ..entity import Entity, register_entity
from ..shared import OptSubjectAware, TenantAware, User


class EvidenceContent(TenantAware, OptSubjectAware):
    """Content for evidence artifacts.

    Immutable proof that justifies decisions. Used in legal proceedings.

    Supersession:
        Original remains unchanged. Correction = new evidence
        with supersedes_id pointing back. Forward lookup via
        SELECT WHERE supersedes_id = original.id.
    """

    evidence_type: str
    """Classification key (e.g., vendor.call, compliance.consent)."""

    # Content
    title: str | None = None
    data: dict | None = None
    source: str | None = None
    source_id: str | None = None
    file_hash: str | None = None

    # Collection metadata
    collected_at: datetime | None = None
    collected_by_id: FK[User] | None = None
    expires_at: datetime | None = None

    # Supersession (backward pointer only)
    supersedes_id: FK[Evidence] | None = None


@register_entity("evidences", immutable=True)
class Evidence(Entity):
    """Immutable evidence artifact. Insert-only, corrections via supersession."""

    content: EvidenceContent

    # Composite indexes for common query patterns
    _indexes = [
        # Fast lookup by tenant + evidence_type (audit queries)
        {"columns": ["tenant_id", "evidence_type"]},
        # Fast lookup by subject + evidence_type (subject timeline)
        {"columns": ["subject_id", "evidence_type"]},
        # Fast lookup by tenant + created_at (chronological audit)
        {"columns": ["tenant_id", "created_at"]},
    ]
