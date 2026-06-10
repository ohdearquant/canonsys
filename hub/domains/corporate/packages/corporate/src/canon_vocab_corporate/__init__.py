"""Corporate feature - vertical slice for M&A compliance management.

This module provides the complete corporate/M&A domain implementation:
- Types: DealPhase, DataSensitivityLevel, CleanTeamReason, FindingStatus,
  CarveOutStatus, ConditionType, ConditionSatisfactionStatus
- Results: CleanTeamRequiredResult, ConditionalFindingsAddressedResult,
  CarveOutReadinessResult, ConditionSatisfactionResult
- Phrases: derive_* (anti-gaming derivations)
- Exceptions: CorporateViolation, CleanTeamRequirementDerivedError, etc.

ANTI-GAMING ARCHITECTURE:

The Corporate domain implements DERIVATION phrases rather than verification
actions. The key difference:

    VERIFICATION (what others do):
        User asserts: "clean team not required"
        System verifies: check if user's assertion is valid
        Problem: User can game the system by making false assertions

    DERIVATION (what we do):
        System derives: examine data categories present
        System determines: clean team IS required because competitive_pricing found
        Benefit: User cannot game - requirement derived from evidence

This pattern prevents:
- Gun-jumping violations (HSR Act)
- Antitrust violations (Sherman Act Section 1)
- Information barrier breaches (FTC/DOJ Guidelines)
- Material misrepresentation (SEC Rules)

Regulatory context:
    - Hart-Scott-Rodino Act (HSR) - antitrust filing/waiting
    - Sherman Act Section 1 - information sharing restrictions
    - FTC/DOJ Merger Guidelines - gun-jumping prevention
    - SEC M&A disclosure rules

Usage:
    from canon_vocab_corporate import (
        # Types
        DealPhase,
        CleanTeamReason,
        ConditionType,
        # Specs classes
        DeriveCleanTeamRequiredSpecs,
        DeriveConditionalFindingsAddressedSpecs,
        # Phrases (derivations)
        derive_clean_team_required,
        derive_conditional_findings_addressed,
        derive_carve_out_readiness,
        derive_condition_satisfaction_status,
        # Results
        CleanTeamRequiredResult,
        ConditionalFindingsAddressedResult,
        CarveOutReadinessResult,
        ConditionSatisfactionResult,
        # Exceptions
        CleanTeamRequirementDerivedError,
        FindingsNotAddressedError,
    )

    # Derive whether clean team is required (anti-gaming)
    result = await derive_clean_team_required(
        DeriveCleanTeamRequiredSpecs(deal_id=deal_id),
        ctx,
    )
    if result["required"]:
        # Clean team required based on data categories
        print(f"Required: {result['reason']} due to {result['sensitivity_triggers']}")
"""

# Exceptions
from .exceptions import (
    CarveOutNotReadyError,
    CleanTeamRequirementDerivedError,
    ConditionsNotSatisfiedError,
    CorporateViolation,
    FindingsNotAddressedError,
)

# Package metadata
from .package import CORPORATE

# Phrases (derivation phrases - anti-gaming)
from .phrases import (  # Specs classes; Phrase functions
    DeriveCarveOutReadinessSpecs,
    DeriveCleanTeamRequiredSpecs,
    DeriveConditionalFindingsAddressedSpecs,
    DeriveConditionSatisfactionSpecs,
    derive_carve_out_readiness,
    derive_clean_team_required,
    derive_condition_satisfaction_status,
    derive_conditional_findings_addressed,
)

# Service
from .service import CorporateService

# Types
from .types import (
    CarveOutReadinessResult,
    CarveOutStatus,
    CleanTeamReason,
    CleanTeamRequiredResult,
    ConditionalFindingsAddressedResult,
    ConditionSatisfactionResult,
    ConditionSatisfactionStatus,
    ConditionType,
    DataSensitivityLevel,
    DealPhase,
    FindingStatus,
    SensitiveDataCategory,
)

__all__ = [
    # Package metadata
    "CORPORATE",
    # Exceptions
    "CarveOutNotReadyError",
    "CleanTeamRequirementDerivedError",
    "ConditionsNotSatisfiedError",
    "CorporateViolation",
    "FindingsNotAddressedError",
    # Specs classes (Pydantic BaseModels)
    "DeriveCarveOutReadinessSpecs",
    "DeriveCleanTeamRequiredSpecs",
    "DeriveConditionSatisfactionSpecs",
    "DeriveConditionalFindingsAddressedSpecs",
    # Phrase functions (derivations)
    "derive_carve_out_readiness",
    "derive_clean_team_required",
    "derive_condition_satisfaction_status",
    "derive_conditional_findings_addressed",
    # Service
    "CorporateService",
    # Types - Enums
    "CarveOutStatus",
    "CleanTeamReason",
    "ConditionSatisfactionStatus",
    "ConditionType",
    "DataSensitivityLevel",
    "DealPhase",
    "FindingStatus",
    "SensitiveDataCategory",
    # Types - Results (frozen dataclasses)
    "CarveOutReadinessResult",
    "CleanTeamRequiredResult",
    "ConditionalFindingsAddressedResult",
    "ConditionSatisfactionResult",
]
