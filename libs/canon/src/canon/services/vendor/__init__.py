"""Vendor service - vendor registry and config versioning.

Usage:
    from hub.services.vendor import VendorService, Vendor, VendorConfig

    # Create service with tenant context
    service = VendorService(tenant_id=tenant_id)

    # Register vendor via request dispatch
    response = await service.request({
        "action": "register",
        "options": {
            "vendor_code": "openai",
            "vendor_name": "OpenAI",
            "vendor_type": "llm",
        }
    })

    # Set config (creates versioned config for "same tool" compliance)
    response = await service.request({
        "action": "set_config",
        "options": {
            "vendor_code": "openai",
            "service_name": "gpt-4o-mini",
            "config_data": {"provider": "openrouter", "model": "openai/gpt-4o-mini"},
            "change_reason": "Initial setup",
        }
    })

For endpoint matching, use canon.utils.endpoints:
    from canon.utils.endpoints import match_endpoint, register_endpoint
"""

from .entities import Vendor, VendorConfig
from .match import create_model
from .service import (
    GetConfigHistoryOptions,
    GetConfigOptions,
    GetOptions,
    ListOptions,
    RegisterOptions,
    SetConfigOptions,
    VendorAction,
    VendorRequest,
    VendorService,
)

__all__ = [
    # Entities
    "Vendor",
    "VendorConfig",
    # Service
    "VendorService",
    "VendorRequest",
    "VendorAction",
    # Options
    "GetConfigHistoryOptions",
    "GetConfigOptions",
    "GetOptions",
    "ListOptions",
    "RegisterOptions",
    "SetConfigOptions",
    # Model factory
    "create_model",
]
