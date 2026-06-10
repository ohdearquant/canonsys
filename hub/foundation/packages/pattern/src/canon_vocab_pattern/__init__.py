"""Pattern feature - vertical slice for pattern detection.

This module provides the complete pattern detection domain implementation:
- Specs: Pydantic BaseModels for phrase inputs/outputs
- Phrases: Pattern detection operations using @phrase decorator
- Types: Legacy result types (PriorActionCountResult, PatternThresholdResult, CumulativeAmountResult)
- Exceptions: PatternThresholdExceededError

Enables detection of repeated actions within a lookback window.
Critical for:
- Manager bypass pattern detection
- Credential renewal abuse
- Override frequency monitoring
- Budget reallocation abuse
- Expense exception stacking

Compliance Context:
    - "Five small exceptions = one material" detection
    - Progressive discipline support
    - AML transaction monitoring

Regulatory context:
    - SOX Section 302 (Management assessment)
    - BSA/AML (Suspicious activity patterns)
    - Employment law (Progressive discipline)

Usage:
    from canon_vocab_pattern import (
        # Specs (Pydantic BaseModels)
        DerivePriorActionCountSpecs,
        CheckPatternThresholdSpecs,
        DeriveCumulativeAmountSpecs,
        DeriveManagerBypassCount12mSpecs,
        DeriveManagerSalaryExceptionCount12mSpecs,
        CheckPriorEscalationsSpecs,
        CheckPriorExemptionsSpecs,
        CheckPriorBypassesSpecs,
        DeriveCumulativeReallocationAmountSpecs,
        DeriveCumulativeExceptionAmountSpecs,
        # Phrases
        derive_prior_action_count,
        check_pattern_threshold,
        derive_cumulative_amount,
        derive_manager_bypass_count_12m,
        derive_manager_salary_exception_count_12m,
        derive_cumulative_reallocation_amount,
        derive_cumulative_exception_amount,
        check_prior_escalations,
        check_prior_exemptions,
        check_prior_bypasses,
        # Types (legacy)
        PriorActionCountResult,
        PatternThresholdResult,
        CumulativeAmountResult,
        # Exceptions
        PatternThresholdExceededError,
        # Package metadata
        PATTERN,
    )
"""

# Exceptions
from .exceptions import PatternThresholdExceededError

# Package metadata
from .package import PATTERN

# Phrases (Specs + functions)
from .phrases import (
    CheckPatternThresholdSpecs,
    CheckPriorBypassesSpecs,
    CheckPriorEscalationsSpecs,
    CheckPriorExemptionsSpecs,
    DeriveCumulativeAmountSpecs,
    DeriveCumulativeExceptionAmountSpecs,
    DeriveCumulativeReallocationAmountSpecs,
    DeriveManagerBypassCount12mSpecs,
    DeriveManagerSalaryExceptionCount12mSpecs,
    DerivePriorActionCountSpecs,
    check_pattern_threshold,
    check_prior_bypasses,
    check_prior_escalations,
    check_prior_exemptions,
    derive_cumulative_amount,
    derive_cumulative_exception_amount,
    derive_cumulative_reallocation_amount,
    derive_manager_bypass_count_12m,
    derive_manager_salary_exception_count_12m,
    derive_prior_action_count,
)

# Service
from .service import PatternService

# Types (legacy - for backwards compatibility)
from .types import (
    CumulativeAmountResult,
    PatternThresholdResult,
    PriorActionCountResult,
)

__all__ = [
    # Package metadata
    "PATTERN",
    # Specs classes (Pydantic BaseModels)
    "CheckPatternThresholdSpecs",
    "CheckPriorBypassesSpecs",
    "CheckPriorEscalationsSpecs",
    "CheckPriorExemptionsSpecs",
    # Types (legacy)
    "CumulativeAmountResult",
    "DeriveCumulativeAmountSpecs",
    "DeriveCumulativeExceptionAmountSpecs",
    "DeriveCumulativeReallocationAmountSpecs",
    "DeriveManagerBypassCount12mSpecs",
    "DeriveManagerSalaryExceptionCount12mSpecs",
    "DerivePriorActionCountSpecs",
    # Exceptions
    "PatternThresholdExceededError",
    "PatternThresholdResult",
    "PriorActionCountResult",
    # Service
    "PatternService",
    # Phrase functions
    "check_pattern_threshold",
    "check_prior_bypasses",
    "check_prior_escalations",
    "check_prior_exemptions",
    "derive_cumulative_amount",
    "derive_cumulative_exception_amount",
    "derive_cumulative_reallocation_amount",
    "derive_manager_bypass_count_12m",
    "derive_manager_salary_exception_count_12m",
    "derive_prior_action_count",
]
