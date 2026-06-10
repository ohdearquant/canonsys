"""Hiring brief workflow entities.

Entities for AI-assisted hiring brief generation with market context
and evidence chain support.

Business context:
    - HiringBrief captures role requirements with AI-generated insights
    - MarketContext provides labor market intelligence for salary/talent decisions
    - Evidence links connect briefs to supporting compliance records
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from kron.types import FK

from ...document import Document
from ...entity import Entity, register_entity
from ...shared import TenantAware

__all__ = (
    "HiringBrief",
    "HiringBriefContent",
    "MarketContext",
    "MarketContextContent",
)


class HiringBriefContent(TenantAware):
    """Content for hiring briefs.

    Hiring briefs are comprehensive role specifications that combine
    stakeholder requirements with AI-generated market intelligence.
    Evidence links ensure auditability of AI-assisted decisions.
    """

    role_title: str
    """The job title for this hiring brief."""

    department: str
    """Department or team the role belongs to."""

    brief_content: str
    """The full hiring brief content (requirements, qualifications, etc.)."""

    market_context: str | None = None
    """Summary of market context influencing this brief."""

    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    """AI-assessed quality/completeness score (0-1)."""

    evidence_ids: list[UUID] | None = None
    """IDs of Evidence records supporting this brief."""

    document_id: FK[Document] | None = None
    """Document record ID linking this brief to its provenance chain."""

    status: str = "draft"
    """Brief status: draft, review, approved, archived."""

    hiring_manager_notes: str | None = None
    """Notes from the hiring manager."""

    compensation_range_min: int | None = None
    """Minimum compensation (annual, in cents to avoid float issues)."""

    compensation_range_max: int | None = None
    """Maximum compensation (annual, in cents)."""


@register_entity("hiring_briefs")
class HiringBrief(Entity):
    """Entity representing a hiring brief."""

    content: HiringBriefContent


class MarketContextContent(TenantAware):
    """Market intelligence context for a hiring brief.

    Provides labor market data to inform compensation, talent availability,
    and competitive positioning for a specific role.
    """

    brief_id: FK[HiringBrief]
    """The hiring brief this context supports."""

    competitor_analysis: str | None = None
    """Analysis of competitor hiring for similar roles."""

    talent_landscape: str | None = None
    """Overview of available talent pool and supply/demand dynamics."""

    salary_benchmarks: dict | None = None
    """Structured salary data: {percentile: amount, source: str, date: str}."""

    geographic_factors: str | None = None
    """Location-specific considerations (cost of living, remote trends)."""

    industry_trends: str | None = None
    """Relevant industry hiring trends affecting this role."""

    data_sources: list[str] | None = None
    """Sources used to compile this market context."""


@register_entity("market_contexts")
class MarketContext(Entity):
    """Entity representing market context for a hiring brief."""

    content: MarketContextContent
