"""JIT Permit Token - single-use execution capability.

Per architecture/certificate.md:
    - Bound to certificate (one-to-one)
    - Single-use: consumed on redemption
    - Transaction-level binding (not user + time window)

This solves the JIT role problem: roles allow multiple actions,
PermitToken binds at transaction boundary.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from canon.entities.entity import ContentModel, Entity, register_entity
from canon.entities.shared import Person, Tenant, User
from kron.types import FK
from kron.utils import compute_hash, now_utc

from .deny import JITPermitDenyReason
from .enum import TokenStatus

__all__ = (
    "PermitToken",
    "PermitTokenContent",
)


class PermitTokenContent(ContentModel):
    """Content for permit tokens (single-use execution capability).

    Usage:
        # At certificate mint
        permit = PermitToken(content=PermitTokenContent(
            tenant_id=tenant.id,
            certificate_id=cert.id,
            subject_id=person.id,
            action="TERMINATE",
            expires_at=now + timedelta(minutes=5),
        ))

        # At execution time
        if permit.content.is_valid():
            permit.content.redeem(bp_instance_id="bp-123")
    """

    # Scope
    tenant_id: FK[Tenant]
    subject_id: FK[Person]  # Who the action targets
    actor_id: FK[User] | None = None  # Who will execute

    # Binding
    certificate_id: UUID  # FK to DecisionCertificate
    action: str  # What action is permitted: TERMINATE, PROMOTE, etc.

    # Token identity
    token_hash: str  # SHA-256 of canonical representation

    # Lifecycle
    status: TokenStatus = TokenStatus.ACTIVE
    issued_at: datetime = Field(default_factory=now_utc)
    expires_at: datetime  # Required, short TTL (5 min default)

    # Redemption
    redeemed_at: datetime | None = None
    redeemed_by_bp: str | None = None  # BP instance ID for idempotency

    @classmethod
    def compute_token_hash(
        cls,
        certificate_id: UUID,
        subject_id: UUID,
        action: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> str:
        """Compute deterministic hash for token integrity."""
        canonical = {
            "certificate_id": str(certificate_id),
            "subject_id": str(subject_id),
            "action": action,
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        return compute_hash(canonical)

    def is_valid(self, as_of: datetime | None = None) -> bool:
        """Check if permit can be redeemed."""
        if self.status != TokenStatus.ACTIVE:
            return False

        check_time = as_of or now_utc()
        return check_time < self.expires_at

    def can_redeem(
        self,
        subject_id: UUID | None = None,
        action: str | None = None,
    ) -> tuple[bool, JITPermitDenyReason | None]:
        """Check if permit can be redeemed with given params.

        Returns:
            (allowed, reason) - reason is None if allowed
        """
        if self.status == TokenStatus.USED:
            return False, JITPermitDenyReason.ALREADY_USED
        if self.status == TokenStatus.REVOKED:
            return False, JITPermitDenyReason.REVOKED

        now = now_utc()
        if now >= self.expires_at:
            return False, JITPermitDenyReason.EXPIRED

        if subject_id and str(subject_id) != str(self.subject_id):
            return False, JITPermitDenyReason.SUBJECT_MISMATCH

        if action and action != self.action:
            return False, JITPermitDenyReason.ACTION_MISMATCH

        return True, None

    def redeem(self, bp_instance_id: str) -> None:
        """Mark permit as consumed.

        Call touch() after for rehash.

        Args:
            bp_instance_id: Business process instance that consumed this
        """
        self.status = TokenStatus.USED
        self.redeemed_at = now_utc()
        self.redeemed_by_bp = bp_instance_id


@register_entity("permit_tokens")
class PermitToken(Entity):
    """Entity representing a JIT permit token."""

    content: PermitTokenContent
