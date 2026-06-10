"""Charter entity - tenant governance documents.

Charters define compliance workflows as declarative specifications
that compile to validated DAGs. Each charter belongs to a tenant
and defines phases, gates, evidence requirements, and role bindings.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from kron.types import FK

from ..entity import Entity, register_entity
from ..shared import TenantAware, User

__all__ = (
    "Charter",
    "CharterContent",
    "CharterStatus",
)


class CharterStatus:
    """Charter lifecycle states."""

    DRAFT = "draft"
    """Charter is being edited, not yet active."""

    ACTIVE = "active"
    """Charter is active and enforcing workflows."""

    SUPERSEDED = "superseded"
    """Charter has been replaced by a newer version."""

    ARCHIVED = "archived"
    """Charter is no longer in use."""


class CharterContent(TenantAware):
    """Content for charter governance documents.

    Charters are versioned compliance workflow specifications.
    The source is the DSL text, compiled data is the parsed/validated result.
    """

    # Identity
    name: str
    """Human-readable charter name."""

    charter_version: str = "1.0"
    """Semantic version of this charter."""

    description: str | None = None
    """Optional description of the charter's purpose."""

    # Source and compilation
    source: str
    """Original DSL source text."""

    compiled_data: dict | None = None
    """Compiled charter data (workflows, phases, features, etc.)."""

    # Status
    status: str = CharterStatus.DRAFT
    """Current lifecycle status."""

    # Authorship
    created_by_id: FK[User] | None = None
    """User who created this charter."""

    published_at: datetime | None = None
    """When the charter was published (moved to ACTIVE)."""

    published_by_id: FK[User] | None = None
    """User who published this charter."""

    # Versioning
    supersedes_id: FK[Charter] | None = None
    """ID of charter this supersedes (for version upgrades)."""

    # Validation
    is_valid: bool = False
    """Whether the charter passed compilation and validation."""

    validation_errors: list[str] = Field(default_factory=list)
    """Errors from compilation/validation if any."""


@register_entity("charters")
class Charter(Entity):
    """Charter governance document.

    Defines compliance workflows for a tenant. Charters are mutable
    while in DRAFT status, but once published (ACTIVE), changes
    require creating a new version that supersedes the old one.
    """

    content: CharterContent
