"""Charter-related type definitions.

Types for charter activation, ratification, and resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = ["Signatory"]


@dataclass(frozen=True, slots=True)
class Signatory:
    """Charter signatory record.

    Represents an individual who has signed a charter during ratification.

    Attributes:
        user_id: UUID of the signing user.
        role: Role of the signer (e.g., "CEO", "GC", "CHRO").
        signed_at: Timestamp when the signature was recorded.
        signature_hash: Optional cryptographic hash of the signature.
    """

    user_id: UUID
    role: str
    signed_at: datetime
    signature_hash: str | None = None
