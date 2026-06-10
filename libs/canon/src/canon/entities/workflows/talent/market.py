"""Market mapping workflow entities.

Entities for competitive intelligence and talent market analysis.

Business context:
    - MarketMap provides high-level industry/geographic talent landscapes
    - MarketAnalysis captures specific analytical findings with confidence scores
    - Quality scores enable AI output monitoring and bias detection
"""

from __future__ import annotations

from pydantic import Field

from kron.types import FK

from ...entity import Entity, register_entity
from ...shared import TenantAware

__all__ = (
    "MarketAnalysis",
    "MarketAnalysisContent",
    "MarketMap",
    "MarketMapContent",
)


class MarketMapContent(TenantAware):
    """Content for market maps.

    Market maps provide comprehensive views of talent landscapes,
    competitor positioning, and talent pool analysis for strategic
    hiring decisions.
    """

    title: str
    """Descriptive title for this market map."""

    industry: str
    """Primary industry focus (e.g., 'fintech', 'healthcare', 'saas')."""

    geography: str
    """Geographic scope (e.g., 'US', 'NYC Metro', 'Remote-US', 'Global')."""

    analysis: dict | None = None
    """Structured analysis data: findings, metrics, visualizations."""

    competitor_list: list[str] | None = None
    """List of competitor companies tracked in this map."""

    talent_pools: list[str] | None = None
    """Identified talent pools (companies, universities, communities)."""

    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    """AI-assessed quality/completeness score (0-1)."""

    status: str = "draft"
    """Map status: draft, review, published, archived."""

    data_freshness_days: int | None = None
    """Age of underlying data in days. Older data may need refresh."""


@register_entity("market_maps")
class MarketMap(Entity):
    """Entity representing a market map."""

    content: MarketMapContent


class MarketAnalysisContent(TenantAware):
    """Individual analysis findings for a market map.

    Captures specific analytical insights with confidence scoring
    to enable AI output quality monitoring and decision auditability.
    """

    map_id: FK[MarketMap]
    """The market map this analysis belongs to."""

    analysis_type: str
    """Type of analysis: competitor, talent_pool, salary, trend, risk."""

    findings: str
    """The analysis findings/conclusions."""

    confidence: float = Field(ge=0.0, le=1.0)
    """Confidence score for this analysis (0-1)."""

    supporting_data: dict | None = None
    """Raw data supporting this analysis."""

    methodology: str | None = None
    """Description of analysis methodology used."""

    limitations: str | None = None
    """Known limitations or caveats for this analysis."""

    data_sources: list[str] | None = None
    """Sources used for this specific analysis."""


@register_entity("market_analyses")
class MarketAnalysis(Entity):
    """Entity representing an analysis finding within a market map."""

    content: MarketAnalysisContent
