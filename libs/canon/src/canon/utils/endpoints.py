from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from kron.services import Endpoint

__all__ = [
    "LIONPRIDE_PROVIDERS",
    "EndpointRegistry",
    "get_endpoint_class",
    "is_supported_provider",
    "list_all_providers",
    "list_registered_endpoints",
    "match_endpoint",
    "register_endpoint",
]

T = TypeVar("T", bound="Endpoint")

# Global endpoint registry: {(provider, endpoint): endpoint_class}
_ENDPOINT_REGISTRY: dict[tuple[str, str], type[Endpoint]] = {}

# Native lionpride providers (from lionpride.services.providers.match)
LIONPRIDE_PROVIDERS: dict[str, list[str]] = {
    "anthropic": ["messages", "chat/completions"],
    "openai": ["chat/completions"],
    "groq": ["chat/completions"],
    "openrouter": ["chat/completions"],
    "nvidia_nim": ["chat/completions"],
    "claude_code": ["query_cli"],
    "gemini_code": ["query_cli"],
}


class EndpointRegistry:
    """Registry for endpoint classes.

    Stores registered endpoint classes keyed by (provider, endpoint) tuples.
    Supports both decorator-based and manual registration.
    """

    @staticmethod
    def register(
        provider: str,
        endpoint: str = "default",
        *,
        override: bool = False,
    ) -> type[Endpoint]:
        """Register an endpoint class.

        Args:
            provider: Provider name (e.g., "openai", "aws", "apify")
            endpoint: Endpoint type (e.g., "chat/completions", "embeddings", "s3")
            override: Allow overriding existing registration

        Returns:
            The registered class (for use as decorator)

        Raises:
            ValueError: If endpoint already registered and override=False
        """

        def decorator(cls: type[T]) -> type[T]:
            key = (provider.lower(), endpoint.lower())

            if key in _ENDPOINT_REGISTRY and not override:
                existing = _ENDPOINT_REGISTRY[key]
                raise ValueError(
                    f"Endpoint already registered for {provider}/{endpoint}: "
                    f"{existing.__name__}. Use override=True to replace."
                )

            _ENDPOINT_REGISTRY[key] = cls
            return cls

        return decorator

    @staticmethod
    def get(provider: str, endpoint: str = "default") -> type[Endpoint] | None:
        """Get registered endpoint class.

        Args:
            provider: Provider name
            endpoint: Endpoint type

        Returns:
            Endpoint class if registered, None otherwise
        """
        key = (provider.lower(), endpoint.lower())
        return _ENDPOINT_REGISTRY.get(key)

    @staticmethod
    def list_all() -> list[tuple[str, str, type[Endpoint]]]:
        """List all registered endpoints.

        Returns:
            List of (provider, endpoint, class) tuples
        """
        return [(p, e, cls) for (p, e), cls in _ENDPOINT_REGISTRY.items()]

    @staticmethod
    def clear() -> None:
        """Clear all registrations (for testing)."""
        _ENDPOINT_REGISTRY.clear()


def register_endpoint(
    provider: str,
    endpoint: str = "default",
    *,
    override: bool = False,
) -> type[Endpoint]:
    """Decorator to register an endpoint class.

    Args:
        provider: Provider name (e.g., "openai", "aws", "apify")
        endpoint: Endpoint type (e.g., "chat/completions", "embeddings", "s3")
        override: Allow overriding existing registration

    Returns:
        Decorator that registers the class

    Example:
        @register_endpoint(provider="openai", endpoint="embeddings")
        class OpenAIEmbedEndpoint(Endpoint):
            ...

        @register_endpoint(provider="aws", endpoint="s3")
        class S3Endpoint(Endpoint):
            ...
    """
    return EndpointRegistry.register(provider, endpoint, override=override)


def get_endpoint_class(
    provider: str,
    endpoint: str = "default",
) -> type[Endpoint] | None:
    """Get registered endpoint class.

    Args:
        provider: Provider name
        endpoint: Endpoint type

    Returns:
        Endpoint class if registered, None otherwise
    """
    return EndpointRegistry.get(provider, endpoint)


def list_registered_endpoints(
    include_lionpride: bool = False,
) -> list[tuple[str, str, type[Endpoint] | str]]:
    """List all registered endpoints.

    Args:
        include_lionpride: If True, also list native lionpride providers

    Returns:
        List of (provider, endpoint, class_or_name) tuples.
        For lionpride providers, class_or_name is a string like "lionpride:AnthropicMessagesEndpoint"
    """
    result: list[tuple[str, str, type[Endpoint] | str]] = EndpointRegistry.list_all()

    if include_lionpride:
        for provider, endpoints in LIONPRIDE_PROVIDERS.items():
            for ep in endpoints:
                # Map to lionpride class names
                if provider == "anthropic":
                    cls_name = "lionpride:AnthropicMessagesEndpoint"
                elif provider == "claude_code":
                    cls_name = "lionpride:ClaudeCodeEndpoint"
                elif provider == "gemini_code":
                    cls_name = "lionpride:GeminiCodeEndpoint"
                else:
                    cls_name = "lionpride:OAIChatEndpoint"
                result.append((provider, ep, cls_name))

    return result


def list_all_providers() -> dict[str, list[str]]:
    """List all supported providers and their endpoints.

    Returns:
        Dict mapping provider names to list of supported endpoints.
        Includes both custom registered and lionpride native providers.
    """
    providers: dict[str, list[str]] = {}

    # Add custom registered
    for provider, endpoint, _ in EndpointRegistry.list_all():
        if provider not in providers:
            providers[provider] = []
        providers[provider].append(endpoint)

    # Add lionpride native
    for provider, endpoints in LIONPRIDE_PROVIDERS.items():
        if provider not in providers:
            providers[provider] = []
        for ep in endpoints:
            if ep not in providers[provider]:
                providers[provider].append(ep)

    return providers


def is_supported_provider(provider: str, endpoint: str = "chat/completions") -> bool:
    """Check if a provider/endpoint combination is supported.

    Args:
        provider: Provider name
        endpoint: Endpoint type

    Returns:
        True if supported (custom or lionpride native), False otherwise
    """
    # Check custom registry
    if get_endpoint_class(provider, endpoint) is not None:
        return True

    # Check lionpride native
    provider_lower = provider.lower()
    if provider_lower in LIONPRIDE_PROVIDERS:
        return endpoint.lower() in [e.lower() for e in LIONPRIDE_PROVIDERS[provider_lower]]

    # Lionpride also accepts unknown providers with warning (OpenAI-compatible fallback)
    return True


def match_endpoint(
    provider: str,
    endpoint: str = "chat/completions",
    **kwargs: Any,
) -> Endpoint:
    # Check registry first (custom endpoints take precedence)
    endpoint_cls = get_endpoint_class(provider, endpoint)

    if endpoint_cls is not None:
        return endpoint_cls(**kwargs)

    # Fall back to kron for LLM providers
    # Note: kron does not have a match_endpoint function yet,
    # so we raise an error for unregistered endpoints
    raise ValueError(
        f"No endpoint registered for provider={provider}, endpoint={endpoint}. "
        f"Register with @register_endpoint or use kron.services.Endpoint directly."
    )
