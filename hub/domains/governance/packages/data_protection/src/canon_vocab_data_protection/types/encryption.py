"""Encryption types for data protection domain.

Defines encryption status and standards for transmission security.

Regulatory context:
    - HIPAA 164.312(e): Transmission security
    - PCI DSS v4.0 Req. 4: Protect cardholder data
    - GDPR Art. 32: Security of processing
"""

from __future__ import annotations

from enum import StrEnum


class EncryptionStatus(StrEnum):
    """Encryption status for data transmission channels."""

    ENCRYPTED = "encrypted"
    UNENCRYPTED = "unencrypted"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class EncryptionStandard(StrEnum):
    """Encryption standards for data transmission.

    Ordered by strength (weakest to strongest for comparison).
    """

    NONE = "none"
    TLS_1_2 = "tls_1_2"
    TLS_1_3 = "tls_1_3"
    AES_128 = "aes_128"
    AES_256 = "aes_256"

    @classmethod
    def strength_order(cls) -> list[EncryptionStandard]:
        """Return standards ordered by strength (weakest first)."""
        return [
            cls.NONE,
            cls.TLS_1_2,
            cls.TLS_1_3,
            cls.AES_128,
            cls.AES_256,
        ]

    def meets_minimum(self, minimum: EncryptionStandard) -> bool:
        """Check if this standard meets the minimum requirement."""
        order = self.strength_order()
        return order.index(self) >= order.index(minimum)
