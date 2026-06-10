"""Enforcement module - services, hooks, and compliance types.

Usage:
    from canon.enforcement import (
        CanonService, CanonCalling, ServiceContext, RequestContext,
        action, InvariantViolation,
    )

    class MyService(CanonService):
        config = CanonServiceConfig(provider="canon", name="my_service")

        @action(evidence_type="my_service.do_thing")
        async def do_thing(self, payload, ctx):
            return {"done": True}
"""

# Enforcement primitives (moved from kron/enforcement/)
from .config import KronConfig, ServiceConfig
from .context import QueryFn, RequestContext
from .degraded import (
    DegradedMode,
    DegradedModeConfig,
    DegradedReason,
    DegradedResult,
    configure_degraded_mode,
    get_degraded_mode,
)
from .errors import RequirementNotMetError
from .exceptions import (
    AIGovernanceViolation,
    AuthorizationViolation,
    ConsentViolation,
    DataProtectionViolation,
    EvidenceViolation,
    InvariantViolation,
    TimingViolation,
)
from .executor import canon_phrase, canon_query_fn
from .hooks import create_evidence_hook, create_recorded_model
from .policy import PolicyEngine, PolicyResolver, ResolvedPolicy
from .service import (
    ActionMeta,
    CanonActionMeta,
    CanonCalling,
    CanonService,
    CanonServiceConfig,
    KronService,
    ServiceContext,
    action,
    canon_action,
    get_action_meta,
    get_canon_action_meta,
    kron_action,
)
from .types import (
    AggregatedResult,
    EnforcementLevel,
    PolicyResult,
    ctx_to_evidence_data,
)
from .vocabulary import (
    FeatureSpec,
    WorkflowSpec,
    WorkflowStep,
    compose_workflow,
    get_feature,
    list_categories,
    list_features,
    vocabulary,
)

__all__ = (
    # Kron enforcement primitives (moved from kron.enforcement)
    "QueryFn",
    "RequestContext",
    "KronConfig",
    "ServiceConfig",
    "ActionMeta",
    "KronService",
    "get_action_meta",
    "kron_action",
    "PolicyEngine",
    "PolicyResolver",
    "ResolvedPolicy",
    # Policy Types (EnforcementLevel re-exported from canon.kron)
    "EnforcementLevel",
    "PolicyResult",
    "AggregatedResult",
    # Degraded Mode
    "DegradedReason",
    "DegradedModeConfig",
    "DegradedResult",
    "DegradedMode",
    "get_degraded_mode",
    "configure_degraded_mode",
    # Hooks (for vendor API calls)
    "create_evidence_hook",
    "create_recorded_model",
    # Context
    "ServiceContext",
    "RequestContext",
    # Config
    "CanonServiceConfig",
    # Service
    "CanonService",
    "CanonCalling",
    # Decorators
    "action",
    "canon_action",
    "CanonActionMeta",
    "get_canon_action_meta",
    # Exceptions (invariant violations)
    "InvariantViolation",
    "ConsentViolation",
    "TimingViolation",
    "AuthorizationViolation",
    "EvidenceViolation",
    "DataProtectionViolation",
    "AIGovernanceViolation",
    # Errors (business requirement failures)
    "RequirementNotMetError",
    # Executor (entity-aware phrases)
    "canon_phrase",
    "canon_query_fn",
    "ctx_to_evidence_data",
    # Vocabulary
    "vocabulary",
    "FeatureSpec",
    "WorkflowSpec",
    "WorkflowStep",
    "get_feature",
    "list_features",
    "list_categories",
    "compose_workflow",
)
