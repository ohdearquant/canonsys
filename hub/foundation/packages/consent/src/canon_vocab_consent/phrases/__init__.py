"""Consent domain phrases.

All consent operations in one place:
- CRUD phrases: grant, revoke, verify, find, list, cascade_revoke, renew
- Requirement phrases: require_active_consent, require_valid_consent, require_not_expired, require_not_withdrawn
- Query phrases: get_consent_history
- Verification phrases: verify_consent_scope_covers
- Truth machine constraints: consent_must_be_valid, etc.
"""

from .cascade_revoke_token import CascadeRevokeSpecs, cascade_revoke_consent_token
from .constraints import (
    consent_must_be_valid,
    consent_must_not_be_expired,
    consent_must_not_be_withdrawn,
    consent_scope_must_cover,
)
from .find_token import FindConsentSpecs, find_consent_token
from .get_history import (
    ConsentHistoryEntry,
    GetConsentHistorySpecs,
    get_consent_history,
)
from .grant_token import GrantConsentSpecs, grant_consent_token
from .list_tokens import ConsentStatusFilter, ListConsentSpecs, list_consent_tokens
from .renew_token import RenewConsentSpecs, renew_consent_token
from .require_active_consent import RequireActiveConsentSpecs, require_active_consent
from .require_not_expired import (
    RequireConsentNotExpiredSpecs,
    require_consent_not_expired,
)
from .require_not_withdrawn import (
    RequireConsentNotWithdrawnSpecs,
    require_consent_not_withdrawn,
)
from .require_valid_consent import RequireValidConsentSpecs, require_valid_consent
from .revoke_token import RevokeConsentSpecs, revoke_consent_token
from .verify_scope_covers import (
    VerifyConsentScopeCoversSpecs,
    verify_consent_scope_covers,
)
from .verify_token import VerifyConsentSpecs, verify_consent_token

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "CascadeRevokeSpecs",
    "FindConsentSpecs",
    "GetConsentHistorySpecs",
    "GrantConsentSpecs",
    "ListConsentSpecs",
    "RenewConsentSpecs",
    "RequireActiveConsentSpecs",
    "RequireConsentNotExpiredSpecs",
    "RequireConsentNotWithdrawnSpecs",
    "RequireValidConsentSpecs",
    "RevokeConsentSpecs",
    "VerifyConsentScopeCoversSpecs",
    "VerifyConsentSpecs",
    # Domain types
    "ConsentHistoryEntry",
    "ConsentStatusFilter",
    # Phrase functions
    "cascade_revoke_consent_token",
    "find_consent_token",
    "get_consent_history",
    "grant_consent_token",
    "list_consent_tokens",
    "renew_consent_token",
    "require_active_consent",
    "require_consent_not_expired",
    "require_consent_not_withdrawn",
    "require_valid_consent",
    "revoke_consent_token",
    "verify_consent_scope_covers",
    "verify_consent_token",
    # Truth machine constraints
    "consent_must_be_valid",
    "consent_must_not_be_expired",
    "consent_must_not_be_withdrawn",
    "consent_scope_must_cover",
]
