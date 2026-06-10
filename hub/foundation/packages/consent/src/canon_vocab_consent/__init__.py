"""Consent feature - vertical slice for consent management.

This module provides the complete consent domain implementation:
- Types: ConsentToken, ConsentScope, ConsentStatus
- Phrases: grant, revoke, verify, find, list, cascade_revoke
- Constraints: Truth machine constraints for regulatory invariants
- Exceptions: ConsentNotValidError, ConsentExpiredError, etc.
- Service: ConsentService with evidence emission

Usage:
    from canon_vocab_consent import (
        # Types
        ConsentToken,
        ConsentScope,
        ConsentStatus,
        # Phrases
        grant_consent_token,
        verify_consent_token,
        # Constraints
        consent_must_be_valid,
    )
"""

# Exceptions
from .exceptions import ConsentExpiredError, ConsentNotValidError, ConsentWithdrawnError

# Package metadata
from .package import CONSENT

# Phrases (includes CRUD phrases, requirement phrases, and truth machine constraints)
from .phrases import (  # Specs classes; Domain types; Phrase functions; Truth machine constraints
    CascadeRevokeSpecs,
    ConsentStatusFilter,
    FindConsentSpecs,
    GrantConsentSpecs,
    ListConsentSpecs,
    RequireActiveConsentSpecs,
    RequireValidConsentSpecs,
    RevokeConsentSpecs,
    VerifyConsentSpecs,
    cascade_revoke_consent_token,
    consent_must_be_valid,
    consent_must_not_be_expired,
    consent_must_not_be_withdrawn,
    consent_scope_must_cover,
    find_consent_token,
    grant_consent_token,
    list_consent_tokens,
    require_active_consent,
    require_valid_consent,
    revoke_consent_token,
    verify_consent_token,
)

# Service
from .service import ConsentService

# Types
from .types import ConsentScope, ConsentStatus, ConsentToken, ConsentTokenContent

__all__ = [
    # Package metadata
    "CONSENT",
    # Specs classes
    "CascadeRevokeSpecs",
    "FindConsentSpecs",
    "GrantConsentSpecs",
    "ListConsentSpecs",
    "RequireActiveConsentSpecs",
    "RequireValidConsentSpecs",
    "RevokeConsentSpecs",
    "VerifyConsentSpecs",
    # Domain types
    "ConsentScope",
    "ConsentStatus",
    "ConsentStatusFilter",
    "ConsentToken",
    "ConsentTokenContent",
    # Exceptions
    "ConsentExpiredError",
    "ConsentNotValidError",
    "ConsentWithdrawnError",
    # Service
    "ConsentService",
    # Phrase functions
    "cascade_revoke_consent_token",
    "find_consent_token",
    "grant_consent_token",
    "list_consent_tokens",
    "require_active_consent",
    "require_valid_consent",
    "revoke_consent_token",
    "verify_consent_token",
    # Truth machine constraints
    "consent_must_be_valid",
    "consent_must_not_be_expired",
    "consent_must_not_be_withdrawn",
    "consent_scope_must_cover",
]
