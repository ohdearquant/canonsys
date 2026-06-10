"""Policy feature - vertical slice for policy management.

This module provides the complete policy domain implementation:

DUAL-KEY ARCHITECTURE:
- PolicyDefinition: Legal/Compliance owned (WHAT is required)
- PolicyAdapter: Engineering owned (HOW it's implemented)
- PolicyRelease: Immutable snapshot of definitions + adapters

TYPES:
- PolicyDefinition, PolicyDefinitionContent
- PolicyAdapter, PolicyAdapterContent
- PolicyRelease, PolicyReleaseContent
- PolicyAuthority, PolicyScope, PolicyStatus, PolicyDecision

PHRASES:
- create_policy_definition, create_policy_adapter
- create_policy_release, publish_policy_release
- evaluate_policy, resolve_policy

FLOW:
1. Legal creates PolicyDefinition (requirements in legal language)
2. Engineering creates PolicyAdapter (Rego implementation)
3. Release bundles definitions + adapters (immutable snapshot)
4. Charter references release (tenant agreement)
5. evaluate_policy fetches Rego from DB and evaluates

Usage:
    from canon_vocab_policy import (
        # Types
        PolicyDefinition,
        PolicyAdapter,
        PolicyRelease,
        # Phrases
        CreateDefinitionSpecs,
        CreateAdapterSpecs,
        CreateReleaseSpecs,
        PublishReleaseSpecs,
        EvaluatePolicySpecs,
        create_policy_definition,
        create_policy_adapter,
        create_policy_release,
        publish_policy_release,
        evaluate_policy,
        # Package metadata
        POLICY,
    )

    # Legal creates definition
    definition = await create_policy_definition(
        CreateDefinitionSpecs(
            policy_id="us.nyc.fair_chance",
            version="1.0.0",
            name="NYC Fair Chance Act",
            authority=PolicyAuthority(...).to_dict(),
            requirements=["inquiry_prohibition_after_conditional_offer"],
        ),
        ctx,
    )

    # Engineering implements adapter
    adapter = await create_policy_adapter(
        CreateAdapterSpecs(
            policy_id="us.nyc.fair_chance",
            policy_definition_version="1.0.0",
            adapter_version="1",
            rego_content='''
                package us.nyc.fair_chance
                default allow = false
                deny["inquiry_before_offer"] { ... }
            ''',
        ),
        ctx,
    )

    # Create and publish release
    release = await create_policy_release(
        CreateReleaseSpecs(version="2026.01", policy_ids=("us.nyc.fair_chance",)),
        ctx,
    )
    await publish_policy_release(
        PublishReleaseSpecs(release_id=release["release_id"]),
        ctx,
    )

    # Evaluate at runtime
    result = await evaluate_policy(
        EvaluatePolicySpecs(
            policy_id="us.nyc.fair_chance",
            facts={"conditional_offer_made": True, "background_check_completed": False},
        ),
        ctx,
    )
"""

# Exceptions
from .exceptions import (
    PolicyAdapterNotFoundError,
    PolicyAdapterVersionMismatchError,
    PolicyDefinitionAlreadyExistsError,
    PolicyDefinitionNotEffectiveError,
    PolicyDefinitionNotFoundError,
    PolicyDeniedError,
    PolicyError,
    PolicyEvaluationError,
    PolicyReleaseAlreadyPublishedError,
    PolicyReleaseNotFoundError,
    PolicyReleaseNotPublishedError,
)

# Package metadata
from .package import POLICY

# Phrases
from .phrases import (
    CreateAdapterSpecs,
    CreateDefinitionSpecs,
    CreateReleaseSpecs,
    EvaluatePolicySpecs,
    PublishReleaseSpecs,
    ResolvePolicySpecs,
    create_policy_adapter,
    create_policy_definition,
    create_policy_release,
    evaluate_policy,
    publish_policy_release,
    resolve_policy,
)

# Service
from .service import PolicyService

# Types
from .types import (
    PolicyAdapter,
    PolicyAdapterContent,
    PolicyAuthority,
    PolicyDecision,
    PolicyDefinition,
    PolicyDefinitionContent,
    PolicyRelease,
    PolicyReleaseContent,
    PolicyScope,
    PolicyStatus,
)

__all__ = [
    # Package metadata
    "POLICY",
    # Types - Entities
    "PolicyAdapter",
    "PolicyDefinition",
    "PolicyRelease",
    # Types - Content
    "PolicyAdapterContent",
    "PolicyDefinitionContent",
    "PolicyReleaseContent",
    # Types - Embedded
    "PolicyAuthority",
    # Types - Enums
    "PolicyDecision",
    "PolicyScope",
    "PolicyStatus",
    # Phrases - Specs (Pydantic BaseModels)
    "CreateAdapterSpecs",
    "CreateDefinitionSpecs",
    "CreateReleaseSpecs",
    "EvaluatePolicySpecs",
    "PublishReleaseSpecs",
    "ResolvePolicySpecs",
    # Phrases - Functions
    "create_policy_adapter",
    "create_policy_definition",
    "create_policy_release",
    "evaluate_policy",
    "publish_policy_release",
    "resolve_policy",
    # Service
    "PolicyService",
    # Exceptions
    "PolicyAdapterNotFoundError",
    "PolicyAdapterVersionMismatchError",
    "PolicyDefinitionAlreadyExistsError",
    "PolicyDefinitionNotEffectiveError",
    "PolicyDefinitionNotFoundError",
    "PolicyDeniedError",
    "PolicyError",
    "PolicyEvaluationError",
    "PolicyReleaseAlreadyPublishedError",
    "PolicyReleaseNotFoundError",
    "PolicyReleaseNotPublishedError",
]
