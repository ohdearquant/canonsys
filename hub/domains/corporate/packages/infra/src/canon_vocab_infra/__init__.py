"""Infrastructure features for operational readiness and compliance.

Complete vertical slice for infrastructure operations including:
- DR test cooldown checks
- Backup dependency derivation
- SLA degradation tracking
- Data loss risk derivation
- Query exfiltration risk banding
- Subdomain depth analysis
- Tag risk classification
- Utilization volatility analysis
- Write acceptance mode derivation
- Traffic drain verification

Regulatory context:
    - SOC 2 CC7.5 (Recovery procedures)
    - ISO 27001 A.17 (Business continuity)
    - ISO 27001 A.12.3 (Backup policy)
    - PCI DSS Req. 12.10 (Incident response)
    - NIST 800-53 SC-7 (Boundary protection)
    - SLA compliance requirements

Usage:
    from canon_vocab_infra import (
        # Check/Derive phrases
        check_dr_test_cooldown,
        derive_degraded_hours_last_30d,
        derive_dependent_backup_count,
        # Derivation phrases
        derive_data_loss_risk,
        derive_rows_read_band,
        derive_subdomain_depth,
        derive_tag_risk_class,
        derive_utilization_volatility,
        derive_write_acceptance_mode,
        # Verification phrases
        verify_traffic_drained,
        # Specs classes
        CheckDRTestCooldownSpecs,
        DeriveDataLossRiskSpecs,
        # Types
        RiskBand,
        TagRiskClass,
        WriteMode,
        # Exceptions
        RequirementNotMetError,
        # Package metadata
        INFRA,
    )
"""

# Package metadata
# Exceptions
from .exceptions import RequirementNotMetError
from .package import INFRA

# Phrases
from .phrases import (
    DEFAULT_COOLDOWN_HOURS,
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_MAX_SAFE_DEPTH,
    DEFAULT_SLA_HOURS,
    DEFAULT_THRESHOLD_PCT,
    THRESHOLD_HIGH,
    THRESHOLD_LOW,
    THRESHOLD_MEDIUM,
    CheckDRTestCooldownSpecs,
    DeriveDataLossRiskSpecs,
    DeriveDegradedHoursSpecs,
    DeriveDependentBackupsSpecs,
    DeriveRowsReadBandSpecs,
    DeriveSubdomainDepthSpecs,
    DeriveTagRiskClassSpecs,
    DeriveUtilizationVolatilitySpecs,
    DeriveWriteAcceptanceModeSpecs,
    VerifyTrafficDrainedSpecs,
    check_dr_test_cooldown,
    derive_data_loss_risk,
    derive_degraded_hours_last_30d,
    derive_dependent_backup_count,
    derive_rows_read_band,
    derive_subdomain_depth,
    derive_tag_risk_class,
    derive_utilization_volatility,
    derive_write_acceptance_mode,
    verify_traffic_drained,
)

# Service
from .service import InfraService

# Types
from .types import (
    DataLossRiskResult,
    DegradedHoursResult,
    DependentBackupsResult,
    DRTestCooldownResult,
    RiskBand,
    RowsReadBandResult,
    SubdomainDepthResult,
    TagRiskClass,
    TagRiskClassResult,
    TrafficDrainResult,
    UtilizationVolatilityResult,
    WriteAcceptanceModeResult,
    WriteMode,
)

__all__ = [
    # Package metadata
    "INFRA",
    # Service
    "InfraService",
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
    # Result types (legacy frozen dataclasses)
    "DRTestCooldownResult",
    "DataLossRiskResult",
    "DegradedHoursResult",
    "DependentBackupsResult",
    "DeriveDataLossRiskSpecs",
    "DeriveDegradedHoursSpecs",
    "DeriveDependentBackupsSpecs",
    "DeriveRowsReadBandSpecs",
    "DeriveSubdomainDepthSpecs",
    "DeriveTagRiskClassSpecs",
    "DeriveUtilizationVolatilitySpecs",
    "DeriveWriteAcceptanceModeSpecs",
    # Exceptions
    "RequirementNotMetError",
    # Literal types
    "RiskBand",
    "RowsReadBandResult",
    "SubdomainDepthResult",
    "TagRiskClass",
    "TagRiskClassResult",
    "TrafficDrainResult",
    "UtilizationVolatilityResult",
    "VerifyTrafficDrainedSpecs",
    "WriteAcceptanceModeResult",
    "WriteMode",
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
    "verify_traffic_drained",
]
