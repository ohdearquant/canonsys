"""Assess control coverage for a vulnerability.

Calculates coverage percentage and strength band based on
controls documented against a specific vulnerability.

Regulatory Context:
    - SOX Section 404 (Internal controls assessment)
    - SOC 2 CC4.1 (Control monitoring)
    - ISO 27001 A.18.2.1 (Compliance review)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import ControlStrength

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["AssessControlCoverageSpecs", "assess_control_coverage"]


def _derive_strength(coverage_pct: int) -> ControlStrength:
    """Derive strength band from coverage percentage.

    Thresholds:
        - >= 80%: strong
        - >= 50%: moderate
        - < 50%: weak
    """
    if coverage_pct >= 80:
        return "strong"
    elif coverage_pct >= 50:
        return "moderate"
    return "weak"


class AssessControlCoverageSpecs(BaseModel):
    """Specs for assess control coverage phrase."""

    # inputs
    entity_id: UUID
    vulnerability_id: str
    controls_doc_id: UUID
    # outputs
    coverage_pct: int
    strength: ControlStrength
    gaps: tuple[str, ...]
    control_count: int
    gap_count: int


@canon_phrase(
    Operable.from_structure(AssessControlCoverageSpecs),
    inputs={"entity_id", "vulnerability_id", "controls_doc_id"},
    outputs={"coverage_pct", "strength", "gaps", "control_count", "gap_count"},
)
async def assess_control_coverage(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Assess control coverage for a vulnerability.

    Evaluates documented controls against a vulnerability to determine
    coverage percentage and identify gaps. Coverage is calculated as
    the ratio of mitigated attack vectors to total attack vectors.

    Args:
        options: Assessment options (entity_id, vulnerability_id, controls_doc_id)
        ctx: Request context (tenant, actor)

    Returns:
        dict with coverage_pct, strength, gaps, control_count, gap_count

    Regulatory:
        - SOX Section 404: Requires assessment of internal control effectiveness
        - SOC 2 CC4.1: COSO principle on control monitoring
        - ISO 27001 A.18.2.1: Independent review of information security
    """
    entity_id = options.get("entity_id")
    vulnerability_id = options.get("vulnerability_id")
    controls_doc_id = options.get("controls_doc_id")

    # Query controls documented for this vulnerability
    # In production: join controls_mappings with vulnerability_vectors
    query = """
        SELECT
            cm.control_id,
            cm.control_name,
            vv.vector_name,
            cm.mitigates_vector
        FROM controls_mappings cm
        CROSS JOIN vulnerability_vectors vv
        WHERE cm.controls_doc_id = $1
          AND vv.vulnerability_id = $2
          AND cm.entity_id = $3
    """
    rows = await fetch(
        query,
        controls_doc_id,
        vulnerability_id,
        entity_id,
        conn=ctx.conn,
    )

    if not rows:
        # No controls documented - complete gap
        return {
            "coverage_pct": 0,
            "strength": "weak",
            "gaps": ("No controls documented for vulnerability",),
            "control_count": 0,
            "gap_count": 1,
        }

    # Calculate coverage
    vectors: set[str] = set()
    mitigated: set[str] = set()
    controls: set[str] = set()
    gaps: list[str] = []

    for row in rows:
        vectors.add(row["vector_name"])
        controls.add(row["control_id"])
        if row["mitigates_vector"]:
            mitigated.add(row["vector_name"])

    # Identify gaps
    unmitigated = vectors - mitigated
    for vector in unmitigated:
        gaps.append(f"Unmitigated vector: {vector}")

    coverage_pct = int((len(mitigated) / len(vectors)) * 100) if vectors else 0
    strength = _derive_strength(coverage_pct)

    return {
        "coverage_pct": coverage_pct,
        "strength": strength,
        "gaps": tuple(gaps),
        "control_count": len(controls),
        "gap_count": len(gaps),
    }
