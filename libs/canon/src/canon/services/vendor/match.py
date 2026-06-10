"""Model factory for vendor configs.

For endpoint matching and registration, use canon.utils.endpoints:
    from canon.utils.endpoints import match_endpoint, register_endpoint
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.utils.endpoints import match_endpoint

if TYPE_CHECKING:
    from kron.services import iModel

__all__ = ["create_model"]


def create_model(config_data: dict[str, Any]) -> iModel:
    """Create iModel from vendor config data.

    This is the main entry point for creating LLM/service models
    from stored vendor configs.

    Args:
        config_data: Full config dict from VendorConfig.config_data
            Must contain at least 'provider' key.
            For LLM configs, typically includes: provider, model, endpoint

    Returns:
        iModel instance ready for invoke()

    Example:
        config = await VendorConfig.get_active(tenant_id, "openai", "gpt-4o-mini")
        model = create_model(config.config_data)
        calling = await model.invoke(messages=[{"role": "user", "content": "Hello"}])
        print(calling.response)
    """
    from kron.services import iModel

    # Extract provider and endpoint from config
    provider = config_data.get("provider")
    if not provider:
        raise ValueError("config_data must contain 'provider' key")

    endpoint = config_data.get("endpoint", "chat/completions")

    # Filter out provider/endpoint from kwargs (handled by match_endpoint)
    kwargs = {k: v for k, v in config_data.items() if k not in ("provider", "endpoint")}

    # Match to endpoint and create model
    backend = match_endpoint(provider=provider, endpoint=endpoint, **kwargs)
    return iModel(backend=backend)
