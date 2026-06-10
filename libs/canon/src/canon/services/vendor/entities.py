"""Vendor entities - vendor registry and config versioning.

Vendor = external service provider (OpenAI, Perplexity, Checkr, etc.)
VendorConfig = frozen tool specification for "same tool" compliance
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from canon.types import FK, Entity
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.types import Tenant, User


class Vendor(Entity):
    """External vendor registry (per-tenant).

    Vendor Types:
    - Service: llm, search, scraping, embed, email, sms, storage
    - Compliance: background_check, identity_verification, ai_screening
    """

    _table_name: ClassVar[str] = "vendors"

    tenant_id: FK[Tenant]

    # Identification
    vendor_code: str  # "openai", "anthropic", "perplexity", "checkr"
    vendor_name: str  # "OpenAI", "Anthropic", "Perplexity"
    vendor_type: str  # "llm", "search", "scraping", "background_check"
    description: str | None = None

    # Status
    is_active: bool = True

    # Data handling
    data_types_provided: list[str] | None = None  # ["embeddings", "chat"]
    data_residency: str | None = None  # "us", "eu", "global"

    # FCRA compliance (for CRA vendors)
    is_consumer_reporting_agency: bool | None = None
    fcra_classification_reason: str | None = None

    # Contact
    contact_email: str | None = None
    vendor_website: str | None = None

    @classmethod
    async def get_by_code(
        cls,
        tenant_id: UUID,
        vendor_code: str,
        dsn: str | None = None,
    ) -> Vendor | None:
        """Get vendor by code."""
        results = await cls.select(
            where={"tenant_id": str(tenant_id), "vendor_code": vendor_code},
            dsn=dsn,
        )
        return results[0] if results else None


class VendorConfig(Entity):
    """Frozen tool configuration for "same tool" compliance.

    Each config change creates a new version. The config_hash proves
    we used the exact same tool specification across workflow runs.

    AEDT compliance: bias audits link to specific config versions.
    """

    _table_name: ClassVar[str] = "vendor_configs"

    tenant_id: FK[Tenant]
    vendor_id: FK[Vendor]

    # Versioning
    version: int = 1  # Auto-increment per vendor
    parent_id: UUID | None = None  # Previous version

    # Config identity
    config_hash: str  # SHA-256 of canonical config JSON
    config_data: dict  # Full config for tool instantiation
    service_name: str  # "gpt-4o-mini", "sonar-pro", "checkr-basic"

    # Status
    is_active: bool = True

    # Audit
    change_reason: str | None = None
    changed_by_id: FK[User] | None = None

    @classmethod
    async def get_active(
        cls,
        tenant_id: UUID,
        vendor_code: str,
        service_name: str | None = None,
        dsn: str | None = None,
    ) -> VendorConfig | None:
        """Get active config for a vendor."""
        vendor = await Vendor.get_by_code(tenant_id, vendor_code, dsn=dsn)
        if not vendor:
            return None

        where = {
            "tenant_id": str(tenant_id),
            "vendor_id": str(vendor.id),
            "is_active": True,
        }
        if service_name:
            where["service_name"] = service_name

        results = await cls.select(where=where, dsn=dsn)
        return results[0] if results else None

    @classmethod
    async def create_version(
        cls,
        tenant_id: UUID,
        vendor_id: UUID,
        config_data: dict,
        service_name: str,
        change_reason: str | None = None,
        changed_by_id: UUID | None = None,
        dsn: str | None = None,
    ) -> VendorConfig:
        """Create a new config version (deactivates previous)."""
        # Get current active
        current = await cls.select(
            where={
                "tenant_id": str(tenant_id),
                "vendor_id": str(vendor_id),
                "service_name": service_name,
                "is_active": True,
            },
            dsn=dsn,
        )

        parent_id = None
        new_version = 1

        if current:
            old = current[0]
            parent_id = old.id
            new_version = old.version + 1
            old.is_active = False
            await old.update(dsn=dsn)

        config = cls(
            tenant_id=tenant_id,  # type: ignore[arg-type]
            vendor_id=vendor_id,  # type: ignore[arg-type]
            version=new_version,
            parent_id=parent_id,
            config_hash=compute_hash(config_data),
            config_data=config_data,
            service_name=service_name,
            is_active=True,
            change_reason=change_reason,
            changed_by_id=changed_by_id,  # type: ignore[arg-type]
        )
        await config.save(dsn=dsn)
        return config
