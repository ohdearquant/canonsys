"""Deployment features for operational readiness controls.

Complete vertical slice for deployment controls including:
- Backup verification
- Approval gates
- Rollback plans
- Environment checks
- Monitoring requirements

Regulatory context:
    - SOX Section 404 (Change management controls)
    - SOC 2 CC8.1 (Change management)
    - ISO 27001 A.12.1.2 (Change management)
    - NIST SP 800-53 (Security controls)
    - PCI DSS v4.0 (Separation of environments)

Usage:
    from canon_vocab_deployment import (
        # Service
        DeploymentService,
        # Phrases
        require_deployment_approval,
        require_production_environment,
        require_backup_verified,
        require_monitoring_active,
        require_rollback_tested,
        verify_backup_complete,
        verify_rollback_plan_present,
        # Specs
        RequireDeploymentApprovalSpecs,
        RequireProductionEnvironmentSpecs,
        RequireBackupVerifiedSpecs,
        RequireMonitoringActiveSpecs,
        RequireRollbackTestedSpecs,
        VerifyBackupCompleteSpecs,
        VerifyRollbackPlanPresentSpecs,
        # Types
        ApprovalStatus,
        EnvironmentType,
        MonitoringStatus,
        RollbackTestStatus,
        # Exceptions
        DeploymentApprovalRequiredError,
        ProductionEnvironmentRequiredError,
        # Package metadata
        DEPLOYMENT,
    )
"""

# Package metadata
# Exceptions
from .exceptions import (
    DeploymentApprovalRequiredError,
    ProductionEnvironmentRequiredError,
    RequirementNotMetError,
)
from .package import DEPLOYMENT

# Phrases
from .phrases import (
    RequireBackupVerifiedSpecs,
    RequireDeploymentApprovalSpecs,
    RequireMonitoringActiveSpecs,
    RequireProductionEnvironmentSpecs,
    RequireRollbackTestedSpecs,
    VerifyBackupCompleteSpecs,
    VerifyRollbackPlanPresentSpecs,
    require_backup_verified,
    require_deployment_approval,
    require_monitoring_active,
    require_production_environment,
    require_rollback_tested,
    verify_backup_complete,
    verify_rollback_plan_present,
)

# Service
from .service import DeploymentService

# Types
from .types import ApprovalStatus, EnvironmentType, MonitoringStatus, RollbackTestStatus

__all__ = [
    # Package metadata
    "DEPLOYMENT",
    # Service
    "DeploymentService",
    # Specs classes (Pydantic BaseModels)
    "RequireBackupVerifiedSpecs",
    "RequireDeploymentApprovalSpecs",
    "RequireMonitoringActiveSpecs",
    "RequireProductionEnvironmentSpecs",
    "RequireRollbackTestedSpecs",
    "VerifyBackupCompleteSpecs",
    "VerifyRollbackPlanPresentSpecs",
    # Types - Enums
    "ApprovalStatus",
    "EnvironmentType",
    "MonitoringStatus",
    "RollbackTestStatus",
    # Exceptions
    "DeploymentApprovalRequiredError",
    "ProductionEnvironmentRequiredError",
    "RequirementNotMetError",
    # Phrase functions
    "require_backup_verified",
    "require_deployment_approval",
    "require_monitoring_active",
    "require_production_environment",
    "require_rollback_tested",
    "verify_backup_complete",
    "verify_rollback_plan_present",
]
