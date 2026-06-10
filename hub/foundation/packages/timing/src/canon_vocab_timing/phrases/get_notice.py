"""Get notice record by ID.

Retrieves notice evidence with optional acknowledgment data.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["GetNoticeSpecs", "NoticeType", "get_notice"]


class NoticeType(str, Enum):
    """Types of notices."""

    PRE_ADVERSE_ACTION = "pre_adverse_action"
    ADVERSE_ACTION = "adverse_action"
    PIP_SPECIFICATION = "pip_specification"
    POLICY_UPDATE = "policy_update"
    GENERIC = "generic"


# Evidence type prefixes for notice records
EVIDENCE_TYPE_NOTICE_PREFIX = "notice."
EVIDENCE_TYPE_ACKNOWLEDGMENT = "notice.acknowledgment"


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse ISO format datetime string to datetime object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    # Handle both Z suffix and +00:00 timezone formats
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


class AcknowledgmentDataDict(BaseModel):
    """Acknowledgment information."""

    acknowledged_at: datetime
    acknowledgment_method: str
    acknowledgment_evidence_id: UUID
    employee_response: str | None = None


class GetNoticeSpecs(BaseModel):
    """Specs for get notice phrase."""

    # inputs
    notice_id: UUID
    include_acknowledgment: bool = False
    # outputs
    found: bool = False
    notice_type: NoticeType | None = None
    evidence_id: UUID | None = None
    subject_id: UUID | None = None
    data: dict[str, Any] | None = None
    acknowledgment: dict[str, Any] | None = None  # AcknowledgmentDataDict as dict
    sent_at: datetime | None = None
    reason: str | None = None


def _extract_notice_type(evidence_type: str) -> NoticeType | None:
    """Extract NoticeType from evidence_type string.

    Evidence types are formatted as: notice.{type} (e.g., notice.pre_adverse_action)
    """
    if not evidence_type.startswith(EVIDENCE_TYPE_NOTICE_PREFIX):
        return None

    type_suffix = evidence_type[len(EVIDENCE_TYPE_NOTICE_PREFIX) :]

    # Skip acknowledgment evidence type
    if type_suffix == "acknowledgment":
        return None

    try:
        return NoticeType(type_suffix)
    except ValueError:
        # Unknown notice type, return GENERIC
        return NoticeType.GENERIC


def _row_to_acknowledgment_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert acknowledgment evidence row to dict."""
    data = row.get("data") or {}

    acknowledged_at = _parse_datetime(data.get("acknowledged_at") or row.get("collected_at"))
    if acknowledged_at is None:
        # Fallback to evidence created_at if available
        acknowledged_at = _parse_datetime(row.get("created_at"))
    if acknowledged_at is None:
        raise ValueError("Acknowledgment evidence missing timestamp")

    return {
        "acknowledged_at": acknowledged_at,
        "acknowledgment_method": data.get("method", "unknown"),
        "acknowledgment_evidence_id": row["id"],
        "employee_response": data.get("employee_response"),
    }


async def _fetch_acknowledgment(
    notice_id: UUID,
    ctx: RequestContext,
) -> dict[str, Any] | None:
    """Fetch acknowledgment evidence for a notice.

    Acknowledgment evidence references the notice via data.notice_id field.
    """
    # Query acknowledgment evidence records
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

    # Find acknowledgment that references this notice
    for row in rows:
        data = row.get("data")
        if not data:
            continue

        # Match notice_id in data
        if str(data.get("notice_id")) == str(notice_id):
            try:
                return _row_to_acknowledgment_dict(row)
            except (KeyError, ValueError, TypeError):
                # Invalid acknowledgment data, continue searching
                continue

    return None


@canon_phrase(
    Operable.from_structure(GetNoticeSpecs),
    inputs={"notice_id", "include_acknowledgment"},
    outputs={
        "notice_id",
        "found",
        "notice_type",
        "evidence_id",
        "subject_id",
        "data",
        "acknowledgment",
        "sent_at",
        "reason",
    },
)
async def get_notice(
    options,
    ctx: RequestContext,
) -> dict:
    """Get notice by ID with optional acknowledgment.

    Queries Evidence records for the notice and optionally its acknowledgment.
    Notice records are stored in the evidences table with evidence_type
    prefixed by "notice." (e.g., "notice.pre_adverse_action").

    Args:
        options: Query options (notice_id, include_acknowledgment) - typed frozen dataclass
        ctx: Request context with tenant_id

    Returns:
        dict with notice_id, found, notice_type, evidence_id, subject_id,
        data, acknowledgment, sent_at, reason
    """
    notice_id: UUID = options.notice_id
    include_acknowledgment: bool = options.include_acknowledgment

    # Query notice evidence by ID
    row = await select_one(
        "evidences",
        where={
            "id": notice_id,
            "tenant_id": ctx.tenant_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "notice_id": notice_id,
            "found": False,
            "notice_type": None,
            "evidence_id": None,
            "subject_id": None,
            "data": None,
            "acknowledgment": None,
            "sent_at": None,
            "reason": f"Notice not found: {notice_id}",
        }

    evidence_type = row.get("evidence_type", "")

    # Validate this is a notice evidence (not some other type)
    if not evidence_type.startswith(EVIDENCE_TYPE_NOTICE_PREFIX):
        return {
            "notice_id": notice_id,
            "found": False,
            "notice_type": None,
            "evidence_id": None,
            "subject_id": None,
            "data": None,
            "acknowledgment": None,
            "sent_at": None,
            "reason": f"Evidence {notice_id} is not a notice (type: {evidence_type})",
        }

    notice_type = _extract_notice_type(evidence_type)
    data = row.get("data") or {}

    # Extract sent_at from data or collected_at
    sent_at = _parse_datetime(data.get("sent_at") or row.get("collected_at"))

    # Build base result
    result: dict[str, Any] = {
        "notice_id": notice_id,
        "found": True,
        "notice_type": notice_type,
        "evidence_id": row["id"],
        "subject_id": row.get("subject_id"),
        "data": data,
        "acknowledgment": None,
        "sent_at": sent_at,
        "reason": None,
    }

    # Fetch acknowledgment if requested
    if include_acknowledgment:
        acknowledgment = await _fetch_acknowledgment(notice_id, ctx)
        result["acknowledgment"] = acknowledgment

    return result
