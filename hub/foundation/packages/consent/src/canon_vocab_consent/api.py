"""Consent API - FastAPI router for consent operations.

Uses ConsentToken entity for state, Evidence for audit trail.
All endpoints use RequestContext for proper provenance.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from canon.config import get_settings
from canon.enforcement import RequestContext
from canon.enforcement.types import ServiceContext
from kron.utils import now_utc

from .schema import (
    ConsentLinkInfo,
    ConsentLinkResponse,
    ConsentListResponse,
    ConsentRecord,
    ConsentVerification,
)
from .service import ConsentService
from .types import ConsentToken

if TYPE_CHECKING:
    from fastapi import Request

    from .schema import (
        CreateConsentLinkRequest,
        GrantConsentRequest,
        RevokeConsentRequest,
        SubmitConsentLinkRequest,
    )
    from .types import ConsentScope

router = APIRouter(prefix="/consent", tags=["consent"])

# Token expiry for consent links (7 days default)
CONSENT_LINK_EXPIRY_DAYS = 7


# =============================================================================
# Dependencies
# =============================================================================


async def get_tenant_id() -> UUID:
    """Get tenant ID from request context.

    In production, this would extract from JWT or session.
    """
    raise NotImplementedError(
        "get_tenant_id is not yet implemented. "
        "Requires tenant extraction from JWT claims or session context. "
        "All consent operations require tenant isolation "
        "(FCRA 1681b(b), GDPR Art. 6-7)."
    )


async def get_current_user_id() -> UUID | None:
    """Get current user ID from request context."""
    raise NotImplementedError(
        "get_current_user_id is not yet implemented. "
        "Requires user identity extraction from JWT claims or session context. "
        "Actor provenance is required for all consent audit trails "
        "(SOX 302/404, GDPR Art. 5(1)(f))."
    )


def get_service_context(tenant_id: UUID = Depends(get_tenant_id)) -> ServiceContext:
    """Get ServiceContext for consent service."""
    return ServiceContext(tenant_id=tenant_id, service_name="consent")


def get_consent_service(
    svc_ctx: ServiceContext = Depends(get_service_context),
) -> ConsentService:
    """Get consent service with ServiceContext."""
    return ConsentService(svc_ctx)


def get_request_context(
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: UUID | None = Depends(get_current_user_id),
) -> RequestContext:
    """Build RequestContext for the request."""
    return RequestContext(
        tenant_id=tenant_id,
        actor_id=user_id,
        timestamp=now_utc(),
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/grant", status_code=status.HTTP_201_CREATED)
async def grant_consent(
    request: GrantConsentRequest,
    service: ConsentService = Depends(get_consent_service),
    ctx: RequestContext = Depends(get_request_context),
) -> dict:
    """Grant consent for a person.

    Creates ConsentToken entity, emits Evidence for audit.
    Idempotent: returns existing token if already granted.
    """
    response = await service.request(
        payload={
            "action": "grant",
            "options": {
                "person_id": str(request.person_id),
                "scope": request.scope.value,
                "version": request.version,
                "ip_address": request.ip_address,
                "user_agent": request.user_agent,
                "collected_by_id": str(ctx.actor_id) if ctx.actor_id else None,
            },
        },
        ctx=ctx,
    )

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.error or "Failed to grant consent",
        )

    return response.data or {}


@router.get("/verify")
async def verify_consent(
    person_id: UUID = Query(..., description="Person to verify consent for"),
    scope: ConsentScope = Query(..., description="Consent scope to verify"),
    service: ConsentService = Depends(get_consent_service),
    ctx: RequestContext = Depends(get_request_context),
) -> ConsentVerification:
    """Verify consent exists and is valid.

    Hot path for gate checks.
    """
    response = await service.request(
        payload={
            "action": "verify",
            "options": {
                "person_id": str(person_id),
                "scope": scope.value,
            },
        },
        ctx=ctx,
    )

    if response.success and response.data:
        return ConsentVerification.model_validate(response.data)
    return ConsentVerification(has_consent=False)


@router.post("/revoke")
async def revoke_consent(
    request: RevokeConsentRequest,
    service: ConsentService = Depends(get_consent_service),
    ctx: RequestContext = Depends(get_request_context),
) -> dict:
    """Revoke consent with cascade support.

    CASCADE: If revoking primary consent (CONSIDERATION_AUTHORIZATION),
    all other consents for this person are also revoked.
    """
    response = await service.request(
        payload={
            "action": "revoke",
            "options": {
                "person_id": str(request.person_id),
                "scope": request.scope.value,
                "reason": request.reason,
            },
        },
        ctx=ctx,
    )

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.error or "Failed to revoke consent",
        )

    data = response.data or {}
    if not data.get("revoked_token_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active consent found for scope: {request.scope.value}",
        )

    return data


@router.get("/")
async def list_consents(
    person_id: UUID = Query(..., description="Person to list consents for"),
    include_revoked: bool = Query(False, description="Include revoked consents"),
    service: ConsentService = Depends(get_consent_service),
    ctx: RequestContext = Depends(get_request_context),
) -> ConsentListResponse:
    """List all consent tokens for a person."""
    response = await service.request(
        payload={
            "action": "list",
            "options": {
                "person_id": str(person_id),
                "include_revoked": include_revoked,
            },
        },
        ctx=ctx,
    )

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=response.error or "Failed to list consents",
        )

    data = response.data or {}
    consents = []
    for t in data.get("tokens", []):
        consents.append(
            ConsentRecord(
                token_id=UUID(t["token_id"]),
                person_id=person_id,
                scope=t["scope"],
                status=t["status"],
                version=t.get("version"),
                granted_at=t.get("granted_at"),
                granted_by_id=(UUID(t["granted_by_id"]) if t.get("granted_by_id") else None),
                revoked_at=t.get("revoked_at"),
                revoked_by_id=(UUID(t["revoked_by_id"]) if t.get("revoked_by_id") else None),
                revocation_reason=t.get("revocation_reason"),
                expires_at=t.get("expires_at"),
            )
        )

    return ConsentListResponse(consents=consents, total=data.get("total", len(consents)))


@router.get("/{token_id}")
async def get_consent(
    token_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
) -> ConsentRecord:
    """Get a specific consent token by ID."""
    tokens = await ConsentToken.select(
        where={
            "id": str(token_id),
            "tenant_id": str(tenant_id),
        }
    )

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Consent token not found: {token_id}",
        )

    t = tokens[0]
    return ConsentRecord(
        token_id=t.id,
        person_id=t.subject_id,  # type: ignore[arg-type]
        scope=t.scope,
        status=t.status.value,
        version=t.version,
        granted_at=t.granted_at.isoformat() if t.granted_at else None,
        granted_by_id=t.granted_by_id,  # type: ignore[arg-type]
        revoked_at=t.revoked_at.isoformat() if t.revoked_at else None,
        revoked_by_id=t.revoked_by_id,  # type: ignore[arg-type]
        revocation_reason=t.revocation_reason,
        expires_at=t.expires_at.isoformat() if t.expires_at else None,
    )


# =============================================================================
# One-Time Link Endpoints
# =============================================================================


def _get_jwt_secret() -> str:
    """Get JWT secret for signing consent tokens."""
    settings = get_settings()
    if settings.secret_key:
        return settings.secret_key.get_secret_value()
    return "dev-secret-change-in-production"


def _generate_consent_token(
    tenant_id: UUID,
    person_id: UUID,
    scopes: list[ConsentScope],
    expiry_days: int,
    job_title: str | None = None,
    company_name: str | None = None,
) -> tuple[str, str]:
    """Generate a signed JWT token for consent link."""
    now = now_utc()
    expires_at = now + timedelta(days=expiry_days)

    payload = {
        "tenant_id": str(tenant_id),
        "person_id": str(person_id),
        "scopes": [s.value for s in scopes],
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    if job_title:
        payload["job_title"] = job_title
    if company_name:
        payload["company_name"] = company_name

    token = jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")
    return token, expires_at.isoformat()


def _decode_consent_token(token: str) -> dict | None:
    """Decode and validate a consent token."""
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def _is_link_used(jti: str, tenant_id: str) -> bool:
    """Check if a consent link has been used by looking for ConsentToken with matching jti in metadata."""
    # Check if any consent token has this jti in its metadata
    # This is stored when the link is used
    tokens = await ConsentToken.select(where={"tenant_id": tenant_id})
    for t in tokens:
        if t.metadata and t.metadata.extra and t.metadata.extra.get("link_jti") == jti:
            return True
    return False


@router.post("/link", status_code=status.HTTP_201_CREATED)
async def create_consent_link(
    request: CreateConsentLinkRequest,
    req: Request,
    tenant_id: UUID = Depends(get_tenant_id),
) -> ConsentLinkResponse:
    """Create a one-time consent link for a candidate."""
    token, expires_at = _generate_consent_token(
        tenant_id=tenant_id,
        person_id=request.person_id,
        scopes=request.scopes,
        expiry_days=request.expiry_days,
        job_title=request.job_title,
        company_name=request.company_name,
    )

    base_url = str(req.base_url).rstrip("/")
    link = f"{base_url}/consent/link/{token}"

    # Evidence for link creation is emitted by service hooks

    return ConsentLinkResponse(
        token=token,
        link=link,
        expires_at=expires_at,
        scopes=[s.value for s in request.scopes],
    )


@router.get("/link/{token}")
async def get_consent_link_info(token: str) -> ConsentLinkInfo:
    """Get info about a consent link (no auth required)."""
    payload = _decode_consent_token(token)

    if not payload:
        return ConsentLinkInfo(
            valid=False,
            scopes=[],
            error="Link is invalid or has expired",
        )

    jti = payload.get("jti", "")
    tenant_id = payload.get("tenant_id", "")

    if await _is_link_used(jti, tenant_id):
        return ConsentLinkInfo(
            valid=False,
            scopes=[],
            error="This consent link has already been used",
        )

    return ConsentLinkInfo(
        valid=True,
        scopes=payload.get("scopes", []),
        job_title=payload.get("job_title"),
        company_name=payload.get("company_name"),
        expires_at=datetime.fromtimestamp(payload.get("exp", 0), tz=UTC).isoformat(),
    )


@router.post("/link/{token}")
async def submit_consent_link(
    token: str,
    request: Request,
    _body: SubmitConsentLinkRequest,
    user_agent: str | None = Header(None),
) -> dict:
    """Submit consent via one-time link (no auth required).

    Creates ConsentToken for each scope. Link is invalidated via jti tracking.
    """
    payload = _decode_consent_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link is invalid or has expired",
        )

    jti = payload.get("jti", "")
    tenant_id_str = payload.get("tenant_id", "")
    person_id_str = payload.get("person_id", "")
    scopes = payload.get("scopes", [])

    if await _is_link_used(jti, tenant_id_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This consent link has already been used",
        )

    ip_address = request.client.host if request.client else None
    tenant_id = UUID(tenant_id_str)
    person_id = UUID(person_id_str)

    # Create service and context
    svc_ctx = ServiceContext(tenant_id=tenant_id, service_name="consent")
    service = ConsentService(svc_ctx)
    ctx = RequestContext(
        tenant_id=tenant_id,
        subject_id=person_id,
        timestamp=now_utc(),
    )

    token_ids = []
    first_grant = True

    for scope_value in scopes:
        response = await service.request(
            payload={
                "action": "grant",
                "options": {
                    "person_id": str(person_id),
                    "scope": scope_value,
                    "version": "1.0",
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                },
            },
            ctx=ctx,
        )

        if response.success and response.data:
            token_id = response.data.get("token_id")
            if token_id:
                token_ids.append(token_id)

                # Store jti in first token's metadata to mark link as used
                if first_grant:
                    tokens = await ConsentToken.select(
                        where={"id": token_id, "tenant_id": str(tenant_id)}
                    )
                    if tokens:
                        t = tokens[0]
                        if t.metadata:
                            t.metadata.extra = t.metadata.extra or {}
                            t.metadata.extra["link_jti"] = jti
                            await t.save()
                    first_grant = False

                # Evidence is emitted by service hooks

    return {
        "success": True,
        "message": "Consent granted successfully",
        "token_ids": token_ids,
        "scopes": scopes,
    }
