"""Scope domain phrases.

All scope operations in one place:
- Creation: create_scope_manifest
- Verification: verify_scope_manifest, verify_scope_definition, etc.
- Derivation: derive_scope_minimization
- Checks: check_environment_scope
- Gate: require_scope_valid

Regulatory context:
    - GDPR Art. 5(1)(c): Data minimization
    - SOC 2 CC6.1: Logical access controls
    - ISO 27001 A.9.1.1: Access control policy
    - HIPAA 164.502(b): Minimum necessary standard
    - GDPR Art. 44-49: Cross-border transfer restrictions
"""

from .check_environment_scope import CheckEnvironmentScopeSpecs, check_environment_scope
from .create_scope_manifest import CreateScopeManifestSpecs, create_scope_manifest
from .derive_scope_minimization import (
    DeriveScopeMinimizationSpecs,
    derive_scope_minimization,
)
from .require_scope_valid import RequireScopeValidSpecs, require_scope_valid
from .verify_channel_allowed import VerifyChannelAllowedSpecs, verify_channel_allowed
from .verify_dataset_snapshot import (
    VerifyDatasetSnapshotSpecs,
    verify_dataset_snapshot_match,
)
from .verify_destination_allowed import (
    VerifyDestinationAllowedSpecs,
    verify_destination_allowed,
)
from .verify_group_membership_snapshot import (
    VerifyGroupMembershipSnapshotSpecs,
    verify_group_membership_snapshot,
)
from .verify_scope_definition import VerifyScopeDefinitionSpecs, verify_scope_definition
from .verify_scope_manifest import VerifyScopeManifestSpecs, verify_scope_manifest
from .verify_stakeholder_notification import (
    VerifyStakeholderNotificationSpecs,
    verify_stakeholder_notification_complete,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "CheckEnvironmentScopeSpecs",
    "CreateScopeManifestSpecs",
    "DeriveScopeMinimizationSpecs",
    "RequireScopeValidSpecs",
    "VerifyChannelAllowedSpecs",
    "VerifyDatasetSnapshotSpecs",
    "VerifyDestinationAllowedSpecs",
    "VerifyGroupMembershipSnapshotSpecs",
    "VerifyScopeDefinitionSpecs",
    "VerifyScopeManifestSpecs",
    "VerifyStakeholderNotificationSpecs",
    # Phrase functions
    "check_environment_scope",
    "create_scope_manifest",
    "derive_scope_minimization",
    "require_scope_valid",
    "verify_channel_allowed",
    "verify_dataset_snapshot_match",
    "verify_destination_allowed",
    "verify_group_membership_snapshot",
    "verify_scope_definition",
    "verify_scope_manifest",
    "verify_stakeholder_notification_complete",
]
