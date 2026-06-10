"""Corporate domain phrases.

Anti-gaming derivation phrases for M&A compliance.

These phrases DERIVE requirements from evidence rather than
verifying user assertions. This is the core anti-gaming pattern.

Regulatory Context:
    - Hart-Scott-Rodino Act (HSR) - antitrust filing/waiting
    - Sherman Act Section 1 - information sharing restrictions
    - FTC/DOJ Merger Guidelines - gun-jumping prevention
    - SEC M&A disclosure rules
"""

from .derive_carve_out_readiness import (
    DeriveCarveOutReadinessSpecs,
    derive_carve_out_readiness,
)
from .derive_clean_team_required import (
    DeriveCleanTeamRequiredSpecs,
    derive_clean_team_required,
)
from .derive_condition_satisfaction_status import (
    DeriveConditionSatisfactionSpecs,
    derive_condition_satisfaction_status,
)
from .derive_conditional_findings_addressed import (
    DeriveConditionalFindingsAddressedSpecs,
    derive_conditional_findings_addressed,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "DeriveCarveOutReadinessSpecs",
    "DeriveCleanTeamRequiredSpecs",
    "DeriveConditionSatisfactionSpecs",
    "DeriveConditionalFindingsAddressedSpecs",
    # Derivation phrase functions (anti-gaming)
    "derive_carve_out_readiness",
    "derive_clean_team_required",
    "derive_condition_satisfaction_status",
    "derive_conditional_findings_addressed",
]
