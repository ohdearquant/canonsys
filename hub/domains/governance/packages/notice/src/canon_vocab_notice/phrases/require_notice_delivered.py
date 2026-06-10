"""Require that notice delivery has been confirmed before proceeding.

Ensures that a compliance notice has been successfully delivered to the
recipient before dependent operations (such as adverse action or
waiting period commencement) can proceed.

Regulatory: FCRA Section 1681m, WARN Act, GDPR Art. 12-14
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireNoticeDeliveredSpecs", "require_notice_delivered"]


class RequireNoticeDeliveredSpecs(BaseModel):
    """Specs for require notice delivered phrase."""

    # inputs
    notice_id: UUID
    # outputs
    satisfied: bool = False
    delivered_at: datetime | None = None
    delivery_method: str | None = None
    reason: str | None = None


require_notice_delivered_operable = Operable.from_structure(RequireNoticeDeliveredSpecs)


@canon_phrase(
    require_notice_delivered_operable,
    inputs={"notice_id"},
    outputs={
        "satisfied",
        "notice_id",
        "delivered_at",
        "delivery_method",
        "reason",
    },
)
async def require_notice_delivered(
    options: RequireNoticeDeliveredSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that notice delivery has been confirmed.

    Gate for compliance workflows that depend on notice receipt.
    Checks that a notice evidence record exists and has a confirmed
    delivery status. Notices that are pending, bounced, or failed
    do not satisfy this gate.

    Regulatory:
        - FCRA Section 1681m: Pre-adverse and adverse action notices
          must be delivered before the employer can take adverse action.
          Proof of delivery is required for compliance defense.
        - WARN Act (29 U.S.C. 2102): 60-day advance written notice
          required for plant closings and mass layoffs. Delivery must
          be confirmed for the notice period to commence.
        - GDPR Art. 12-14: Transparent information, communication, and
          modalities. Data subjects must actually receive notices about
          processing of their personal data.
        - State employment laws: Various states require confirmed
          delivery of notices (e.g., CA WARN Act, NYC LL144).

    Args:
        options: Options containing notice_id to check.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with delivery confirmation details.

    Raises:
        RequirementNotMetError: If notice delivery is not confirmed.
    """
    notice_id = options.notice_id

    # Query for the notice evidence record
    row = await select_one(
        "evidences",
        {
            "tenant_id": ctx.tenant_id,
            "id": notice_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="notice_delivered",
            reason=f"Notice {notice_id} not found",
        )

    # Extract delivery status from the evidence data
    data = row.get("data") or {}
    delivery_status = data.get("delivery_status")
    delivered_at = data.get("delivered_at")
    delivery_method = data.get("delivery_method")

    # Only "delivered" status satisfies this gate
    # "sent" is not sufficient - we need confirmed delivery
    if delivery_status != "delivered":
        status_msg = delivery_status or "unknown"
        raise RequirementNotMetError(
            requirement="notice_delivered",
            reason=(
                f"Notice {notice_id} delivery not confirmed "
                f"(current status: {status_msg}). "
                "Confirmed delivery required before proceeding."
            ),
            evidence_id=notice_id,
        )

    return {
        "satisfied": True,
        "notice_id": notice_id,
        "delivered_at": delivered_at,
        "delivery_method": delivery_method,
        "reason": "Notice delivery confirmed",
    }


# Export auto-generated types from the Phrase object
RequireNoticeDeliveredOptions = require_notice_delivered.options_type
RequireNoticeDeliveredResult = require_notice_delivered.result_type
