"""Derive control equivalence score.

Evaluates how effectively a compensating control can substitute for
an original control.

Regulatory Context:
    - SOX Section 404 (Compensating controls for material weaknesses)
    - SOC 2 CC4.1 (Control monitoring and evaluation)
    - ISO 27001 A.18.2.1 (Compliance with security policies)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import ControlEquivalence

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveControlEquivalenceSpecs", "derive_control_equivalence_score"]


def _derive_equivalence(score: float) -> ControlEquivalence:
    """Derive equivalence category from numerical score.

    Thresholds:
        - >= 0.8: equivalent (acceptable substitute)
        - >= 0.5: partial (requires additional controls)
        - < 0.5: inadequate (not acceptable)
    """
    if score >= 0.8:
        return "equivalent"
    elif score >= 0.5:
        return "partial"
    return "inadequate"


class DeriveControlEquivalenceSpecs(BaseModel):
    """Specs for derive control equivalence score phrase."""

    # inputs
    original_control_id: UUID
    compensating_control_id: UUID
    # outputs
    equivalence: ControlEquivalence
    score: float
    mapping_doc_id: UUID | None = None
    rationale: str


@canon_phrase(
    Operable.from_structure(DeriveControlEquivalenceSpecs),
    inputs={"original_control_id", "compensating_control_id"},
    outputs={"equivalence", "score", "mapping_doc_id", "rationale"},
)
async def derive_control_equivalence_score(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Derive equivalence score between original and compensating control.

    Evaluates how effectively a compensating control can substitute for
    an original control that cannot be implemented. Scoring considers:
    - Coverage overlap (risk vectors addressed)
    - Detection capability parity
    - Response time equivalence
    - Automation level

    Args:
        options: Derivation options (original_control_id, compensating_control_id)
        ctx: Request context (tenant, actor)

    Returns:
        dict with equivalence, score, mapping_doc_id, rationale

    Regulatory:
        - SOX Section 404: Compensating controls must provide equivalent assurance
        - SOC 2 CC4.1: Monitoring must ensure control objectives are met
        - ISO 27001 A.18.2.1: Alternative controls must be justified
    """
    original_control_id = options.get("original_control_id")
    compensating_control_id = options.get("compensating_control_id")

    # Query for existing equivalence mapping
    mapping_row = await select_one(
        "control_equivalence_mappings",
        where={
            "original_control_id": original_control_id,
            "compensating_control_id": compensating_control_id,
            "tenant_id": ctx.tenant_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if mapping_row:
        # Use existing mapping
        score = float(mapping_row["equivalence_score"])
        return {
            "equivalence": _derive_equivalence(score),
            "score": score,
            "mapping_doc_id": mapping_row.get("mapping_doc_id"),
            "rationale": mapping_row.get("rationale", ""),
        }

    # No existing mapping - calculate from control attributes
    attr_query = """
        SELECT
            oc.risk_vectors AS original_vectors,
            oc.detection_capability AS original_detection,
            oc.automation_level AS original_automation,
            cc.risk_vectors AS comp_vectors,
            cc.detection_capability AS comp_detection,
            cc.automation_level AS comp_automation
        FROM controls oc, controls cc
        WHERE oc.control_id = $1
          AND cc.control_id = $2
    """
    attr_rows = await fetch(
        attr_query,
        original_control_id,
        compensating_control_id,
        conn=ctx.conn,
    )
    attr_row = attr_rows[0] if attr_rows else None

    if not attr_row:
        return {
            "equivalence": "inadequate",
            "score": 0.0,
            "mapping_doc_id": None,
            "rationale": "One or both controls not found in registry",
        }

    # Calculate component scores
    original_vectors = set(attr_row.get("original_vectors") or [])
    comp_vectors = set(attr_row.get("comp_vectors") or [])
    vector_coverage = (
        len(original_vectors & comp_vectors) / len(original_vectors) if original_vectors else 0.0
    )

    original_detection = attr_row.get("original_detection") or 1
    comp_detection = attr_row.get("comp_detection") or 0
    detection_score = min(comp_detection / max(original_detection, 1), 1.0)

    original_automation = attr_row.get("original_automation") or 1
    comp_automation = attr_row.get("comp_automation") or 0
    automation_score = min(comp_automation / max(original_automation, 1), 1.0)

    # Weighted average
    score = (vector_coverage * 0.5) + (detection_score * 0.3) + (automation_score * 0.2)
    score = round(score, 2)
    equivalence = _derive_equivalence(score)

    rationale_parts = [
        f"Vector coverage: {vector_coverage:.0%}",
        f"Detection parity: {detection_score:.0%}",
        f"Automation parity: {automation_score:.0%}",
    ]

    return {
        "equivalence": equivalence,
        "score": score,
        "mapping_doc_id": None,
        "rationale": "; ".join(rationale_parts),
    }
