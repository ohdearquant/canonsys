"""Infrastructure vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

INFRA = VocabularyPackage(
    name="infra",
    description="Infrastructure operations: DR testing, risk classification, SLA tracking, backup dependencies, and traffic drain.",
    feature_names=frozenset(
        {
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
        }
    ),
    schema_names=frozenset(
        {
            "DataLossRiskResult",
            "DegradedHoursResult",
            "DependentBackupsResult",
            "DRTestCooldownResult",
            "RowsReadBandResult",
            "SubdomainDepthResult",
            "TagRiskClassResult",
            "TrafficDrainResult",
            "UtilizationVolatilityResult",
            "WriteAcceptanceModeResult",
        }
    ),
    regulatory_basis=("SOC 2 CC7.1",),
    version="2026.01",
    domain_module="canon_vocab_infra",
)
