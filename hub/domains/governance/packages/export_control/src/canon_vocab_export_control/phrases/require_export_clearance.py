"""Require export control clearance before cross-border data or goods transfer.

Composite gate that verifies all applicable export control regimes
(OFAC, BIS/EAR, ITAR) have cleared a transfer. This is a high-level
gate that checks for a clearance record rather than re-running
individual screening checks.

WARNING: Export control violations carry CRIMINAL penalties up to
$1M fine and 20 years imprisonment.

Regulatory: EAR (15 CFR 730-774), ITAR (22 CFR 120-130), OFAC (31 CFR 500-599)
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

__all__ = ["RequireExportClearanceSpecs", "require_export_clearance"]


class RequireExportClearanceSpecs(BaseModel):
    """Specs for require export clearance phrase."""

    # inputs
    transfer_id: UUID
    destination_country: str
    # outputs
    clearance_id: UUID | None = None
    cleared_at: datetime | None = None
    cleared_by: UUID | None = None
    clearance_type: str | None = None


require_export_clearance_operable = Operable.from_structure(RequireExportClearanceSpecs)


@canon_phrase(
    require_export_clearance_operable,
    inputs={"transfer_id", "destination_country"},
    outputs={
        "transfer_id",
        "destination_country",
        "clearance_id",
        "cleared_at",
        "cleared_by",
        "clearance_type",
    },
)
async def require_export_clearance(
    options: RequireExportClearanceSpecs,
    ctx: RequestContext,
) -> dict:
    """Require export control clearance before cross-border transfer.

    Composite gate that verifies an export clearance record exists for
    a transfer. The clearance record is produced after all applicable
    regime-specific checks (OFAC, BIS, ITAR) have passed. This gate
    verifies the clearance exists and is valid for the destination.

    WARNING: Export control violations carry CRIMINAL penalties.

    Regulatory:
        - EAR (15 CFR Parts 730-774): Bureau of Industry and Security
          export controls. License required for controlled items to
          most destinations. Civil penalties up to $330,000/violation.
        - ITAR (22 CFR Parts 120-130): State Department defense trade
          controls. Authorization required for USML items. Criminal
          penalties up to $1M and 20 years.
        - OFAC (31 CFR Parts 500-599): Treasury Department sanctions.
          Transactions with sanctioned parties/destinations prohibited.
          Criminal penalties up to $1M and 20 years.
        - EU Dual-Use Regulation (2021/821): For EU-destination transfers,
          dual-use items require authorization.

    Args:
        options: Options containing transfer_id and destination_country.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with clearance details if clearance exists and is valid.

    Raises:
        RequirementNotMetError: If no valid export clearance exists.
    """
    transfer_id = options.transfer_id
    destination_country = options.destination_country.upper().strip()

    # Query for export clearance record
    row = await select_one(
        "export_clearances",
        {
            "tenant_id": ctx.tenant_id,
            "transfer_id": transfer_id,
            "status": "cleared",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="export_clearance",
            reason=(
                f"No export clearance found for transfer {transfer_id} "
                f"to {destination_country}. All applicable export control "
                "regimes (OFAC, BIS/EAR, ITAR) must clear the transfer "
                "before it can proceed."
            ),
        )

    # Verify clearance matches the destination
    cleared_destination = (row.get("destination_country") or "").upper().strip()
    if cleared_destination and cleared_destination != destination_country:
        raise RequirementNotMetError(
            requirement="export_clearance",
            reason=(
                f"Export clearance for transfer {transfer_id} was issued "
                f"for destination {cleared_destination}, not "
                f"{destination_country}. Clearance must match destination."
            ),
        )

    return {
        "transfer_id": transfer_id,
        "destination_country": destination_country,
        "clearance_id": row["id"],
        "cleared_at": row.get("cleared_at"),
        "cleared_by": row.get("cleared_by"),
        "clearance_type": row.get("clearance_type"),
    }


# Export auto-generated types from the Phrase object
RequireExportClearanceOptions = require_export_clearance.options_type
RequireExportClearanceResult = require_export_clearance.result_type
