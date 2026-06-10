"""ServiceAwarePhraseResolver - Routes charter actions through KronService.

Extends PhraseResolver to optionally route phrase calls through registered
CanonService instances, enabling:
- OPA policy evaluation
- Automatic evidence emission hooks
- Service-level input validation
- Pre/post hooks

When no service is registered for an action, falls back to direct phrase call.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from canon.enforcement.context import RequestContext
    from canon.enforcement.service import CanonService
    from canon.hub.package import VocabularyPackage

logger = logging.getLogger(__name__)

__all__ = (
    "ExplicitServiceMapping",
    "ServiceAwarePhraseResolver",
    "ServiceCallable",
    "ServiceMapping",
)


class ServiceCallable(Protocol):
    """Protocol for service.call() signature."""

    async def __call__(
        self,
        name: str,
        options: Any,
        ctx: RequestContext,
    ) -> Any: ...


# Mapping from action name to CanonService instance
ServiceMapping = dict[str, "CanonService"]


class ServiceAwarePhraseResolver:
    """Resolve feature names to callables, routing through services when available.

    Extends the behavior of PhraseResolver by:
    1. Checking if a registered service handles the requested action
    2. If yes, returning a wrapper that calls service.call()
    3. If no, falling back to direct phrase callable lookup

    This enables CharterExecutor to benefit from service-layer features:
    - Policy evaluation (OPA)
    - Evidence emission hooks
    - Input validation
    - Pre/post hooks

    Example:
        >>> from canon.enforcement.service import CanonService
        >>> from canon.hub.package import VocabularyPackage
        >>>
        >>> # Map action names to services
        >>> services = {
        ...     "verify_consent_token": consent_service,
        ...     "grant_consent_token": consent_service,
        ...     "certify_termination": certification_service,
        ... }
        >>>
        >>> resolver = ServiceAwarePhraseResolver(ALL_PACKAGES, services)
        >>> executor = CharterExecutor(resolver)
        >>>
        >>> # Now actions route through services with full hooks/policies
        >>> result = await executor.execute(compiled, "workflow", ctx)
    """

    def __init__(
        self,
        packages: Sequence[VocabularyPackage],
        services: ServiceMapping | None = None,
        explicit_mapping: ExplicitServiceMapping | None = None,
    ) -> None:
        """Initialize resolver with packages and optional service mappings.

        Args:
            packages: VocabularyPackages to scan for phrase callables.
            services: Mapping of action_name -> CanonService.
                      When an action has a registered service, calls route
                      through service.call() instead of direct phrase invocation.
            explicit_mapping: Optional explicit phrase->action name mapping.
        """
        self._callables: dict[str, Callable] = {}
        self._services = services or {}
        self._explicit_mapping = explicit_mapping

        # Import phrase callables from packages (same as PhraseResolver)
        self._load_packages(packages)

    def _load_packages(self, packages: Sequence[VocabularyPackage]) -> None:
        """Scan packages and load phrase callables."""
        import importlib

        for pkg in packages:
            if not pkg.domain_module:
                continue
            try:
                mod = importlib.import_module(f"{pkg.domain_module}.phrases")
            except ImportError:
                logger.warning("Cannot import phrases for package %s", pkg.name)
                continue

            for fname in pkg.feature_names:
                fn = getattr(mod, fname, None)
                if fn is not None and callable(fn):
                    self._callables[fname] = fn

    @property
    def feature_names(self) -> frozenset[str]:
        """All resolvable feature names."""
        return frozenset(self._callables)

    @property
    def service_routed_actions(self) -> frozenset[str]:
        """Action names that route through services."""
        return frozenset(self._services)

    def has(self, name: str) -> bool:
        """Check if feature is resolvable."""
        return name in self._callables

    def has_service(self, name: str) -> bool:
        """Check if action has a registered service."""
        return name in self._services

    def resolve(self, name: str) -> Callable:
        """Resolve feature name to callable, routing through service if available.

        If a service is registered for this action:
            Returns a wrapper that calls service.call(name, options, ctx)

        Otherwise:
            Returns the direct phrase callable.

        Args:
            name: Feature/action name to resolve.

        Returns:
            Async callable with signature (options, ctx) -> result

        Raises:
            KeyError: If feature not found in any package.
        """
        # First, ensure the feature exists
        if name not in self._callables:
            raise KeyError(
                f"Feature '{name}' not resolved. Available: {sorted(self._callables)[:10]}..."
            )

        # Check explicit mapping first
        if self._explicit_mapping:
            mapping_entry = self._explicit_mapping.get(name)
            if mapping_entry is not None:
                service, action_name = mapping_entry
                logger.debug(
                    "Routing action '%s' through service '%s' as '%s' (explicit)",
                    name,
                    service.service_name,
                    action_name,
                )
                return self._make_service_wrapper(action_name, service)

        # Check if we have a service for this action
        service = self._services.get(name)
        if service is not None:
            logger.debug(
                "Routing action '%s' through service '%s'",
                name,
                service.service_name,
            )
            # Return a wrapper that calls service.call()
            return self._make_service_wrapper(name, service)

        # Fall back to direct phrase callable
        logger.debug("Direct phrase call for '%s' (no service registered)", name)
        return self._callables[name]

    def resolve_or_none(self, name: str) -> Callable | None:
        """Resolve feature name, returning None if not found."""
        try:
            return self.resolve(name)
        except KeyError:
            return None

    def _make_service_wrapper(
        self,
        action_name: str,
        service: CanonService,
    ) -> Callable:
        """Create a wrapper that routes calls through service.call().

        The wrapper adapts the executor's calling convention:
            phrase_fn(args_dict, ctx)

        To the service's calling convention:
            service.call(name, options, ctx)
        """
        # Capture the original phrase callable for fallback
        original_phrase_name = action_name
        original_callable = self._callables.get(action_name)

        async def service_wrapper(options: dict, ctx: Any) -> Any:
            """Wrapper that routes through service.call()."""
            # Map the action name to the service's action method name
            # e.g., "verify_consent_token" -> "verify"
            short_name = self._infer_action_name(action_name)

            try:
                return await service.call(short_name, options, ctx)
            except ValueError:
                # Action not found in service, fall back to direct call
                logger.warning(
                    "Service '%s' has no action '%s', falling back to direct phrase",
                    service.service_name,
                    short_name,
                )
                if original_callable:
                    return await original_callable(options, ctx)
                raise

        return service_wrapper

    def _infer_action_name(self, phrase_name: str) -> str:
        """Infer service action name from phrase name.

        Convention:
            verify_consent_token -> verify
            grant_consent_token -> grant
            certify_termination -> certify
            list_consent_tokens -> list

        This strips the domain suffix from phrase names.
        """
        # Common patterns:
        # verify_* -> verify
        # require_* -> require
        # grant_* -> grant
        # revoke_* -> revoke
        # list_* -> list
        # check_* -> check
        # certify_* -> certify
        # cascade_* -> cascade

        prefixes = (
            "verify_",
            "require_",
            "grant_",
            "revoke_",
            "list_",
            "check_",
            "certify_",
            "cascade_",
            "get_",
            "record_",
        )

        for prefix in prefixes:
            if phrase_name.startswith(prefix):
                return prefix.rstrip("_")

        # No match, return as-is
        return phrase_name

    @classmethod
    def from_callables(
        cls,
        callables: dict[str, Callable],
        services: ServiceMapping | None = None,
    ) -> ServiceAwarePhraseResolver:
        """Create resolver from explicit feature->callable mapping.

        Useful for testing without importing real package modules.
        """
        inst = cls.__new__(cls)
        inst._callables = dict(callables)
        inst._services = services or {}
        inst._explicit_mapping = None
        return inst

    def register_service(self, action_names: list[str], service: CanonService) -> None:
        """Register a service for a set of action names.

        Args:
            action_names: List of phrase names this service handles.
            service: CanonService instance to route calls through.
        """
        for name in action_names:
            if name in self._services:
                logger.warning(
                    "Overwriting service registration for '%s': %s -> %s",
                    name,
                    self._services[name].service_name,
                    service.service_name,
                )
            self._services[name] = service

    def unregister_service(self, action_name: str) -> CanonService | None:
        """Remove service registration for an action name."""
        return self._services.pop(action_name, None)


class ExplicitServiceMapping:
    """Explicit mapping from phrase names to (service, action_name) pairs.

    This is more explicit than inferring action names from phrase names.

    Example:
        >>> mapping = ExplicitServiceMapping()
        >>> mapping.add("verify_consent_token", consent_service, "verify")
        >>> mapping.add("grant_consent_token", consent_service, "grant")
        >>> mapping.add("certify_termination", cert_service, "certify")
        >>>
        >>> resolver = ServiceAwarePhraseResolver(packages, explicit_mapping=mapping)
    """

    def __init__(self):
        self._mapping: dict[str, tuple[CanonService, str]] = {}

    def add(
        self,
        phrase_name: str,
        service: CanonService,
        action_name: str,
    ) -> None:
        """Map a phrase name to a (service, action_name) pair."""
        self._mapping[phrase_name] = (service, action_name)

    def get(self, phrase_name: str) -> tuple[CanonService, str] | None:
        """Get (service, action_name) for a phrase, or None."""
        return self._mapping.get(phrase_name)

    def __contains__(self, phrase_name: str) -> bool:
        return phrase_name in self._mapping
