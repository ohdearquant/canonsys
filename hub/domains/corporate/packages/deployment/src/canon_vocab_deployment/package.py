"""Deployment vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

DEPLOYMENT = VocabularyPackage(
    name="deployment",
    description="Deployment approval, backup verification, rollback testing, and monitoring activation.",
    feature_names=frozenset(
        {
            "require_backup_verified",
            "require_deployment_approval",
            "require_monitoring_active",
            "require_production_environment",
            "require_rollback_tested",
            "verify_backup_complete",
            "verify_rollback_plan_present",
        }
    ),
    schema_names=frozenset(
        {
            "ApprovalStatus",
            "EnvironmentType",
            "MonitoringStatus",
            "RollbackTestStatus",
        }
    ),
    regulatory_basis=("SOC 2 CC7.1-8.1",),
    version="2026.01",
    domain_module="canon_vocab_deployment",
)
