"""Vendor service - registration and config management.

VendorService handles:
- Vendor registration
- Config versioning (for "same tool" compliance)
- Config retrieval

Does NOT handle workflow execution - that's WorkflowService.

Uses BaseService pattern for uniform dispatch and automatic evidence tracking.
"""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from canon.service import Action, BaseService, RequestModel, ResponseModel

from .entities import Vendor, VendorConfig

# Action Enum


class VendorAction(Action):
    """Actions available on the vendor service."""

    REGISTER = "register"
    GET = "get"
    LIST = "list"
    SET_CONFIG = "set_config"
    GET_CONFIG = "get_config"
    GET_CONFIG_HISTORY = "get_config_history"

    @classmethod
    def action_option_map(cls) -> dict[Action, type[BaseModel]]:
        """Map actions to their option models."""
        return {
            cls.REGISTER: RegisterOptions,
            cls.GET: GetOptions,
            cls.LIST: ListOptions,
            cls.SET_CONFIG: SetConfigOptions,
            cls.GET_CONFIG: GetConfigOptions,
            cls.GET_CONFIG_HISTORY: GetConfigHistoryOptions,
        }


# Option Models


class RegisterOptions(BaseModel):
    """Options for registering a new vendor."""

    vendor_code: str = Field(..., description="Unique vendor code (e.g., 'openai')")
    vendor_name: str = Field(..., description="Human-readable name (e.g., 'OpenAI')")
    vendor_type: str = Field(..., description="Vendor type (e.g., 'llm', 'search')")
    description: str | None = Field(default=None, description="Optional description")
    data_types_provided: list[str] | None = Field(
        default=None, description="Types of data provided"
    )
    is_consumer_reporting_agency: bool | None = Field(
        default=None, description="FCRA CRA classification"
    )


class GetOptions(BaseModel):
    """Options for getting a vendor by code."""

    vendor_code: str = Field(..., description="Vendor code to look up")


class ListOptions(BaseModel):
    """Options for listing vendors."""

    vendor_type: str | None = Field(default=None, description="Filter by vendor type")
    active_only: bool = Field(default=True, description="Only include active vendors")


class SetConfigOptions(BaseModel):
    """Options for setting vendor config (creates new version)."""

    vendor_code: str = Field(..., description="Vendor code")
    service_name: str = Field(..., description="Service name (e.g., 'gpt-4o-mini')")
    config_data: dict = Field(..., description="Full config for tool instantiation")
    change_reason: str | None = Field(default=None, description="Reason for change")
    changed_by_id: UUID | None = Field(default=None, description="User making the change")


class GetConfigOptions(BaseModel):
    """Options for getting active vendor config."""

    vendor_code: str = Field(..., description="Vendor code")
    service_name: str | None = Field(default=None, description="Optional service filter")


class GetConfigHistoryOptions(BaseModel):
    """Options for getting config version history."""

    vendor_code: str = Field(..., description="Vendor code")
    service_name: str | None = Field(default=None, description="Optional service filter")
    limit: int = Field(default=10, description="Max versions to return")


# Request Model


class VendorRequest(RequestModel):
    """Request model for vendor service operations."""

    action_class: ClassVar[type[Action]] = VendorAction

    action: VendorAction | None = Field(default=None, description="Action to perform")


# Service Implementation


class VendorService(BaseService[VendorRequest]):
    """Service for vendor operations.

    Extends BaseService for uniform dispatch and automatic evidence tracking.
    Compliance-affecting actions (register, set_config) emit ChainEntry.
    """

    request_class: ClassVar[type[RequestModel]] = VendorRequest
    _service_name: ClassVar[str] = "vendor"

    # Action Handlers

    async def _handle_register(self, req: VendorRequest) -> ResponseModel:
        """Register a new vendor."""
        opts = self._options_as(req, RegisterOptions)

        # Check if vendor already exists
        existing = await Vendor.get_by_code(self.tenant_id, opts.vendor_code)
        if existing:
            return ResponseModel.ok(
                {
                    "vendor_id": str(existing.id),
                    "vendor_code": existing.vendor_code,
                    "already_exists": True,
                }
            )

        # Create vendor
        vendor = Vendor(
            tenant_id=self.tenant_id,  # type: ignore[arg-type]
            vendor_code=opts.vendor_code,
            vendor_name=opts.vendor_name,
            vendor_type=opts.vendor_type,
            description=opts.description,
            data_types_provided=opts.data_types_provided,
            is_consumer_reporting_agency=opts.is_consumer_reporting_agency,
        )
        await vendor.save()

        # Emit chained evidence for compliance tracking
        await self.emit_chained_evidence(
            operation="registered",
            data={
                "vendor_id": str(vendor.id),
                "vendor_code": opts.vendor_code,
                "vendor_type": opts.vendor_type,
            },
            title=f"Vendor registered: {opts.vendor_code}",
            chain_event_type="vendor.registered",
        )

        return ResponseModel.ok(
            {
                "vendor_id": str(vendor.id),
                "vendor_code": vendor.vendor_code,
                "already_exists": False,
            }
        )

    async def _handle_get(self, req: VendorRequest) -> ResponseModel:
        """Get vendor by code."""
        opts = self._options_as(req, GetOptions)

        vendor = await Vendor.get_by_code(self.tenant_id, opts.vendor_code)
        if not vendor:
            return ResponseModel.ok({"vendor": None})

        return ResponseModel.ok(
            {
                "vendor": {
                    "id": str(vendor.id),
                    "vendor_code": vendor.vendor_code,
                    "vendor_name": vendor.vendor_name,
                    "vendor_type": vendor.vendor_type,
                    "description": vendor.description,
                    "is_active": vendor.is_active,
                    "data_types_provided": vendor.data_types_provided,
                    "is_consumer_reporting_agency": vendor.is_consumer_reporting_agency,
                }
            }
        )

    async def _handle_list(self, req: VendorRequest) -> ResponseModel:
        """List vendors for tenant."""
        opts = self._options_as(req, ListOptions)

        where: dict[str, Any] = {"tenant_id": str(self.tenant_id)}
        if opts.vendor_type:
            where["vendor_type"] = opts.vendor_type
        if opts.active_only:
            where["is_active"] = True

        vendors = await Vendor.select(where=where)

        return ResponseModel.ok(
            {
                "vendors": [
                    {
                        "id": str(v.id),
                        "vendor_code": v.vendor_code,
                        "vendor_name": v.vendor_name,
                        "vendor_type": v.vendor_type,
                        "is_active": v.is_active,
                    }
                    for v in vendors
                ],
                "count": len(vendors),
            }
        )

    async def _handle_set_config(self, req: VendorRequest) -> ResponseModel:
        """Set config for a vendor service (creates new version)."""
        opts = self._options_as(req, SetConfigOptions)

        vendor = await Vendor.get_by_code(self.tenant_id, opts.vendor_code)
        if not vendor:
            return ResponseModel.fail(f"Vendor not found: {opts.vendor_code}")

        config = await VendorConfig.create_version(
            tenant_id=self.tenant_id,
            vendor_id=vendor.id,
            config_data=opts.config_data,
            service_name=opts.service_name,
            change_reason=opts.change_reason,
            changed_by_id=opts.changed_by_id,
        )

        # Emit chained evidence for compliance tracking
        await self.emit_chained_evidence(
            operation="config_updated",
            data={
                "config_id": str(config.id),
                "vendor_code": opts.vendor_code,
                "service_name": opts.service_name,
                "version": config.version,
                "config_hash": config.config_hash,
            },
            title=f"Vendor config updated: {opts.vendor_code}/{opts.service_name} v{config.version}",
            chain_event_type="vendor.config_updated",
        )

        return ResponseModel.ok(
            {
                "config_id": str(config.id),
                "vendor_code": opts.vendor_code,
                "service_name": config.service_name,
                "version": config.version,
                "config_hash": config.config_hash,
            }
        )

    async def _handle_get_config(self, req: VendorRequest) -> ResponseModel:
        """Get active config for a vendor."""
        opts = self._options_as(req, GetConfigOptions)

        config = await VendorConfig.get_active(self.tenant_id, opts.vendor_code, opts.service_name)

        if not config:
            return ResponseModel.ok({"config": None})

        return ResponseModel.ok(
            {
                "config": {
                    "id": str(config.id),
                    "vendor_id": str(config.vendor_id),
                    "service_name": config.service_name,
                    "version": config.version,
                    "config_hash": config.config_hash,
                    "config_data": config.config_data,
                    "is_active": config.is_active,
                }
            }
        )

    async def _handle_get_config_history(self, req: VendorRequest) -> ResponseModel:
        """Get config version history."""
        opts = self._options_as(req, GetConfigHistoryOptions)

        vendor = await Vendor.get_by_code(self.tenant_id, opts.vendor_code)
        if not vendor:
            return ResponseModel.ok({"configs": [], "count": 0})

        where: dict[str, Any] = {
            "tenant_id": str(self.tenant_id),
            "vendor_id": str(vendor.id),
        }
        if opts.service_name:
            where["service_name"] = opts.service_name

        configs = await VendorConfig.select(
            where=where,
            order_by="version DESC",
            limit=opts.limit,
        )

        return ResponseModel.ok(
            {
                "configs": [
                    {
                        "id": str(c.id),
                        "version": c.version,
                        "service_name": c.service_name,
                        "config_hash": c.config_hash,
                        "is_active": c.is_active,
                        "change_reason": c.change_reason,
                    }
                    for c in configs
                ],
                "count": len(configs),
            }
        )
