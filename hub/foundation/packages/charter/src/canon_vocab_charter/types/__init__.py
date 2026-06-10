"""Charter types module.

Exports:
    CharterStatus: Charter lifecycle states enum (DRAFT, ACTIVE, SUSPENDED, RETIRED)
    Charter: Charter governance document entity
    CharterSurfaceBinding: Binding between charter and control surface
    CharterContent: Creation payload for Charter
    CharterSurfaceBindingContent: Creation payload for surface bindings
    SurfaceBinding: Result type for bound surfaces (legacy, prefer CharterSurfaceBinding)

Result types:
    CreateCharterResult: Result of charter creation
    ActivateCharterResult: Result of charter activation
    BindSurfaceResult: Result of surface binding operation
    DecisionResult: Result of decision evaluation against charter policy
"""

from .charter import (
    Charter,
    CharterContent,
    CharterSurfaceBinding,
    CharterSurfaceBindingContent,
)
from .results import (
    ActivateCharterResult,
    BindSurfaceResult,
    CreateCharterResult,
    DecisionResult,
    SurfaceBinding,
)
from .status import CharterStatus

__all__ = (
    # Enums
    "CharterStatus",
    # Entities
    "Charter",
    "CharterSurfaceBinding",
    # Creation payloads
    "CharterContent",
    "CharterSurfaceBindingContent",
    # Result types
    "ActivateCharterResult",
    "BindSurfaceResult",
    "CreateCharterResult",
    "DecisionResult",
    "SurfaceBinding",
)
