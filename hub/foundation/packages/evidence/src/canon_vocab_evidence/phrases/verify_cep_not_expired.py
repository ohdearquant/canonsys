"""Verify CEP is within validity period.

Complete vertical slice:
- Looks up CEP and its type
- Calculates expiration based on type-specific validity periods
- Returns validity status and expiration date

Regulatory: SPEC-001 - CEP types have validity periods (12-36 months)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from .create_cep import CEPType

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyCEPNotExpiredSpecs", "verify_cep_not_expired"]


# CEP type validity periods in months
CEP_VALIDITY_PERIODS: dict[str, int] = {
    CEPType.PERF_METRIC.value: 12,  # Performance data: 1 year
    CEPType.POLICY_LOG.value: 24,  # Policy/access logs: 2 years
    CEPType.CONDUCT_RECORD.value: 36,  # Conduct records: 3 years
    CEPType.INVESTIGATION_RULING.value: 36,  # Investigation findings: 3 years
    CEPType.PIP_FAIL.value: 24,  # PIP failures: 2 years
}

DEFAULT_VALIDITY_MONTHS = 24  # Default to 2 years


class VerifyCEPNotExpiredSpecs(BaseModel):
    """Specs for verify CEP not expired phrase."""

    # inputs
    cep_id: UUID
    # outputs
    valid: bool = False
    expires_at: datetime | None = None
    cep_type: str | None = None
    validity_period_months: int | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyCEPNotExpiredSpecs),
    inputs={"cep_id"},
    outputs={
        "valid",
        "cep_id",
        "expires_at",
        "cep_type",
        "validity_period_months",
        "reason",
    },
)
async def verify_cep_not_expired(
    options: VerifyCEPNotExpiredSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify a CEP is within its validity period.

    Different CEP types have different validity periods:
    - perf_metric: 12 months
    - policy_log: 24 months
    - conduct_record: 36 months
    - investigation_ruling: 36 months
    - pip_fail: 24 months

    Args:
        options: Options containing cep_id.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with validity status and expiration date.
    """
    cep_id = options.cep_id
    now = now_utc()

    # Fetch CEP
    row = await select_one(
        "certified_evidence_packets",
        where={"id": cep_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "valid": False,
            "cep_id": cep_id,
            "expires_at": None,
            "cep_type": None,
            "validity_period_months": None,
            "reason": "CEP not found",
        }

    # Check tenant isolation
    if row["tenant_id"] != ctx.tenant_id:
        return {
            "valid": False,
            "cep_id": cep_id,
            "expires_at": None,
            "cep_type": None,
            "validity_period_months": None,
            "reason": "CEP tenant mismatch",
        }

    # Check not superseded
    if row.get("superseded_by_id"):
        return {
            "valid": False,
            "cep_id": cep_id,
            "expires_at": None,
            "cep_type": row.get("cep_type"),
            "validity_period_months": None,
            "reason": "CEP has been superseded",
        }

    # Get CEP type and validity period
    cep_type = row.get("cep_type", "")
    validity_months = CEP_VALIDITY_PERIODS.get(cep_type, DEFAULT_VALIDITY_MONTHS)

    # Calculate expiration from sealed_at or created_at
    base_date = row.get("sealed_at") or row.get("created_at")
    if not base_date:
        return {
            "valid": False,
            "cep_id": cep_id,
            "expires_at": None,
            "cep_type": cep_type,
            "validity_period_months": validity_months,
            "reason": "CEP has no timestamp for expiration calculation",
        }

    # Calculate expiration (approximate months as 30 days)
    expires_at = base_date + timedelta(days=validity_months * 30)

    # Check if expired
    if now > expires_at:
        return {
            "valid": False,
            "cep_id": cep_id,
            "expires_at": expires_at,
            "cep_type": cep_type,
            "validity_period_months": validity_months,
            "reason": f"CEP expired on {expires_at.isoformat()}",
        }

    # CEP is valid
    return {
        "valid": True,
        "cep_id": cep_id,
        "expires_at": expires_at,
        "cep_type": cep_type,
        "validity_period_months": validity_months,
        "reason": None,
    }
