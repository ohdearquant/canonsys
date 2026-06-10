"""Policy domain: definitions, authorities, adapters, and releases.

Three-Key Architecture:
    Key 1 (PolicyDefinition): Legal-authored specification. WHAT is required.
    Key 2 (PolicyAdapter): Engineering implementation. HOW it's enforced.
    Key 3 (PolicyRelease): Versioned snapshot. WHEN it's active.

Separation ensures legal owns requirements, engineering owns implementation,
and releases provide immutable audit trail of what was enforced when.
"""

from .adapter import PolicyAdapter, PolicyAdapterContent
from .authority import PolicyAuthority
from .decision import PolicyDecision
from .definition import PolicyDefinition, PolicyDefinitionContent
from .release import PolicyRelease, PolicyReleaseContent
from .scope import PolicyScope
from .status import PolicyStatus

__all__ = (
    # Entities
    "PolicyAdapter",
    "PolicyAdapterContent",
    "PolicyDefinition",
    "PolicyDefinitionContent",
    "PolicyRelease",
    "PolicyReleaseContent",
    # Value objects
    "PolicyAuthority",
    "PolicyDecision",
    "PolicyScope",
    "PolicyStatus",
)
