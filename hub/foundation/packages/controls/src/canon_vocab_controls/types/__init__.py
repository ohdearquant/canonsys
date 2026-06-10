"""Control domain types.

Includes categorical classifications (type aliases) and result dataclasses
for control assessment operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID

__all__ = [
    # Enums (Literal type aliases)
    "ControlEquivalence",
    "ControlStrength",
    "LoggingCoverage",
    # Results
    "ControlCoverageResult",
    "ControlEquivalenceResult",
    "ExploitabilityResult",
    "LoggingCoverageResult",
    "SanitizationResult",
    "ToolControlResult",
]

# -----------------------------------------------------------------------------
# Enum types (Literal type aliases)
# -----------------------------------------------------------------------------

ControlStrength = Literal["weak", "moderate", "strong"]
"""Control strength band based on coverage percentage.

Thresholds:
    - >= 80%: strong
    - >= 50%: moderate
    - < 50%: weak
"""

ControlEquivalence = Literal["equivalent", "partial", "inadequate"]
"""Equivalence rating between original and compensating control.

Thresholds:
    - >= 0.8: equivalent (acceptable substitute)
    - >= 0.5: partial (requires additional controls)
    - < 0.5: inadequate (not acceptable)
"""

LoggingCoverage = Literal["full_equivalent", "partial_equivalent", "minimal", "unknown"]
"""Categorical coverage rating for logging configuration.

Thresholds:
    - 100%: full_equivalent
    - >= 80%: partial_equivalent
    - >= 50%: minimal
    - < 50% or unknown: unknown
"""

# -----------------------------------------------------------------------------
# Result dataclasses
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ControlCoverageResult:
    """Result of control coverage assessment.

    Attributes:
        coverage_pct: Percentage of vulnerability surface covered (0-100)
        strength: Overall control strength band
        gaps: Identified coverage gaps
        control_count: Number of controls assessed
        gap_count: Number of gaps identified
    """

    coverage_pct: int
    strength: ControlStrength
    gaps: tuple[str, ...]
    control_count: int
    gap_count: int


@dataclass(frozen=True, slots=True)
class ControlEquivalenceResult:
    """Result of control equivalence scoring.

    Attributes:
        equivalence: Categorical equivalence rating
        score: Numerical equivalence score (0.0-1.0)
        mapping_doc_id: Document ID containing equivalence mapping (if exists)
        rationale: Explanation for the equivalence rating
    """

    equivalence: ControlEquivalence
    score: float
    mapping_doc_id: UUID | None
    rationale: str


@dataclass(frozen=True, slots=True)
class ExploitabilityResult:
    """Result of exploitability status check.

    Attributes:
        is_exploitable: Whether the CVE is known to be exploited
        cve_id: The CVE identifier checked
        in_kev: Whether the CVE is in CISA KEV catalog
        kev_added_date: Date added to KEV catalog (if present)
        exploit_maturity: Maturity level of known exploits
    """

    is_exploitable: bool
    cve_id: str
    in_kev: bool
    kev_added_date: date | None
    exploit_maturity: str


@dataclass(frozen=True, slots=True)
class LoggingCoverageResult:
    """Result of logging coverage assessment.

    Attributes:
        coverage: Categorical coverage rating
        logged_events: Count of required events being logged
        required_events: Total count of required events
        missing_events: Events not covered by logging configuration
    """

    coverage: LoggingCoverage
    logged_events: int
    required_events: int
    missing_events: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SanitizationResult:
    """Result of sanitization profile verification.

    Attributes:
        valid: Whether the profile is valid and covers all required types
        profile_id: ID of the sanitization profile
        sanitization_level: Level of sanitization (e.g., "clear", "purge", "destroy")
        covers_data_types: Data types covered by the profile
        missing_coverage: Required data types not covered by the profile
    """

    valid: bool
    profile_id: UUID
    sanitization_level: str
    covers_data_types: tuple[str, ...]
    missing_coverage: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ToolControlResult:
    """Result of tool control verification.

    Attributes:
        satisfied: Whether all required controls are present
        tool_id: ID of the tool being verified
        tool_category: Category of the tool (e.g., "aedt", "financial")
        required_controls: Controls required for this tool/category/bypass
        present_controls: Controls that are documented and active
        missing_controls: Controls that are required but not present
    """

    satisfied: bool
    tool_id: UUID
    tool_category: str
    required_controls: tuple[str, ...]
    present_controls: tuple[str, ...]
    missing_controls: tuple[str, ...]
