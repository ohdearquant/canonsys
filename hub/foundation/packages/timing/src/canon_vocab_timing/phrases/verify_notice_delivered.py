"""Verify notice delivery to recipient.

Generic notice verification for any compliance domain.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext


class NoticeDeliveryStatus(StrEnum):
    DELIVERED = "delivered"
    PENDING = "pending"
    FAILED = "failed"
    BOUNCED = "bounced"
    NOT_SENT = "not_sent"


class NoticeChannel(StrEnum):
    EMAIL = "email"
    POSTAL = "postal"
    IN_APP = "in_app"
    SMS = "sms"


__all__ = [
    "NoticeChannel",
    "NoticeDeliveryStatus",
    "VerifyNoticeDeliveredSpecs",
    "verify_notice_delivered",
]


class VerifyNoticeDeliveredSpecs(BaseModel):
    """Specs for verify notice delivered phrase."""

    # inputs
    recipient_id: UUID
    notice_type: str
    required_channel: NoticeChannel | None = None
    # outputs
    verified: bool = False
    notice_id: UUID | None = None
    status: NoticeDeliveryStatus = NoticeDeliveryStatus.NOT_SENT
    channel: NoticeChannel | None = None
    delivered_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyNoticeDeliveredSpecs),
    inputs={"recipient_id", "notice_type", "required_channel"},
    outputs={
        "verified",
        "notice_id",
        "recipient_id",
        "notice_type",
        "status",
        "channel",
        "delivered_at",
        "reason",
    },
)
async def verify_notice_delivered(
    options,
    ctx: RequestContext,
) -> dict:
    """Verify that a notice has been delivered to recipient.

    Generic notice verification for any compliance domain.
    Domain libraries compose this with specific notice types.

    Regulatory:
        - FCRA 1681m (Adverse action notice)
        - NYC LL144 SS 20-871 (AEDT candidate notice)
        - BIPA 740 ILCS 14/15(b) (Biometric notice)
        - GDPR Art. 13/14 (Privacy notice)

    Args:
        options: Verification options (recipient_id, notice_type, required_channel)
        ctx: Request context

    Returns:
        dict with verified, notice_id, recipient_id, notice_type, status,
        channel, delivered_at, reason
    """
    recipient_id: UUID = options.recipient_id
    notice_type: str = options.notice_type
    required_channel: NoticeChannel | None = options.required_channel

    query = """
        SELECT notice_id, status, channel, delivered_at
        FROM notice_deliveries
        WHERE recipient_id = $1 AND notice_type = $2
        ORDER BY delivered_at DESC NULLS LAST
        LIMIT 1
    """
    rows = await fetch(
        query,
        recipient_id,
        notice_type,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )
    row = rows[0] if rows else None

    if not row:
        return {
            "verified": False,
            "notice_id": UUID("00000000-0000-0000-0000-000000000000"),
            "recipient_id": recipient_id,
            "notice_type": notice_type,
            "status": NoticeDeliveryStatus.NOT_SENT,
            "channel": None,
            "delivered_at": None,
            "reason": "No notice found",
        }

    status = NoticeDeliveryStatus(row["status"])
    channel = NoticeChannel(row["channel"]) if row["channel"] else None

    # Check channel requirement if specified
    if required_channel and channel != required_channel:
        return {
            "verified": False,
            "notice_id": row["notice_id"],
            "recipient_id": recipient_id,
            "notice_type": notice_type,
            "status": status,
            "channel": channel,
            "delivered_at": row["delivered_at"],
            "reason": f"Required channel {required_channel.value}, got {channel.value if channel else 'none'}",
        }

    verified = status == NoticeDeliveryStatus.DELIVERED

    return {
        "verified": verified,
        "notice_id": row["notice_id"],
        "recipient_id": recipient_id,
        "notice_type": notice_type,
        "status": status,
        "channel": channel,
        "delivered_at": row["delivered_at"],
        "reason": None if verified else f"Notice status: {status.value}",
    }
