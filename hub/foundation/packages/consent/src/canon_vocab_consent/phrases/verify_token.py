"""Verify consent for processing scope.

Complete vertical slice:
- Queries for active consent token
- Checks not expired
- Returns binary verification result

Regulatory basis: FCRA Section 1681b(b)(3)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person
from kron.specs import CrudPattern, Operable
from kron.types import FK
from kron.utils import now_utc

from ..types import ConsentScope, ConsentToken

__all__ = ["VerifyConsentSpecs", "verify_consent_token"]


class VerifyConsentSpecs(BaseModel):
    """Specs for verify consent phrase."""

    # inputs
    subject_id: FK[Person]
    scope: ConsentScope
    # outputs
    has_consent: bool = False
    reason: str | None = None
    token_id: FK[ConsentToken] | None = None
    granted_at: datetime | None = None


def _parse_verify_consent(row: dict | None) -> dict:
    """Check row exists, status is active, not expired."""
    if row is None:
        return {
            "has_consent": False,
            "reason": "No active consent token found",
            "token_id": None,
            "granted_at": None,
        }

    # Check expiration
    expires_at = row.get("expires_at")
    if expires_at and expires_at < now_utc():
        return {
            "has_consent": False,
            "reason": "Consent token has expired",
            "token_id": row.get("id"),
            "granted_at": None,
        }

    return {
        "has_consent": True,
        "reason": None,
        "token_id": row.get("id"),
        "granted_at": row.get("granted_at"),
    }


verify_consent_token = canon_phrase(
    Operable.from_structure(VerifyConsentSpecs),
    inputs={"subject_id", "scope"},
    outputs={"has_consent", "subject_id", "scope", "reason", "token_id", "granted_at"},
    crud=CrudPattern(
        table="consent_tokens",
        operation="read",
        lookup={"subject_id", "scope", "status"},
        defaults={"status": "active"},
    ),
    result_parser=_parse_verify_consent,
    name="verify_consent_token",
)
"""Verify consent exists for subject and scope.

Regulatory basis: FCRA Section 1681b(b)(3)
"""
