"""ChainEntry entity - hash-linked audit trail."""

from __future__ import annotations

from uuid import UUID

from ..entity import Entity, register_entity
from ..shared import OptActorAware, OptSubjectAware, TenantAware

__all__ = (
    "ChainEntry",
    "ChainEntryContent",
)


class ChainEntryContent(TenantAware, OptSubjectAware, OptActorAware):
    """Content for hash-linked chain entries.

    Forms tamper-evident audit trail. Each entry references the previous
    via previous_hash, creating a verifiable chain of events.

    Resource linking:
        References entities via resource_type + resource_id.
        Example: resource_type="evidence", resource_id=evidence.id,
        payload_hash=evidence.content_hash.
    """

    event_type: str
    """Event classification (e.g., consent_granted, decision_made)."""

    resource_type: str | None = None
    """Type of linked resource (evidence, decision, application)."""

    resource_id: UUID | None = None
    """ID of linked resource."""

    # Chain integrity
    payload_hash: str
    """SHA256 of payload content."""

    previous_hash: str | None = None
    """Hash of previous entry. None = genesis entry."""

    chain_hash: str
    """Composite hash: SHA256(payload_hash + previous_hash)."""

    sequence: int = 0
    """Monotonic sequence number within chain."""

    # Optional inline payload
    payload: dict | None = None
    """Embedded payload data (when resource linking not used)."""


@register_entity("chain_entries", immutable=True)
class ChainEntry(Entity):
    """Immutable chain entry. Insert-only for tamper-evident audit trail."""

    content: ChainEntryContent
