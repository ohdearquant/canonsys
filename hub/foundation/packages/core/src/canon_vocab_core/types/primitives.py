"""Primitive type definitions for generic compliance features.

Types for value checks, amount bands, evidence freshness, signer identity,
and value matching operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime, timedelta
    from uuid import UUID

__all__ = [
    "AmountBandConfig",
    "AmountBandResult",
    "FreshnessResult",
    "NumericValue",
    "SignerIdentityResult",
    "ValueWithinLimitResult",
    "ValuesMatchResult",
]

# Type alias for numeric values (Decimal preferred for money)
NumericValue = Decimal | float | int


@dataclass(frozen=True, slots=True)
class ValueWithinLimitResult:
    """Result of numeric threshold verification.

    Returned when value is within limit. If value exceeds limit,
    a ValueExceedsLimitError is raised instead.

    Regulatory:
        - BSA/AML (Bank Secrecy Act) - CTR thresholds
        - SOX Section 404 - Internal controls
        - COSO Framework - Authorization limits

    Attributes:
        value: The actual value that was checked.
        limit: The threshold limit.
        headroom: Amount remaining before limit (limit - value).
        description: Optional description of the threshold check.
    """

    value: Decimal
    limit: Decimal
    headroom: Decimal
    description: str | None = None


@dataclass(frozen=True, slots=True)
class AmountBandConfig:
    """Configuration for amount band thresholds.

    Compliance Context:
        - Finance surfaces (CS-009, CS-056-064): Amount classification determines approval chain
        - Anti-gaming: Amount band MUST be derived, never user-asserted

    Attributes:
        bands: Tuple of (band_name, threshold) tuples, sorted ascending by threshold.
               Amount >= threshold assigns that band.
    """

    bands: tuple[tuple[str, Decimal], ...]

    @classmethod
    def default(cls) -> AmountBandConfig:
        """Default band configuration matching Finance surfaces."""
        return cls(
            bands=(
                ("STANDARD", Decimal(0)),
                ("ELEVATED", Decimal(10000)),
                ("HIGH", Decimal(50000)),
                ("CRITICAL", Decimal(250000)),
            )
        )


@dataclass(frozen=True, slots=True)
class AmountBandResult:
    """Result of amount band derivation.

    Attributes:
        band: The classified band name (e.g., "HIGH").
        amount: The input amount that was classified.
        threshold: The threshold that triggered this band.
        next_band_at: Amount needed to reach next band (None if at highest).
        config_version: Hash of the band config used (for audit).
    """

    band: str
    amount: Decimal
    threshold: Decimal
    next_band_at: Decimal | None
    config_version: str


@dataclass(frozen=True, slots=True)
class FreshnessResult:
    """Result of evidence freshness verification.

    Regulatory context:
        - PCI DSS 11.3: Quarterly vulnerability scans
        - SOC 2 CC7.1: Timely response to security events
        - ISO 27001 A.12.6: Technical vulnerability management
    """

    evidence_id: UUID
    """Evidence ID that was checked."""

    fresh: bool
    """Whether evidence is within acceptable age limit."""

    evidence_age: timedelta
    """Age of the evidence (now - collected_at)."""

    max_age: timedelta
    """Maximum acceptable age threshold."""

    collected_at: datetime | None = None
    """When the evidence was collected (None if not found)."""

    expires_at: datetime | None = None
    """When the evidence expires (collected_at + max_age)."""

    found: bool = True
    """Whether the evidence was found."""

    reason: str | None = None
    """Human-readable explanation (for failures)."""


@dataclass(frozen=True, slots=True)
class SignerIdentityResult:
    """Result of signer identity verification.

    Returns verification status without raising exceptions.
    Caller decides how to handle verification failures.

    Regulatory citations:
        - SOX Section 302: CEO/CFO must certify financial reports
        - EU AI Act Art. 17: Human oversight requires accountability
        - FCRA Section 1681m: Adverse action requires authorized signoff
    """

    verified: bool
    """Whether the expected role signed the evidence."""

    evidence_id: UUID
    """Evidence artifact that was checked."""

    signer_id: UUID | None = None
    """ID of the signer (if found)."""

    signer_role: str | None = None
    """Role of the signer found (may differ from expected)."""

    expected_role: str | None = None
    """Role that was expected."""

    signed_at: datetime | None = None
    """When the attestation was recorded."""

    reason: str | None = None
    """Human-readable explanation of result."""


@dataclass(frozen=True, slots=True)
class ValuesMatchResult:
    """Result of values match verification.

    Regulatory Citations:
        - FCRA: Pre-adverse action notices must contain accurate information
          matching the consumer report and employment records.
        - GDPR Art. 5(1)(d): Personal data shall be accurate and kept up to date.
        - SOX Section 404: Internal controls must ensure data integrity
          and consistency across financial systems.

    Attributes:
        matched: True if value_a equals value_b.
        value_a: First value that was compared.
        value_b: Second value that was compared.
        field_name_a: Name/description of first field.
        field_name_b: Name/description of second field.
        checked_at: Timestamp of the verification.
        evidence_id: ID of evidence record (if recorded).
        reason: Explanation if values don't match.
    """

    matched: bool
    value_a: Any
    value_b: Any
    field_name_a: str
    field_name_b: str
    checked_at: datetime
    evidence_id: UUID | None = None
    reason: str | None = None
