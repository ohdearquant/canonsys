"""Tenant entity and TenantAware mixin."""

from __future__ import annotations

from kron.types import FK

from ..entity import ContentModel, Entity, register_entity
from .organization import Organization

__all__ = (
    "Tenant",
    "TenantAware",
    "TenantContent",
)


class TenantContent(ContentModel):
    """A tenant (isolated workspace/account).

    Each tenant is an isolated environment with its own data.
    Typically represents a company or division using the platform.
    Row-Level Security enforces isolation at the database level.
    """

    name: str
    slug: str
    """URL-friendly unique identifier (used in RLS policies)."""

    organization_id: FK[Organization] | None = None
    status: str = "active"  # active, suspended
    settings: dict | None = None


@register_entity("tenants")
class Tenant(Entity):
    """Entity representing a tenant."""

    content: TenantContent


class TenantAware(ContentModel):
    """Mixin for content models scoped to a single tenant.

    All tenant-scoped entities must inherit this. RLS policies
    use tenant_id to enforce data isolation.
    """

    tenant_id: FK[Tenant]
