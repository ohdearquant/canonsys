"""Charter feature - vertical slice for charter management.

This module provides the complete charter domain implementation:
- Types: Charter, CharterContent, CharterStatus, CharterSurfaceBinding
- Phrases: create_charter, activate_charter, bind_surface, evaluate_decision
- Exceptions: CharterNotFoundError, CharterStatusError, etc.

The Charter is the root governance document for a tenant. It defines:
- Which surfaces (control points) are active
- What policies govern each surface
- What evidence is required for decisions

Lifecycle: DRAFT -> ACTIVE -> SUSPENDED/RETIRED

Usage:
    from canon_vocab_charter import (
        # Specs classes
        CreateCharterSpecs,
        ActivateCharterSpecs,
        BindSurfaceSpecs,
        EvaluateDecisionSpecs,
        # Types
        Charter,
        CharterContent,
        CharterStatus,
        # Phrases
        create_charter,
        activate_charter,
        bind_surface,
        evaluate_decision,
        # Package metadata
        CHARTER,
    )

    # Create a draft charter
    result = await create_charter(
        {"name": "ACME Corp Hiring Charter", "version": "1.0.0"},
        ctx,
    )

    # Bind surfaces and activate
    await bind_surface(
        {"charter_id": result["charter_id"], "surface_id": "CS-001", "policy_version": "sha256:..."},
        ctx,
    )
    await activate_charter({"charter_id": result["charter_id"]}, ctx)

    # Evaluate decisions
    decision = await evaluate_decision(
        {
            "charter_id": result["charter_id"],
            "surface_id": "CS-001",
            "facts": {"consent.verified": True},
        },
        ctx,
    )
"""

# Exceptions
from .exceptions import (
    CharterAlreadyActiveError,
    CharterError,
    CharterNotFoundError,
    CharterNotRatifiedError,
    CharterStatusError,
    PolicyEvaluationError,
    SurfaceAlreadyBoundError,
    SurfaceNotBoundError,
)

# Package metadata
from .package import CHARTER

# Phrases
from .phrases import (
    ActivateCharterSpecs,
    BindSurfaceSpecs,
    CreateCharterSpecs,
    EvaluateDecisionSpecs,
    activate_charter,
    bind_surface,
    create_charter,
    evaluate_decision,
)

# Service
from .service import CharterService

# Types
# Legacy result types (deprecated, use Specs classes)
from .types import (
    ActivateCharterResult,
    BindSurfaceResult,
    Charter,
    CharterContent,
    CharterStatus,
    CharterSurfaceBinding,
    CharterSurfaceBindingContent,
    CreateCharterResult,
    DecisionResult,
    SurfaceBinding,
)

__all__ = (
    # Package metadata
    "CHARTER",
    # Service
    "CharterService",
    # Specs classes (Pydantic BaseModels)
    "ActivateCharterSpecs",
    "BindSurfaceSpecs",
    "CreateCharterSpecs",
    "EvaluateDecisionSpecs",
    # Types
    "Charter",
    "CharterContent",
    "CharterStatus",
    "CharterSurfaceBinding",
    "CharterSurfaceBindingContent",
    "SurfaceBinding",
    # Legacy result types (deprecated)
    "ActivateCharterResult",
    "BindSurfaceResult",
    "CreateCharterResult",
    "DecisionResult",
    # Phrases
    "activate_charter",
    "bind_surface",
    "create_charter",
    "evaluate_decision",
    # Exceptions
    "CharterAlreadyActiveError",
    "CharterError",
    "CharterNotFoundError",
    "CharterNotRatifiedError",
    "CharterStatusError",
    "PolicyEvaluationError",
    "SurfaceAlreadyBoundError",
    "SurfaceNotBoundError",
)
