"""Infrastructure feature phrases.

All infrastructure-related async operations for:
- Check operations (DR cooldown)
- Derivation operations (risk bands, classifications, modes, SLA tracking, backup dependencies)
- Verification operations (traffic drain)
- Gate operations (backup verification)
"""

from .check_dr_test_cooldown import CheckDRTestCooldownSpecs, check_dr_test_cooldown
from .constants import (
    DEFAULT_COOLDOWN_HOURS,
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_MAX_SAFE_DEPTH,
    DEFAULT_SLA_HOURS,
    DEFAULT_THRESHOLD_PCT,
    THRESHOLD_HIGH,
    THRESHOLD_LOW,
    THRESHOLD_MEDIUM,
)
from .derive_data_loss_risk import DeriveDataLossRiskSpecs, derive_data_loss_risk
from .derive_degraded_hours import (
    DeriveDegradedHoursSpecs,
    derive_degraded_hours_last_30d,
)
from .derive_dependent_backups import (
    DeriveDependentBackupsSpecs,
    derive_dependent_backup_count,
)
from .derive_rows_read_band import DeriveRowsReadBandSpecs, derive_rows_read_band
from .derive_subdomain_depth import DeriveSubdomainDepthSpecs, derive_subdomain_depth
from .derive_tag_risk_class import DeriveTagRiskClassSpecs, derive_tag_risk_class
from .derive_utilization_volatility import (
    DeriveUtilizationVolatilitySpecs,
    derive_utilization_volatility,
)
from .derive_write_acceptance_mode import (
    DeriveWriteAcceptanceModeSpecs,
    derive_write_acceptance_mode,
)
from .require_backup_verified import (
    RequireBackupVerifiedSpecs,
    require_backup_verified,
)
from .verify_traffic_drained import VerifyTrafficDrainedSpecs, verify_traffic_drained

__all__ = [
    # Constants
    "DEFAULT_COOLDOWN_HOURS",
    "DEFAULT_LOOKBACK_HOURS",
    "DEFAULT_MAX_SAFE_DEPTH",
    "DEFAULT_SLA_HOURS",
    "DEFAULT_THRESHOLD_PCT",
    "THRESHOLD_HIGH",
    "THRESHOLD_LOW",
    "THRESHOLD_MEDIUM",
    # Specs classes (Pydantic BaseModels)
    "CheckDRTestCooldownSpecs",
    "DeriveDataLossRiskSpecs",
    "DeriveDegradedHoursSpecs",
    "DeriveDependentBackupsSpecs",
    "DeriveRowsReadBandSpecs",
    "DeriveSubdomainDepthSpecs",
    "DeriveTagRiskClassSpecs",
    "DeriveUtilizationVolatilitySpecs",
    "DeriveWriteAcceptanceModeSpecs",
    "RequireBackupVerifiedSpecs",
    "VerifyTrafficDrainedSpecs",
    # Phrase functions
    "check_dr_test_cooldown",
    "derive_data_loss_risk",
    "derive_degraded_hours_last_30d",
    "derive_dependent_backup_count",
    "derive_rows_read_band",
    "derive_subdomain_depth",
    "derive_tag_risk_class",
    "derive_utilization_volatility",
    "derive_write_acceptance_mode",
    "require_backup_verified",
    "verify_traffic_drained",
]
