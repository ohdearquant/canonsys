"""Require encrypted transmission gate.

Raises EncryptionMissingError if channel lacks required encryption.

Regulatory context:
    - HIPAA 164.312(e): Transmission security
    - PCI DSS v4.0 Req. 4: Protect cardholder data
    - GDPR Art. 32: Security of processing
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.exceptions import EncryptionMissingError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import EncryptionStandard, EncryptionStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireEncryptedTransmissionSpecs", "require_encrypted_transmission"]


class RequireEncryptedTransmissionSpecs(BaseModel):
    """Specs for require encrypted transmission phrase."""

    # inputs
    resource_id: UUID
    channel_id: UUID
    min_standard: EncryptionStandard = EncryptionStandard.TLS_1_2
    # outputs
    encryption_status: EncryptionStatus | None = None
    encryption_standard: EncryptionStandard | None = None


require_encrypted_transmission_operable = Operable.from_structure(RequireEncryptedTransmissionSpecs)


@canon_phrase(
    require_encrypted_transmission_operable,
    inputs={"resource_id", "channel_id", "min_standard"},
    outputs={"resource_id", "channel_id", "encryption_status", "encryption_standard"},
)
async def require_encrypted_transmission(
    options: RequireEncryptedTransmissionSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that data transmission uses adequate encryption.

    Raises EncryptionMissingError if channel lacks required encryption.

    Args:
        options: Transmission options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with resource_id, channel_id, encryption_status, encryption_standard

    Raises:
        EncryptionMissingError: If channel lacks required encryption.

    Regulatory:
        - HIPAA 164.312(e): Transmission security
        - PCI DSS v4.0 Req. 4: Protect cardholder data
        - GDPR Art. 32: Security of processing
    """
    resource_id = options.resource_id
    channel_id = options.channel_id
    min_standard = options.min_standard

    row = await select_one(
        "transmission_channels",
        where={"channel_id": channel_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.OPTIONAL,
    )

    if not row:
        raise EncryptionMissingError(
            channel=str(channel_id),
            required_standard=min_standard.value,
            actual_standard=None,
            context={
                "resource_id": str(resource_id),
                "reason": "Channel encryption status unknown",
            },
        )

    status = EncryptionStatus(row["encryption_status"])
    standard = (
        EncryptionStandard(row["encryption_standard"]) if row.get("encryption_standard") else None
    )

    if status != EncryptionStatus.ENCRYPTED:
        raise EncryptionMissingError(
            channel=str(channel_id),
            required_standard=min_standard.value,
            actual_standard=standard.value if standard else None,
            context={
                "resource_id": str(resource_id),
                "encryption_status": status.value,
                "reason": f"Channel not encrypted: {status.value}",
            },
        )

    # Check minimum standard using the type's method
    if standard and not standard.meets_minimum(min_standard):
        raise EncryptionMissingError(
            channel=str(channel_id),
            required_standard=min_standard.value,
            actual_standard=standard.value,
            context={
                "resource_id": str(resource_id),
                "reason": f"Encryption standard {standard.value} below minimum {min_standard.value}",
            },
        )

    # At this point we have a valid standard
    return {
        "resource_id": resource_id,
        "channel_id": channel_id,
        "encryption_status": status,
        "encryption_standard": standard or min_standard,
    }


# Export auto-generated types from the Phrase object
RequireEncryptedTransmissionOptions = require_encrypted_transmission.options_type
RequireEncryptedTransmissionResult = require_encrypted_transmission.result_type
