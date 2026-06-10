"""Chain entry types for evidence chains.

Evidence chains provide tamper-evident linkage between evidence records,
enabling verification that the audit trail has not been modified.
"""

from __future__ import annotations

from kron.types import Enum

__all__ = ("ChainEventType", "CustodyChainStatus")


class CustodyChainStatus(Enum):
    """Chain of custody verification status.

    Regulatory context:
        - FRE 901 (Authentication of evidence)
        - ISO 27037 (Digital evidence handling)
        - FRCP Rule 37(e) (ESI preservation duty)
    """

    # Chain is complete with all required entries
    COMPLETE = "complete"

    # Chain exists but is missing required entries
    INCOMPLETE = "incomplete"

    # Chain integrity verification failed (hash mismatch)
    BROKEN = "broken"

    # No chain entries exist yet
    NOT_STARTED = "not_started"


class ChainEventType(Enum):
    """Types of events recorded in the evidence chain.

    Each event type represents a discrete action in the evidence lifecycle
    that must be recorded for audit purposes.
    """

    # Genesis event - first evidence in a chain
    EVIDENCE_COLLECTED = "evidence_collected"

    # Evidence linked to existing chain
    EVIDENCE_LINKED = "evidence_linked"

    # Evidence superseded by correction
    EVIDENCE_SUPERSEDED = "evidence_superseded"

    # CEP created for evidence
    CEP_CREATED = "cep_created"

    # CEP sealed and ready for binding
    CEP_SEALED = "cep_sealed"

    # Evidence transferred to new custodian
    CUSTODY_TRANSFERRED = "custody_transferred"

    # Evidence accessed for review
    EVIDENCE_ACCESSED = "evidence_accessed"

    # Evidence verified (integrity check)
    EVIDENCE_VERIFIED = "evidence_verified"
