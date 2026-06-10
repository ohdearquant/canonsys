"""Require fraud screening pass phrase.

Requires passing fraud screening for financial transactions.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import FraudScreeningResult

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireFraudScreeningPassSpecs", "require_fraud_screening_pass"]


class RequireFraudScreeningPassSpecs(BaseModel):
    """Specs for require fraud screening pass phrase.

    Regulatory:
        - BSA/AML (Bank Secrecy Act)
        - PCI DSS v4.0 Req. 11 (Fraud monitoring)
        - FFIEC (Fraud detection)
    """

    # inputs
    transaction_id: UUID
    max_score: float = 0.7
    # outputs
    satisfied: bool
    screening_id: UUID | None = None
    result: FraudScreeningResult | None = None
    score: float | None = None
    screened_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireFraudScreeningPassSpecs),
    inputs={"transaction_id", "max_score"},
    outputs={
        "satisfied",
        "transaction_id",
        "screening_id",
        "result",
        "score",
        "screened_at",
        "reason",
    },
)
async def require_fraud_screening_pass(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Require passing fraud screening for financial transactions.

    Args:
        options: Requirement options (transaction_id, max_score)
        ctx: Request context

    Returns:
        dict with satisfaction status and screening details

    Raises:
        RequirementNotMetError: If screening not found, failed, or score exceeds threshold.
    """
    transaction_id = options.get("transaction_id")
    max_score = options.get("max_score", 0.7)

    query = """
        SELECT screening_id, result, score, screened_at
        FROM fraud_screenings
        WHERE transaction_id = $1 AND tenant_id = $2
        ORDER BY screened_at DESC
        LIMIT 1
    """
    rows = await fetch(
        query,
        transaction_id,
        ctx.tenant_id,
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,  # Already filtered in query
    )

    if not rows:
        raise RequirementNotMetError(
            requirement="fraud_screening_pass",
            reason=f"Fraud screening required for transaction {transaction_id}",
        )

    row = rows[0]
    result = FraudScreeningResult(row["result"])
    score = row["score"]

    if result == FraudScreeningResult.FAIL:
        raise RequirementNotMetError(
            requirement="fraud_screening_pass",
            reason="Fraud screening failed",
        )

    if result == FraudScreeningResult.PENDING:
        raise RequirementNotMetError(
            requirement="fraud_screening_pass",
            reason="Fraud screening pending",
        )

    if score is not None and score > max_score:
        raise RequirementNotMetError(
            requirement="fraud_screening_pass",
            reason=f"Fraud score {score:.2f} exceeds threshold {max_score}",
        )

    return {
        "satisfied": True,
        "transaction_id": transaction_id,
        "screening_id": row["screening_id"],
        "result": result,
        "score": score,
        "screened_at": row["screened_at"],
        "reason": None,
    }
