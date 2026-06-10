"""Type re-exports for convenient imports.

This module re-exports commonly used types from their canonical locations
so consumers can use shorter import paths.

Usage:
    from canon.types import Evidence, ConsentToken, Entity, FK

Instead of:
    from canon.entities.evidence.evidence import Evidence
    from canon.entities.consent import ConsentToken
    from canon.entities.entity import Entity
    from canon.db import FK
"""

# Core entity system
# Consent types
# Database types
from canon.db import FK, FKMeta, Vector, VectorMeta
from canon.entities.consent import (
    ConsentScope,
    ConsentStatus,
    ConsentToken,
    ConsentTokenContent,
)
from canon.entities.entity import ContentModel, Entity, register_entity

# Evidence types
from canon.entities.evidence import ChainEntry, ChainEntryContent, Evidence, EvidenceContent

# Shared entities
from canon.entities.shared import (
    Organization,
    OrganizationContent,
    Person,
    PersonContent,
    Session,
    SessionContent,
    Tenant,
    TenantAware,
    TenantContent,
    User,
    UserAware,
    UserContent,
)

__all__ = (
    # Core entity system
    "Entity",
    "ContentModel",
    "register_entity",
    # Database types
    "FK",
    "FKMeta",
    "Vector",
    "VectorMeta",
    # Evidence types
    "Evidence",
    "EvidenceContent",
    "ChainEntry",
    "ChainEntryContent",
    # Shared entities
    "Organization",
    "OrganizationContent",
    "Person",
    "PersonContent",
    "Session",
    "SessionContent",
    "Tenant",
    "TenantAware",
    "TenantContent",
    "User",
    "UserAware",
    "UserContent",
    # Consent types
    "ConsentToken",
    "ConsentTokenContent",
    "ConsentScope",
    "ConsentStatus",
)
