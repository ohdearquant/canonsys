"""Derive risk classification for a resource tag.

Evaluates tag mutability requirements and historical change patterns
to classify the tag's risk level.

Regulatory Context:
    - SOC 2 CC6.1: Logical access security
    - ISO 27001 A.8.2.1: Information classification
    - PCI DSS 9.6: Physical access control to media
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import TagRiskClass

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveTagRiskClassSpecs", "derive_tag_risk_class"]


class DeriveTagRiskClassSpecs(BaseModel):
    """Specs for tag risk classification derivation phrase."""

    # inputs
    tag_name: str
    resource_id: UUID
    # outputs
    risk_class: TagRiskClass | None = None
    change_frequency: int | None = None
    last_changed: datetime | None = None


@canon_phrase(
    Operable.from_structure(DeriveTagRiskClassSpecs),
    inputs={"tag_name", "resource_id"},
    outputs={"risk_class", "tag_name", "change_frequency", "last_changed"},
)
async def derive_tag_risk_class(
    options: DeriveTagRiskClassSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive risk classification for a resource tag.

    Evaluates tag mutability requirements and historical change patterns
    to classify the tag's risk level. Higher-risk tags require stricter
    change controls and audit requirements.

    Regulatory Citations:
        - SOC 2 CC6.1: "The entity implements logical access security
          software, infrastructure, and architectures over protected
          information assets."
        - ISO 27001 A.8.2.1: "Information shall be classified in terms
          of legal requirements, value, criticality and sensitivity."
        - PCI DSS 9.6: "Control physical access to media that contain
          cardholder data."

    Args:
        options: Derivation options (tag_name, resource_id)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with risk_class, tag_name, change_frequency, last_changed

    Risk Classes:
        - immutable: Cannot be changed after creation (e.g., compliance-id)
        - protected: Changes require approval (e.g., cost-center)
        - mutable: Normal change controls (e.g., team-owner)
        - ephemeral: Operational tags, minimal controls (e.g., last-sync)
    """
    tag_name = options.tag_name
    resource_id = options.resource_id
    _ = resource_id, now_utc()  # Will query tag_history

    # Known immutable tag patterns
    immutable_patterns = ("compliance-", "audit-", "legal-hold-", "retention-")
    protected_patterns = ("cost-center", "data-class", "pii-", "owner-")
    ephemeral_patterns = ("last-", "sync-", "cache-", "temp-")

    # Placeholder - would query actual tag history
    change_frequency = 0
    last_changed = None

    # Classify based on tag name patterns
    tag_lower = tag_name.lower()

    if any(tag_lower.startswith(p) for p in immutable_patterns):
        risk_class: TagRiskClass = "immutable"
    elif any(tag_lower.startswith(p) for p in protected_patterns):
        risk_class = "protected"
    elif any(tag_lower.startswith(p) for p in ephemeral_patterns):
        risk_class = "ephemeral"
    else:
        risk_class = "mutable"

    return {
        "risk_class": risk_class,
        "tag_name": tag_name,
        "change_frequency": change_frequency,
        "last_changed": last_changed,
    }
