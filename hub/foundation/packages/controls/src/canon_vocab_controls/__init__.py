"""Controls feature - vertical slice for control assessment and verification.

This module provides the complete controls domain implementation:
- Types: ControlStrength, ControlEquivalence, LoggingCoverage, and result dataclasses
- Phrases: assess, check, derive, verify operations
- Exceptions: ControlViolation and specific control-related errors

Regulatory context:
    - SOX Section 404 (Internal controls assessment)
    - SOC 2 CC4.1 (Control monitoring)
    - SOC 2 CC6.1 (Logical access controls)
    - SOC 2 CC6.7 (Data sanitization)
    - SOC 2 CC7.1 (Security monitoring)
    - SOC 2 CC7.2 (System monitoring)
    - ISO 27001 A.12.4 (Logging and monitoring)
    - ISO 27001 A.12.6.1 (Technical vulnerability management)
    - ISO 27001 A.18.2.1 (Compliance review)
    - CISA BOD 22-01 (KEV catalog)
    - NYC LL144 (AEDT tool requirements)
    - GDPR Article 32 (Security of processing)
    - NIST SP 800-88 (Media sanitization guidelines)

Usage:
    from canon_vocab_controls import (
        # Types
        ControlStrength,
        ControlCoverageResult,
        # Specs classes
        AssessControlCoverageSpecs,
        # Phrases
        assess_control_coverage,
        check_exploitability_status,
        # Exceptions
        ControlViolation,
        # Package metadata
        CONTROLS,
    )
"""

# Exceptions
from .exceptions import (
    ControlCoverageInsufficientError,
    ControlEquivalenceInsufficientError,
    ControlViolation,
    RequiredControlsMissingError,
    SanitizationCoverageInsufficientError,
)

# Package metadata
from .package import CONTROLS

# Phrases
from .phrases import (
    AssessControlCoverageSpecs,
    CheckExploitabilitySpecs,
    DeriveControlEquivalenceSpecs,
    DeriveLoggingCoverageSpecs,
    VerifySanitizationSpecs,
    VerifyToolControlsSpecs,
    assess_control_coverage,
    check_exploitability_status,
    derive_compensating_logging_coverage,
    derive_control_equivalence_score,
    verify_required_controls_for_tool,
    verify_sanitization_profile,
)

# Service
from .service import ControlsService

# Types
from .types import (
    ControlCoverageResult,
    ControlEquivalence,
    ControlEquivalenceResult,
    ControlStrength,
    ExploitabilityResult,
    LoggingCoverage,
    LoggingCoverageResult,
    SanitizationResult,
    ToolControlResult,
)

__all__ = [
    # Package metadata
    "CONTROLS",
    # Service
    "ControlsService",
    # Types - Enums
    "ControlEquivalence",
    "ControlStrength",
    "LoggingCoverage",
    # Types - Results
    "ControlCoverageResult",
    "ControlEquivalenceResult",
    "ExploitabilityResult",
    "LoggingCoverageResult",
    "SanitizationResult",
    "ToolControlResult",
    # Specs classes (Pydantic BaseModels)
    "AssessControlCoverageSpecs",
    "CheckExploitabilitySpecs",
    "DeriveControlEquivalenceSpecs",
    "DeriveLoggingCoverageSpecs",
    "VerifySanitizationSpecs",
    "VerifyToolControlsSpecs",
    # Exceptions
    "ControlCoverageInsufficientError",
    "ControlEquivalenceInsufficientError",
    "ControlViolation",
    "RequiredControlsMissingError",
    "SanitizationCoverageInsufficientError",
    # Phrases - Assessment
    "assess_control_coverage",
    # Phrases - Checks
    "check_exploitability_status",
    # Phrases - Derivation
    "derive_compensating_logging_coverage",
    "derive_control_equivalence_score",
    # Phrases - Verification
    "verify_required_controls_for_tool",
    "verify_sanitization_profile",
]
