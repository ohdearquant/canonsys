"""Corporate domain types.

Enums for deal phases, data sensitivity, and M&A condition tracking.
Result types for anti-gaming derivations.
"""

from .enums import (
    CarveOutStatus,
    CleanTeamReason,
    ConditionSatisfactionStatus,
    ConditionType,
    DataSensitivityLevel,
    DealPhase,
    FindingStatus,
    SensitiveDataCategory,
)
from .results import (
    CarveOutReadinessResult,
    CleanTeamRequiredResult,
    ConditionalFindingsAddressedResult,
    ConditionSatisfactionResult,
)

__all__ = [
    "CarveOutReadinessResult",
    "CarveOutStatus",
    "CleanTeamReason",
    "CleanTeamRequiredResult",
    "ConditionSatisfactionResult",
    "ConditionSatisfactionStatus",
    "ConditionType",
    "ConditionalFindingsAddressedResult",
    "DataSensitivityLevel",
    "DealPhase",
    "FindingStatus",
    "SensitiveDataCategory",
]
