"""OPA/Rego policy engine utilities.

Key components:
- EnginePool: Thread-safe pool of pre-warmed regorus engines
- PolicyEngine: High-level facade for policy evaluation
- PolicyResolver: Determines which policies apply to context

Usage:
    from canon.utils.opa import (
        EnginePool, PolicyEngine, PolicyResolver,
        PolicyIndex, ResolutionContext,
    )

    # Create engine pool and policy engine
    pool = EnginePool(policies_path=Path("policies/"))
    engine = PolicyEngine(pool)

    # Resolve policies for context
    resolver = PolicyResolver(index, constitution)
    policies = resolver.resolve(context)

    # Evaluate policies directly
    for policy in policies:
        result = await engine.evaluate_single(policy, input_data)
"""

from .decoder import DecodedDecision, decode_policy
from .engine import (
    EnginePool,
    EnginePoolConfig,
    EnginePoolExhausted,
    PolicyEngine,
    ResolvedPolicy,
)
from .resolver import PolicyIndex, PolicyIndexEntry, PolicyResolver, ResolutionContext
from .types import AggregatedResult, PolicyResult

__all__ = (
    # Engine
    "EnginePool",
    "EnginePoolConfig",
    "EnginePoolExhausted",
    "PolicyEngine",
    "ResolvedPolicy",
    # Resolver
    "PolicyIndex",
    "PolicyIndexEntry",
    "PolicyResolver",
    "ResolutionContext",
    # Decoder
    "DecodedDecision",
    "decode_policy",
    # Types
    "PolicyResult",
    "AggregatedResult",
)
