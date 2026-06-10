"""Get acknowledgment for a notice.

Retrieves the employee acknowledgment record if exists.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["GetAcknowledgmentSpecs", "get_acknowledgment"]

# Evidence type for acknowledgment records
EVIDENCE_TYPE_ACKNOWLEDGMENT = "notice.acknowledgment"


class GetAcknowledgmentSpecs(BaseModel):
    """Specs for get acknowledgment phrase."""

    # inputs
    notice_id: UUID
    # outputs
    found: bool = False
    acknowledged_at: datetime | None = None
    acknowledgment_method: str | None = None  # portal_click, email_reply, signature, in_person
    employee_response: str | None = None


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO format datetime string to datetime object."""
    if value is None:
        return None
    # Handle both Z suffix and +00:00 timezone formats
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


@canon_phrase(
    Operable.from_structure(GetAcknowledgmentSpecs),
    inputs={"notice_id"},
    outputs={
        "notice_id",
        "found",
        "acknowledged_at",
        "acknowledgment_method",
        "employee_response",
    },
)
async def get_acknowledgment(
    options,
    ctx: RequestContext,
) -> dict:
    """Get acknowledgment for a notice.

    Queries Evidence records with evidence_type="notice.acknowledgment"
    and returns the acknowledgment data if found for the given notice_id.

    Args:
        options: Query options (notice_id) - typed frozen dataclass
        ctx: Request context with tenant_id

    Returns:
        dict with notice_id, found, acknowledged_at, acknowledgment_method, employee_response
    """
    notice_id: UUID = options.notice_id

    # Query evidence records for acknowledgments
    rows = await select(
        "evidences",
        where={
            "tenant_id": ctx.tenant_id,
            "evidence_type": EVIDENCE_TYPE_ACKNOWLEDGMENT,
        },
        order_by="collected_at DESC",
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Find records that reference this notice_id
    # The notice_id is stored in the data JSONB field
    for row in rows:
        data = row.get("data")
        if not data:
            continue

        # Match notice_id in data
        if str(data.get("notice_id")) == str(notice_id):
            try:
                return {
                    "notice_id": notice_id,
                    "found": True,
                    "acknowledged_at": _parse_datetime(data.get("acknowledged_at")),
                    "acknowledgment_method": data.get("acknowledgment_method"),
                    "employee_response": data.get("employee_response"),
                }
            except (KeyError, ValueError, TypeError):
                # Return found but with minimal data on parse error
                return {
                    "notice_id": notice_id,
                    "found": True,
                    "acknowledged_at": None,
                    "acknowledgment_method": None,
                    "employee_response": None,
                }

    return {
        "notice_id": notice_id,
        "found": False,
        "acknowledged_at": None,
        "acknowledgment_method": None,
        "employee_response": None,
    }
