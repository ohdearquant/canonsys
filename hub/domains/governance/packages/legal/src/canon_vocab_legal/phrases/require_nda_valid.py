"""Require a valid NDA before information sharing.

Raises NDARequiredError if no valid NDA exists.

Regulatory:
    - Trade secret law (DTSA)
    - M&A confidentiality requirements
    - Due diligence best practices
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import NDARequiredError
from .verify_nda_status import verify_nda_status

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireNDAValidSpecs", "require_nda_valid"]


class RequireNDAValidSpecs(BaseModel):
    """Specs for require NDA valid phrase."""

    # inputs
    party_id: UUID
    counterparty_id: UUID | None = None
    # outputs
    satisfied: bool | None = None
    nda_id: UUID | None = None
    expiration_date: datetime | None = None
    reason: str | None = None


require_nda_valid_operable = Operable.from_structure(RequireNDAValidSpecs)


@canon_phrase(
    require_nda_valid_operable,
    inputs={"party_id", "counterparty_id"},
    outputs={
        "satisfied",
        "party_id",
        "counterparty_id",
        "nda_id",
        "expiration_date",
        "reason",
    },
)
async def require_nda_valid(
    options: RequireNDAValidSpecs,
    ctx: RequestContext,
) -> dict:
    """Require a valid NDA before information sharing.

    Args:
        options: Options containing party_id and optional counterparty_id
        ctx: Request context (tenant, actor)

    Returns:
        dict with satisfaction status if NDA is valid.

    Raises:
        NDARequiredError: If no valid NDA exists.
    """
    party_id: UUID = options.party_id
    counterparty_id: UUID | None = options.counterparty_id

    verify_result = await verify_nda_status(
        {"party_id": party_id, "counterparty_id": counterparty_id}, ctx
    )

    if not verify_result["verified"]:
        raise NDARequiredError(
            party_id=party_id,
            counterparty_id=counterparty_id,
            status=verify_result["status"],
            reason=verify_result["reason"] or "Valid NDA required",
        )

    return {
        "satisfied": True,
        "party_id": party_id,
        "counterparty_id": counterparty_id,
        "nda_id": verify_result["nda_id"],
        "expiration_date": verify_result["expiration_date"],
        "reason": None,
    }


# Export auto-generated types from the Phrase object
RequireNDAValidOptions = require_nda_valid.options_type
RequireNDAValidResult = require_nda_valid.result_type
