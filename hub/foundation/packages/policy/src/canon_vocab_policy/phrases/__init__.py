"""Policy domain phrases.

All policy operations in one place:
- Definition: create_policy_definition
- Adapter: create_policy_adapter
- Release: create_policy_release, publish_policy_release
- Evaluation: evaluate_policy, evaluate_conditional_policy, resolve_policy
- Require: require_policy_active, require_policy_pass, require_policy_version_current
- Query: get_applicable_policies
- Verify: verify_policy_not_overridden
"""

from .create_adapter import CreateAdapterSpecs, create_policy_adapter
from .create_definition import CreateDefinitionSpecs, create_policy_definition
from .create_release import CreateReleaseSpecs, create_policy_release
from .derive_risk_tier import DeriveRiskTierSpecs, RiskTier, derive_risk_tier
from .evaluate_conditional_policy import (
    EvaluateConditionalPolicySpecs,
    evaluate_conditional_policy,
)
from .evaluate_policy import EvaluatePolicySpecs, evaluate_policy
from .get_applicable_policies import GetApplicablePoliciesSpecs, get_applicable_policies
from .publish_release import PublishReleaseSpecs, publish_policy_release
from .require_policy_active import RequirePolicyActiveSpecs, require_policy_active
from .require_policy_pass import RequirePolicyPassSpecs, require_policy_pass
from .require_policy_version_current import (
    RequirePolicyVersionCurrentSpecs,
    require_policy_version_current,
)
from .resolve_policy import ResolvePolicySpecs, resolve_policy
from .verify_policy_not_overridden import (
    VerifyPolicyNotOverriddenSpecs,
    verify_policy_not_overridden,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "CreateAdapterSpecs",
    "CreateDefinitionSpecs",
    "CreateReleaseSpecs",
    "DeriveRiskTierSpecs",
    "EvaluateConditionalPolicySpecs",
    "EvaluatePolicySpecs",
    "GetApplicablePoliciesSpecs",
    "PublishReleaseSpecs",
    "RequirePolicyActiveSpecs",
    "RequirePolicyPassSpecs",
    "RequirePolicyVersionCurrentSpecs",
    "ResolvePolicySpecs",
    "VerifyPolicyNotOverriddenSpecs",
    # Enums
    "RiskTier",
    # Create phrases
    "create_policy_adapter",
    "create_policy_definition",
    "create_policy_release",
    # Derive phrases
    "derive_risk_tier",
    # Evaluate phrases
    "evaluate_conditional_policy",
    "evaluate_policy",
    # Get phrases
    "get_applicable_policies",
    # Publish phrases
    "publish_policy_release",
    # Require phrases
    "require_policy_active",
    "require_policy_pass",
    "require_policy_version_current",
    # Resolve phrases
    "resolve_policy",
    # Verify phrases
    "verify_policy_not_overridden",
]
