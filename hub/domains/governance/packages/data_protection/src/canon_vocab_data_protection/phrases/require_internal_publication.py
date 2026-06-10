"""Require internal publication gate for restricted content.

Raises PublicationRestrictedError if content has publication restrictions.

Regulatory context:
    - SEC Regulation FD: Fair disclosure
    - ITAR 22 CFR 120-130: Export controls
    - Trade secret law (DTSA)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import PublicationRestrictedError
from ..types import PublicationRestriction

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireInternalPublicationSpecs", "require_internal_publication"]


class RequireInternalPublicationSpecs(BaseModel):
    """Specs for require internal publication phrase."""

    # inputs
    resource_id: UUID
    # outputs
    restriction: PublicationRestriction | None = None


require_internal_publication_operable = Operable.from_structure(RequireInternalPublicationSpecs)


@canon_phrase(
    require_internal_publication_operable,
    inputs={"resource_id"},
    outputs={"resource_id", "restriction"},
)
async def require_internal_publication(
    options: RequireInternalPublicationSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that restricted content is not published externally.

    Raises PublicationRestrictedError if content has publication restrictions.

    Args:
        options: Publication options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with resource_id, restriction

    Raises:
        PublicationRestrictedError: If publication is restricted.

    Regulatory:
        - SEC Regulation FD: Fair disclosure
        - ITAR 22 CFR 120-130: Export controls
        - Trade secret law (DTSA)
    """
    resource_id = options.resource_id

    row = await select_one(
        "publication_restrictions",
        where={
            "resource_id": resource_id,
            "status": "active",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.OPTIONAL,
    )

    if not row:
        return {
            "resource_id": resource_id,
            "restriction": PublicationRestriction.NONE,
        }

    restriction = PublicationRestriction(row["restriction_type"])

    if restriction == PublicationRestriction.NONE:
        return {
            "resource_id": resource_id,
            "restriction": restriction,
        }

    embargo_until = row.get("embargo_until")
    raise PublicationRestrictedError(
        resource_id=resource_id,
        restriction=restriction.value,
        restriction_reason=row.get("restriction_reason"),
        embargo_until=embargo_until.isoformat() if embargo_until else None,
    )


# Export auto-generated types from the Phrase object
RequireInternalPublicationOptions = require_internal_publication.options_type
RequireInternalPublicationResult = require_internal_publication.result_type
