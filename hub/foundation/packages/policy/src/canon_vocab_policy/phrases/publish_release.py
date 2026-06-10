"""Publish a policy release.

Complete vertical slice:
- Transitions release from draft to published
- Freezes the release (no further modifications)
- Optionally signs the release for integrity
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from canon.db import TenantScope, select_one, update
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..exceptions import PolicyReleaseAlreadyPublishedError, PolicyReleaseNotFoundError

__all__ = ["PublishReleaseSpecs", "publish_policy_release"]


class PublishReleaseSpecs(BaseModel):
    """Specs for publish policy release phrase."""

    # inputs
    release_id: UUID | None = None
    version: str | None = None  # Alternative to release_id

    # Optional signing
    sign: bool = False
    signed_by: str | None = None

    # outputs
    bundle_hash: str | None = None
    published_at: datetime | None = None
    signature: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(PublishReleaseSpecs),
    inputs={"release_id", "version", "sign", "signed_by"},
    outputs={"release_id", "version", "bundle_hash", "published_at", "signature"},
)
async def publish_policy_release(
    options: PublishReleaseSpecs,
    ctx: RequestContext,
) -> dict:
    """Publish a policy release.

    Publishing freezes the release - no modifications allowed after.
    Charters can then reference this release by version.

    Args:
        options: Publish options.
        ctx: Request context.

    Returns:
        Dict with release_id, version, bundle_hash, published_at, signature.

    Raises:
        PolicyReleaseNotFoundError: If release doesn't exist.
        PolicyReleaseAlreadyPublishedError: If already published.
    """
    effective_conn = ctx.conn

    # Find release
    if options.release_id:
        release = await select_one(
            "policy_releases",
            where={"id": options.release_id},
            conn=effective_conn,
            tenant_scope=TenantScope.DISABLED,
        )
    elif options.version:
        release = await select_one(
            "policy_releases",
            where={"version": options.version},
            conn=effective_conn,
            tenant_scope=TenantScope.DISABLED,
        )
    else:
        raise ValueError("Either release_id or version must be provided")

    if not release:
        raise PolicyReleaseNotFoundError(
            release_id=options.release_id,
            version=options.version,
        )

    # Check not already published
    if release.get("status") != "draft":
        raise PolicyReleaseAlreadyPublishedError(
            release_id=release["id"],
            version=release.get("version"),
        )

    now = now_utc()

    # Compute signature if requested
    signature = None
    if options.sign:
        # In production, this would use RSA-4096 signing
        # For now, just hash the bundle_hash + timestamp
        sign_data = {
            "bundle_hash": release.get("bundle_hash"),
            "published_at": now.isoformat(),
            "signed_by": options.signed_by or str(ctx.actor_id),
        }
        signature = f"sig:{compute_hash(sign_data)[:32]}"

    # Update status
    update_data: dict = {
        "status": "published",
        "published_at": now,
        "published_by": (options.signed_by or str(ctx.actor_id) if ctx.actor_id else None),
    }
    if signature:
        update_data["signature"] = signature
        update_data["signed_by"] = options.signed_by or str(ctx.actor_id) if ctx.actor_id else None

    await update(
        "policy_releases",
        update_data,
        where={"id": release["id"]},
        conn=effective_conn,
        tenant_scope=TenantScope.DISABLED,
    )

    return {
        "release_id": release["id"],
        "version": release["version"],
        "bundle_hash": release.get("bundle_hash", ""),
        "published_at": now,
        "signature": signature,
    }
