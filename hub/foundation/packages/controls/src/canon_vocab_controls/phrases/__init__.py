"""Controls domain phrases.

All control assessment operations in one place:
- Assessment: assess_control_coverage
- Checks: check_exploitability_status
- Derivation: derive_compensating_logging_coverage, derive_control_equivalence_score
- Verification: verify_required_controls_for_tool, verify_sanitization_profile
"""

from .assess_coverage import AssessControlCoverageSpecs, assess_control_coverage
from .check_exploitability import CheckExploitabilitySpecs, check_exploitability_status
from .derive_control_equivalence import (
    DeriveControlEquivalenceSpecs,
    derive_control_equivalence_score,
)
from .derive_logging_coverage import (
    DeriveLoggingCoverageSpecs,
    derive_compensating_logging_coverage,
)
from .verify_sanitization import VerifySanitizationSpecs, verify_sanitization_profile
from .verify_tool_controls import (
    VerifyToolControlsSpecs,
    verify_required_controls_for_tool,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "AssessControlCoverageSpecs",
    "CheckExploitabilitySpecs",
    "DeriveControlEquivalenceSpecs",
    "DeriveLoggingCoverageSpecs",
    "VerifySanitizationSpecs",
    "VerifyToolControlsSpecs",
    # Phrase functions - Assessment
    "assess_control_coverage",
    # Phrase functions - Checks
    "check_exploitability_status",
    # Phrase functions - Derivation
    "derive_compensating_logging_coverage",
    "derive_control_equivalence_score",
    # Phrase functions - Verification
    "verify_required_controls_for_tool",
    "verify_sanitization_profile",
]
