"""Verify request source authentication.

Complete vertical slice:
- Queries request authentication record
- Verifies the source is properly authenticated
- Returns authentication details for audit

Regulatory context:
    - NIST SP 800-63 (Digital Identity Guidelines)
    - SOC 2 CC6.1 (Logical access controls)
    - OAuth 2.0 / OIDC (Token-based authentication)
    - mTLS (Mutual TLS authentication)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "VerifyRequestSourceAuthenticatedSpecs",
    "verify_request_source_authenticated",
]


class VerifyRequestSourceAuthenticatedSpecs(BaseModel):
    """Specs for verify request source authenticated phrase."""

    # inputs
    request_id: UUID
    # outputs
    authenticated: bool | None = None
    source_type: str | None = None
    auth_method: str | None = None
    verified_at: datetime | None = None
    trust_level: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyRequestSourceAuthenticatedSpecs),
    inputs={"request_id"},
    outputs={
        "request_id",
        "authenticated",
        "source_type",
        "auth_method",
        "verified_at",
        "trust_level",
    },
)
async def verify_request_source_authenticated(
    options,
    ctx: RequestContext,
) -> dict:
    """Verify the source of a request is properly authenticated.

    Checks the authentication record for a request to verify:
    - The request has valid authentication credentials
    - The authentication method is appropriate
    - The authentication is not expired

    Regulatory citations:
    - NIST SP 800-63 Section 6: Authentication and lifecycle
    - SOC 2 CC6.1: Entity implements logical access security
    - OAuth 2.0 RFC 6749: Authorization framework
    - RFC 8705: OAuth 2.0 Mutual-TLS

    Args:
        options: Verification options (request_id) - typed frozen dataclass
        ctx: Request context (tenant, actor)

    Returns:
        dict with request_id, authenticated, source_type, auth_method, verified_at, trust_level
    """
    request_id: UUID = options.request_id
    now = now_utc()

    # Query request authentication record
    row = await select_one(
        "request_authentications",
        where={
            "tenant_id": ctx.tenant_id,
            "request_id": request_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        # No authentication record - unauthenticated
        return {
            "request_id": request_id,
            "authenticated": False,
            "source_type": "unknown",
            "auth_method": "none",
            "verified_at": now,
            "trust_level": "untrusted",
        }

    # Extract authentication details
    source_type = row.get("source_type", "unknown")
    auth_method = row.get("auth_method", "unknown")
    verified_at = row.get("verified_at", now)
    expires_at = row.get("expires_at")

    # Check if authentication is expired
    if expires_at and expires_at < now:
        return {
            "request_id": request_id,
            "authenticated": False,
            "source_type": source_type,
            "auth_method": auth_method,
            "verified_at": verified_at,
            "trust_level": "untrusted",
        }

    # Determine trust level based on auth method and source type
    trust_level = _determine_trust_level(source_type, auth_method)

    return {
        "request_id": request_id,
        "authenticated": True,
        "source_type": source_type,
        "auth_method": auth_method,
        "verified_at": verified_at,
        "trust_level": trust_level,
    }


def _determine_trust_level(source_type: str, auth_method: str) -> str:
    """Determine trust level based on source and auth method.

    Trust levels:
    - system: Internal system calls with mTLS
    - elevated: OAuth with strong auth or mTLS
    - standard: OAuth with basic auth
    - untrusted: API key or unknown
    """
    # System-level trust for internal services with mTLS
    if source_type == "system" and auth_method == "mtls":
        return "system"

    # Elevated trust for mTLS or strong OAuth
    if auth_method in ("mtls", "oauth_strong"):
        return "elevated"

    # Standard trust for regular OAuth/session
    if auth_method in ("oauth", "session"):
        return "standard"

    # Untrusted for API keys or unknown methods
    return "untrusted"
