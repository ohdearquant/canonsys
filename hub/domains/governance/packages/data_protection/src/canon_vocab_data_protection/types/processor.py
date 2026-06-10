"""Processor terms types for data protection domain.

Defines processor agreement status for data sharing with third parties.

Regulatory context:
    - GDPR Art. 28: Processor requirements
    - CCPA Section 1798.140(w): Service provider contracts
    - HIPAA 164.308(b): Business associate contracts
"""

from __future__ import annotations

from enum import StrEnum


class ProcessorTermsStatus(StrEnum):
    """Status of processor/DPA terms verification."""

    VERIFIED = "verified"
    PENDING = "pending"
    EXPIRED = "expired"
    REJECTED = "rejected"
    NOT_FOUND = "not_found"
