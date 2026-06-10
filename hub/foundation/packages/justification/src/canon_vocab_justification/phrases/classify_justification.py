"""Classify justification text into regulatory categories.

Complete vertical slice:
- Analyzes justification text for regulatory indicators
- Checks tenant-specific classification rules
- Returns classification with confidence and escalation requirements
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import JustificationClass

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ClassifyJustificationSpecs", "classify_justification"]


class ClassifyJustificationSpecs(BaseModel):
    """Specs for classify justification phrase."""

    # inputs
    justification_text: str
    context: str
    # outputs
    classification: JustificationClass | None = None
    confidence: float | None = None
    indicators: tuple[str, ...] | None = None
    requires_escalation: bool | None = None


# Keyword indicators for each classification
_CLASSIFICATION_INDICATORS: dict[JustificationClass, tuple[list[str], bool]] = {
    "legal_requirement": (
        [
            "law requires",
            "statute",
            "legal obligation",
            "court order",
            "judicial",
            "litigation",
            "subpoena",
            "legal hold",
            "regulatory mandate",
            "compliance requirement",
            "legally required",
            "statutory requirement",
            "mandated by law",
        ],
        False,  # No escalation - clear legal basis
    ),
    "regulatory": (
        [
            "regulation",
            "regulatory",
            "compliance",
            "audit",
            "sox",
            "gdpr",
            "hipaa",
            "fcra",
            "eeoc",
            "osha",
            "sec",
            "finra",
            "regulator",
            "examination",
            "enforcement action",
        ],
        False,  # No escalation - clear regulatory basis
    ),
    "business_convenience": (
        [
            "business need",
            "efficiency",
            "cost reduction",
            "streamline",
            "simplify",
            "productivity",
            "convenience",
            "faster",
            "easier",
            "operational",
            "process improvement",
            "resource optimization",
        ],
        True,  # Requires escalation - needs additional justification
    ),
    "cosmetic": (
        [
            "looks better",
            "cleaner",
            "nicer",
            "preference",
            "aesthetic",
            "appearance",
            "format",
            "style",
            "presentation",
            "visual",
        ],
        True,  # Requires escalation - weak justification
    ),
}


@canon_phrase(
    Operable.from_structure(ClassifyJustificationSpecs),
    inputs={"justification_text", "context"},
    outputs={"classification", "confidence", "indicators", "requires_escalation"},
)
async def classify_justification(
    options: ClassifyJustificationSpecs,
    ctx: RequestContext,
) -> dict:
    """Classify a justification into legal, regulatory, business, or cosmetic.

    Analyzes justification text to determine its basis and whether it
    requires additional scrutiny or escalation. Prevents weak justifications
    from bypassing controls.

    Args:
        options: Classification options (justification_text, context)
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with classification, confidence, indicators, requires_escalation.

    Regulatory:
        - SOX Section 404 (Controls over exceptions and waivers)
        - COSO Framework (Exception handling)
        - Audit standards (Documentation of control overrides)
    """
    text_lower = options.justification_text.lower()
    found_indicators: dict[JustificationClass, list[str]] = {
        "legal_requirement": [],
        "regulatory": [],
        "business_convenience": [],
        "cosmetic": [],
    }

    # Scan for indicators
    for classification, (keywords, _) in _CLASSIFICATION_INDICATORS.items():
        for keyword in keywords:
            if keyword in text_lower:
                found_indicators[classification].append(keyword)

    # Determine best classification
    best_class: JustificationClass = "business_convenience"  # Default
    max_count = 0
    total_indicators = 0

    for classification, indicators in found_indicators.items():
        total_indicators += len(indicators)
        if len(indicators) > max_count:
            max_count = len(indicators)
            best_class = classification

    # Calculate confidence
    if total_indicators == 0:
        # No indicators found - classify as business convenience with low confidence
        confidence = 0.3
        requires_escalation = True
    else:
        # Confidence based on ratio of indicators for best class
        confidence = min(0.95, 0.5 + (max_count / max(total_indicators, 1)) * 0.45)
        _, requires_escalation = _CLASSIFICATION_INDICATORS[best_class]

    # Check for tenant-specific classification rules
    rows = await fetch(
        """
        SELECT classification, requires_escalation
        FROM justification_classification_rules
        WHERE tenant_id = $1 AND context = $2
        AND $3 ~* pattern
        ORDER BY priority DESC
        LIMIT 1
        """,
        ctx.tenant_id,
        options.context,
        options.justification_text,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if rows:
        row = rows[0]
        best_class = row["classification"]
        requires_escalation = row["requires_escalation"]
        confidence = 0.95  # High confidence for explicit rule match

    return {
        "classification": best_class,
        "confidence": confidence,
        "indicators": tuple(found_indicators[best_class]),
        "requires_escalation": requires_escalation,
    }
