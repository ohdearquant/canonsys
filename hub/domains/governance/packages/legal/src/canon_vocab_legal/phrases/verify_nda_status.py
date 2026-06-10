"""Verify that an NDA is active between parties.

Returns verified=True if active NDA exists.

Regulatory:
    - Trade secret law (DTSA)
    - Contract law (NDA enforcement)
    - M&A due diligence requirements
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import NDAStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyNDAStatusSpecs", "verify_nda_status"]


class VerifyNDAStatusSpecs(BaseModel):
    """Specs for verify NDA status phrase."""

    # inputs
    party_id: UUID
    counterparty_id: UUID | None = None
    # outputs
    verified: bool | None = None
    status: NDAStatus | None = None
    nda_id: UUID | None = None
    effective_date: datetime | None = None
    expiration_date: datetime | None = None
    reason: str | None = None


verify_nda_status_operable = Operable.from_structure(VerifyNDAStatusSpecs)


@canon_phrase(
    verify_nda_status_operable,
    inputs={"party_id", "counterparty_id"},
    outputs={
        "verified",
        "party_id",
        "counterparty_id",
        "status",
        "nda_id",
        "effective_date",
        "expiration_date",
        "reason",
    },
)
async def verify_nda_status(
    options: VerifyNDAStatusSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that an NDA is active between parties.

    Args:
        options: Options containing party_id and optional counterparty_id
        ctx: Request context (tenant, actor)

    Returns:
        dict with verification status and NDA details.
    """
    party_id: UUID = options.party_id
    counterparty_id: UUID | None = options.counterparty_id

    # Build where clause - can't easily do optional counterparty with select_one
    # Need to use raw query for conditional WHERE
    if counterparty_id is not None:
        rows = await fetch(
            """
            SELECT nda_id, status, effective_date, expiration_date
            FROM nda_agreements
            WHERE party_id = $1
            AND counterparty_id = $2
            AND status = 'active'
            ORDER BY effective_date DESC
            LIMIT 1
            """,
            party_id,
            counterparty_id,
            conn=ctx.conn,
            tenant_scope=TenantScope.REQUIRED,
        )
    else:
        rows = await fetch(
            """
            SELECT nda_id, status, effective_date, expiration_date
            FROM nda_agreements
            WHERE party_id = $1
            AND status = 'active'
            ORDER BY effective_date DESC
            LIMIT 1
            """,
            party_id,
            conn=ctx.conn,
            tenant_scope=TenantScope.REQUIRED,
        )

    if not rows:
        return {
            "verified": False,
            "party_id": party_id,
            "counterparty_id": counterparty_id,
            "status": NDAStatus.NOT_FOUND,
            "nda_id": None,
            "effective_date": None,
            "expiration_date": None,
            "reason": "No active NDA found",
        }

    row = rows[0]
    exp_date = row.get("expiration_date")
    now = datetime.now(UTC)

    if exp_date and exp_date < now:
        return {
            "verified": False,
            "party_id": party_id,
            "counterparty_id": counterparty_id,
            "status": NDAStatus.EXPIRED,
            "nda_id": row.get("nda_id"),
            "effective_date": row.get("effective_date"),
            "expiration_date": exp_date,
            "reason": "NDA has expired",
        }

    return {
        "verified": True,
        "party_id": party_id,
        "counterparty_id": counterparty_id,
        "status": NDAStatus.ACTIVE,
        "nda_id": row.get("nda_id"),
        "effective_date": row.get("effective_date"),
        "expiration_date": exp_date,
        "reason": None,
    }


# Export auto-generated types from the Phrase object
VerifyNDAStatusOptions = verify_nda_status.options_type
VerifyNDAStatusResult = verify_nda_status.result_type
