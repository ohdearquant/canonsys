"""Pattern detection phrases.

Pattern detection for compliance monitoring:
- derive_prior_action_count: Derive count of actions within lookback window
- check_pattern_threshold: Check if count exceeds threshold
- derive_cumulative_amount: Sum amounts over period for anti-gaming detection

Surface-specific wrappers:
- derive_manager_bypass_count_12m: this surface manager posting bypass tracking
- derive_manager_salary_exception_count_12m: this surface salary exception tracking
- check_prior_escalations: this surface privilege escalation tracking
- check_prior_exemptions: this surface MFA exemption tracking
- check_prior_bypasses: this surface application bypass tracking
- derive_cumulative_reallocation_amount: this surface budget reallocation patterns
- derive_cumulative_exception_amount: this surface expense exception patterns

Gate:
- require_no_adverse_pattern: Enforce pattern threshold limits
"""

from .check_pattern_threshold import CheckPatternThresholdSpecs, check_pattern_threshold
from .check_prior_bypasses import CheckPriorBypassesSpecs, check_prior_bypasses
from .check_prior_escalations import CheckPriorEscalationsSpecs, check_prior_escalations
from .check_prior_exemptions import CheckPriorExemptionsSpecs, check_prior_exemptions
from .derive_cumulative_amount import (
    DeriveCumulativeAmountSpecs,
    derive_cumulative_amount,
)
from .derive_cumulative_exception_amount import (
    DeriveCumulativeExceptionAmountSpecs,
    derive_cumulative_exception_amount,
)
from .derive_cumulative_reallocation_amount import (
    DeriveCumulativeReallocationAmountSpecs,
    derive_cumulative_reallocation_amount,
)
from .derive_manager_bypass_count_12m import (
    DeriveManagerBypassCount12mSpecs,
    derive_manager_bypass_count_12m,
)
from .derive_manager_salary_exception_count_12m import (
    DeriveManagerSalaryExceptionCount12mSpecs,
    derive_manager_salary_exception_count_12m,
)
from .derive_prior_action_count import (
    DerivePriorActionCountSpecs,
    derive_prior_action_count,
)
from .require_no_adverse_pattern import (
    RequireNoAdversePatternSpecs,
    require_no_adverse_pattern,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "CheckPatternThresholdSpecs",
    "CheckPriorBypassesSpecs",
    "CheckPriorEscalationsSpecs",
    "CheckPriorExemptionsSpecs",
    "DeriveCumulativeAmountSpecs",
    "DeriveCumulativeExceptionAmountSpecs",
    "DeriveCumulativeReallocationAmountSpecs",
    "DeriveManagerBypassCount12mSpecs",
    "DeriveManagerSalaryExceptionCount12mSpecs",
    "DerivePriorActionCountSpecs",
    "RequireNoAdversePatternSpecs",
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
    "require_no_adverse_pattern",
]
