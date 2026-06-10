"""Deployment domain phrases.

All deployment operations in one place:
- Requirement phrases: require_backup_verified, require_deployment_approval, etc.
- Verification phrases: verify_backup_complete, verify_rollback_plan_present
"""

from .require_backup_verified import RequireBackupVerifiedSpecs, require_backup_verified
from .require_deployment_approval import (
    RequireDeploymentApprovalSpecs,
    require_deployment_approval,
)
from .require_monitoring_active import (
    RequireMonitoringActiveSpecs,
    require_monitoring_active,
)
from .require_production_environment import (
    RequireProductionEnvironmentSpecs,
    require_production_environment,
)
from .require_rollback_tested import RequireRollbackTestedSpecs, require_rollback_tested
from .verify_backup_complete import VerifyBackupCompleteSpecs, verify_backup_complete
from .verify_rollback_plan_present import (
    VerifyRollbackPlanPresentSpecs,
    verify_rollback_plan_present,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "RequireBackupVerifiedSpecs",
    "RequireDeploymentApprovalSpecs",
    "RequireMonitoringActiveSpecs",
    "RequireProductionEnvironmentSpecs",
    "RequireRollbackTestedSpecs",
    "VerifyBackupCompleteSpecs",
    "VerifyRollbackPlanPresentSpecs",
    # Phrase functions
    "require_backup_verified",
    "require_deployment_approval",
    "require_monitoring_active",
    "require_production_environment",
    "require_rollback_tested",
    "verify_backup_complete",
    "verify_rollback_plan_present",
]
