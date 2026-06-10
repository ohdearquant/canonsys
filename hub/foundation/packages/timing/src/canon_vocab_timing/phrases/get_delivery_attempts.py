"""Get delivery attempts for a notice.

Tracks all delivery attempts (email, SMS, postal) for compliance.
FCRA and other regulations require proof of delivery for notices.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "DeliveryStatus",
    "GetDeliveryAttemptsSpecs",
    "get_delivery_attempts",
]

# Evidence type for delivery attempt records
EVIDENCE_TYPE_DELIVERY = "notice.delivery"


class DeliveryStatus(str, Enum):
    """Delivery attempt status."""

    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


class DeliveryAttemptDict(BaseModel):
    """Individual delivery attempt."""

    attempted_at: datetime
    method: str  # email, sms, postal
    address: str
    status: DeliveryStatus
    error_message: str | None = None
    provider_response: dict[str, Any] | None = None


class GetDeliveryAttemptsSpecs(BaseModel):
    """Specs for get delivery attempts phrase."""

    # inputs
    notice_id: UUID
    # outputs
    attempts: list[dict[str, Any]] = []  # List of DeliveryAttemptDict as dicts
    latest_status: DeliveryStatus | None = None
    delivered: bool = False


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO format datetime string to datetime object."""
    if value is None:
        return None
    # Handle both Z suffix and +00:00 timezone formats
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _parse_status(value: str | None) -> DeliveryStatus:
    """Parse delivery status string to enum."""
    if value is None:
        return DeliveryStatus.FAILED
    try:
        return DeliveryStatus(value.lower())
    except ValueError:
        return DeliveryStatus.FAILED


def _row_to_attempt_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Convert evidence data dict to delivery attempt dict."""
    return {
        "attempted_at": _parse_datetime(data["attempted_at"]),
        "method": str(data.get("method", "unknown")),
        "address": str(data.get("address", "")),
        "status": _parse_status(data.get("status")),
        "error_message": data.get("error_message"),
        "provider_response": data.get("provider_response"),
    }


@canon_phrase(
    Operable.from_structure(GetDeliveryAttemptsSpecs),
    inputs={"notice_id"},
    outputs={"notice_id", "attempts", "latest_status", "delivered"},
)
async def get_delivery_attempts(
    options,
    ctx: RequestContext,
) -> dict:
    """Get all delivery attempts for a notice.

    Queries Evidence records with evidence_type="notice.delivery"
    and returns all attempts for the given notice_id, sorted by
    attempted_at timestamp (most recent first).

    Args:
        options: Query options (notice_id) - typed frozen dataclass
        ctx: Request context with tenant_id

    Returns:
        dict with notice_id, attempts, latest_status, delivered
    """
    notice_id: UUID = options.notice_id

    # Query evidence records for delivery attempts
    rows = await select(
        "evidences",
        where={
            "tenant_id": ctx.tenant_id,
            "evidence_type": EVIDENCE_TYPE_DELIVERY,
        },
        order_by="collected_at DESC",
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Find records that reference this notice_id
    # The notice_id is stored in the data JSONB field
    attempts: list[dict[str, Any]] = []
    for row in rows:
        data = row.get("data")
        if not data:
            continue

        # Match notice_id in data
        if str(data.get("notice_id")) == str(notice_id):
            try:
                attempt = _row_to_attempt_dict(data)
                attempts.append(attempt)
            except (KeyError, ValueError, TypeError):
                # Skip malformed records
                continue

    # Sort by attempted_at (most recent first)
    attempts.sort(key=lambda a: a["attempted_at"] or datetime.min, reverse=True)

    # Determine latest_status and delivered flag
    latest_status: DeliveryStatus | None = None
    delivered = False

    if attempts:
        latest_status = attempts[0]["status"]
        delivered = any(a["status"] == DeliveryStatus.DELIVERED for a in attempts)

    return {
        "notice_id": notice_id,
        "attempts": attempts,
        "latest_status": latest_status,
        "delivered": delivered,
    }
