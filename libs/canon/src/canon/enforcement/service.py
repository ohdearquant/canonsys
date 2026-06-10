"""Service infrastructure - KronService base and CanonService compliance layer.

KronService: Typed action handlers with policy evaluation (from kron).
CanonService: Extends KronService with evidence emission, OPA, and rich context.

Usage:
    class ConsentService(CanonService):
        config = CanonServiceConfig(provider="canon", name="consent")

        @action(evidence_type="consent.grant")
        async def grant(self, payload: dict, ctx: RequestContext) -> dict:
            return {"status": "granted"}

    # Invocation via iModel
    model = iModel(backend=service, hook_registry=service.create_hook_registry())
    calling = await model.invoke(action="grant", payload={...}, ctx=ctx)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import Field, PrivateAttr

from kron.services import Calling, HookPhase, HookRegistry
from kron.types import HashableModel

from .config import KronConfig
from .context import RequestContext
from .policy import EnforcementLevel, PolicyEngine, PolicyResolver
from .types import ServiceContext, ctx_to_evidence_data

if TYPE_CHECKING:
    from canon.utils.opa.engine import PolicyEngine as OPAPolicyEngine
    from canon.utils.opa.resolver import PolicyIndex

logger = logging.getLogger(__name__)

__all__ = (
    # Kron action primitives
    "ActionMeta",
    "KronService",
    "kron_action",
    "get_action_meta",
    # Canon context
    "ServiceContext",
    "RequestContext",
    # Canon config
    "CanonServiceConfig",
    # Canon decorators
    "action",
    "canon_action",
    "CanonActionMeta",
    "get_canon_action_meta",
    # Canon service
    "CanonService",
    "CanonCalling",
)


# =============================================================================
# Kron action primitives (moved from kron/enforcement/service.py)
# =============================================================================

_ACTION_ATTR = "_kron_action"


@dataclass(frozen=True, slots=True)
class ActionMeta:
    """Metadata for an action handler.

    Attributes:
        name: Action identifier (e.g., "consent.grant").
        inputs: Field names from service operable used as inputs.
        outputs: Field names from service operable used as outputs.
        pre_hooks: Hook names to run before action.
        post_hooks: Hook names to run after action.
    """

    name: str
    inputs: frozenset[str] = frozenset()
    outputs: frozenset[str] = frozenset()
    pre_hooks: tuple[str, ...] = ()
    post_hooks: tuple[str, ...] = ()

    # Lazily computed types (set by service at registration)
    _options_type: Any = None
    _result_type: Any = None


def kron_action(
    name: str,
    inputs: set[str] | None = None,
    outputs: set[str] | None = None,
    pre_hooks: list[str] | None = None,
    post_hooks: list[str] | None = None,
) -> Callable[[Callable], Callable]:
    """Decorator to declare action handler metadata (kron-level).

    Args:
        name: Action identifier (e.g., "consent.grant").
        inputs: Field names from service operable used as inputs.
        outputs: Field names from service operable used as outputs.
        pre_hooks: Hook names to run before action.
        post_hooks: Hook names to run after action.

    Usage:
        @kron_action(
            name="consent.grant",
            inputs={"permissions", "subject_id"},
            outputs={"consent_id", "granted_at"},
        )
        async def _handle_grant(self, options, ctx):
            ...
    """

    def decorator(func: Callable) -> Callable:
        meta = ActionMeta(
            name=name,
            inputs=frozenset(inputs or set()),
            outputs=frozenset(outputs or set()),
            pre_hooks=tuple(pre_hooks or []),
            post_hooks=tuple(post_hooks or []),
        )
        setattr(func, _ACTION_ATTR, meta)
        return func

    return decorator


def get_action_meta(handler: Callable) -> ActionMeta | None:
    """Get action metadata from a handler method."""
    return getattr(handler, _ACTION_ATTR, None)


def _to_pascal(name: str) -> str:
    """Convert action name to PascalCase.

    consent.grant -> ConsentGrant
    consent_grant -> ConsentGrant
    """
    # Replace dots and underscores, capitalize each part
    parts = name.replace(".", "_").split("_")
    return "".join(part.capitalize() for part in parts)


# =============================================================================
# KronService
# =============================================================================


class KronService(HashableModel):
    """Service backend with typed actions.

    Subclasses implement action handlers with @action decorator.
    Actions derive typed I/O from service's canonical operable.

    Example:
        class ConsentService(KronService):
            config = KronConfig(
                name="consent",
                provider="canon",
                operable=Operable([
                    Spec("permissions", list[str]),
                    Spec("consent_id", UUID),
                    Spec("granted_at", datetime),
                    Spec("subject_id", FK[Subject]),
                ]),
            )

            @kron_action(
                name="consent.grant",
                inputs={"permissions", "subject_id"},
                outputs={"consent_id", "granted_at"},
            )
            async def _handle_grant(self, options, ctx):
                ...

        service = ConsentService()
        result = await service.call("consent.grant", options, ctx)
    """

    config: KronConfig = Field(default_factory=KronConfig)
    _policy_engine: PolicyEngine | None = PrivateAttr(default=None)
    _policy_resolver: PolicyResolver | None = PrivateAttr(default=None)
    _action_registry: dict[str, tuple[Callable, ActionMeta]] = PrivateAttr(default_factory=dict)

    def __init__(
        self,
        config: KronConfig | None = None,
        policy_engine: PolicyEngine | None = None,
        policy_resolver: PolicyResolver | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize service with optional policy engine and resolver.

        Args:
            config: Service configuration.
            policy_engine: PolicyEngine for policy evaluation.
            policy_resolver: PolicyResolver for determining applicable policies.
        """
        super().__init__(config=config, **kwargs)
        self._policy_engine = policy_engine
        self._policy_resolver = policy_resolver
        self._action_registry = {}
        self._register_actions()

    @property
    def provider(self) -> str:
        """Provider name from config."""
        return self.config.provider

    @property
    def name(self) -> str:
        """Service name from config."""
        return self.config.name

    @property
    def version(self) -> str | None:
        """Service version from config."""
        return self.config.version

    @property
    def tags(self) -> set[str]:
        """Service tags from config."""
        return set(self.config.tags) if self.config.tags else set()

    def _register_actions(self) -> None:
        """Scan for @action decorated methods and register them."""
        for name in dir(self):
            if name.startswith("_"):
                method = getattr(self, name, None)
                if method and callable(method):
                    meta = get_action_meta(method)
                    if meta:
                        self._action_registry[meta.name] = (method, meta)
                        self._build_action_types(meta)

    def _build_action_types(self, meta: ActionMeta) -> None:
        """Build options_type and result_type for an action from service operable."""
        if not self.config.operable:
            return

        operable = self.config.operable

        # Validate inputs/outputs exist in operable
        allowed = operable.allowed()
        invalid_inputs = meta.inputs - allowed
        invalid_outputs = meta.outputs - allowed

        if invalid_inputs:
            logger.warning(
                "Action '%s' has inputs not in operable: %s",
                meta.name,
                invalid_inputs,
            )
        if invalid_outputs:
            logger.warning(
                "Action '%s' has outputs not in operable: %s",
                meta.name,
                invalid_outputs,
            )

        # Build typed structures (frozen dataclasses)
        if meta.inputs:
            options_type = operable.compose_structure(
                _to_pascal(meta.name) + "Options",
                include=set(meta.inputs),
                frozen=True,
            )
            object.__setattr__(meta, "_options_type", options_type)

        if meta.outputs:
            result_type = operable.compose_structure(
                _to_pascal(meta.name) + "Result",
                include=set(meta.outputs),
                frozen=True,
            )
            object.__setattr__(meta, "_result_type", result_type)

    @property
    def has_engine(self) -> bool:
        """True if policy engine is configured."""
        return self._policy_engine is not None

    @property
    def has_resolver(self) -> bool:
        """True if policy resolver is configured."""
        return self._policy_resolver is not None

    async def call(
        self,
        name: str,
        options: Any,
        ctx: RequestContext,
    ) -> Any:
        """Call an action by name.

        Args:
            name: Action name (e.g., "consent.grant").
            options: Input data (dict or typed dataclass).
            ctx: Request context.

        Returns:
            Action result.

        Raises:
            ValueError: If action not found.
            PermissionError: If policy blocks action.
        """
        handler, meta = self._fetch_handler(name)

        # Update context
        ctx.name = name

        # Run pre-hooks
        await self._run_hooks(meta.pre_hooks, options, ctx)

        # Evaluate policies
        if self.config.use_policies and self._policy_engine:
            await self._evaluate_policies(ctx)

        # Validate options if we have typed options_type
        if meta._options_type and self.config.operable:
            options = self.config.operable.validate_instance(meta._options_type, options)

        # Execute handler
        result = await handler(options, ctx)

        # Run post-hooks
        await self._run_hooks(meta.post_hooks, options, ctx, result=result)

        return result

    def _fetch_handler(self, name: str) -> tuple[Callable, ActionMeta]:
        """Fetch handler and metadata by action name.

        Args:
            name: Action name.

        Returns:
            Tuple of (handler, ActionMeta).

        Raises:
            ValueError: If action not found.
        """
        if name not in self._action_registry:
            raise ValueError(f"Unknown action: {name}")
        return self._action_registry[name]

    async def _run_hooks(
        self,
        hook_names: tuple[str, ...],
        options: Any,
        ctx: RequestContext,
        result: Any = None,
    ) -> None:
        """Run named hooks from config.hooks."""
        for hook_name in hook_names:
            hook_fn = self.config.hooks.get(hook_name)
            if hook_fn:
                try:
                    await hook_fn(self, options, ctx, result)
                except Exception as e:
                    logger.error("Hook '%s' failed: %s", hook_name, e)
            else:
                logger.warning("Hook '%s' not found in config.hooks", hook_name)

    async def _evaluate_policies(self, ctx: RequestContext) -> None:
        """Evaluate policies via engine."""
        if not self._policy_engine or not self._policy_resolver:
            return

        try:
            resolved = self._policy_resolver.resolve(ctx)

            if not resolved:
                return

            policy_ids = [p.policy_id for p in resolved]
            input_data = ctx.to_dict()

            results = await self._policy_engine.evaluate_batch(policy_ids, input_data)

            for result in results:
                if EnforcementLevel.is_blocking(result):
                    raise PermissionError(f"Policy {result.policy_id} blocked: {result.message}")

        except PermissionError:
            raise
        except Exception as e:
            logger.error("Policy evaluation failed: %s", e)
            if not self.config.fail_open_on_engine_error:
                raise PermissionError(f"Policy engine error: {e}")


# =============================================================================
# Canon action decorators
# =============================================================================

_CANON_ACTION_ATTR = "_canon_action"


@dataclass(frozen=True, slots=True)
class CanonActionMeta:
    """Action metadata for canon-core.

    Attributes:
        name: Action identifier (e.g., "consent.grant").
        evidence_type: Evidence type for audit trail (defaults to action name).
        skip_evidence: If True, skip automatic evidence emission.
    """

    name: str
    evidence_type: str | None = None
    skip_evidence: bool = False


def canon_action(
    name: str | None = None,
    *,
    evidence_type: str | None = None,
    skip_evidence: bool = False,
) -> Callable[[Callable], Callable]:
    """Decorator to declare action metadata.

    Args:
        name: Action identifier. Defaults to method name.
        evidence_type: Evidence type for audit trail.
        skip_evidence: If True, skip automatic evidence emission.

    Usage:
        @canon_action(evidence_type="consent.grant")
        async def grant(self, payload: dict, ctx: RequestContext) -> dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        action_name = name or func.__name__
        meta = CanonActionMeta(
            name=action_name,
            evidence_type=evidence_type,
            skip_evidence=skip_evidence,
        )
        setattr(func, _CANON_ACTION_ATTR, meta)
        return func

    return decorator


def get_canon_action_meta(handler: Callable) -> CanonActionMeta | None:
    """Get action metadata from a handler method."""
    return getattr(handler, _CANON_ACTION_ATTR, None)


# Alias for convenience
action = canon_action


# =============================================================================
# CanonService
# =============================================================================


class CanonServiceConfig(KronConfig):
    """Configuration for CanonService.

    Attributes:
        evidence_type_prefix: Prefix for evidence types.
        skip_evidence: If True, skip automatic evidence emission.
        skip_policy_evaluation: If True, skip OPA policy evaluation.
    """

    evidence_type_prefix: str = ""
    skip_evidence: bool = False
    skip_policy_evaluation: bool = False


class CanonCalling(Calling):
    """Calling event for CanonService with compliance context.

    Extends kron's Calling with canon's rich RequestContext.
    """

    action: str = Field(..., description="Action name being invoked")
    ctx: RequestContext = Field(..., exclude=True, description="Request context")

    @property
    def call_args(self) -> dict[str, Any]:
        """Get arguments for backend.call()."""
        return {
            "name": self.action,
            "options": self.payload,
            "ctx": self.ctx,
        }

    def to_evidence_data(self) -> dict[str, Any]:
        """Serialize calling for evidence."""
        from kron.types import is_sentinel

        response = self.response
        response_data = None
        if not is_sentinel(response) and response is not None:
            response_data = response.model_dump()

        return {
            "action": self.action,
            "payload": self.payload,
            "context": ctx_to_evidence_data(self.ctx),
            "response": response_data,
        }


class CanonService(KronService):
    """Compliance-aware service backend.

    Extends KronService with:
    - Evidence emission hook
    - Canon's rich RequestContext
    - Optional OPA policy evaluation

    Example:
        class ConsentService(CanonService):
            config = CanonServiceConfig(provider="canon", name="consent")

            @action(evidence_type="consent.grant")
            async def grant(self, payload: dict, ctx: RequestContext) -> dict:
                return {"status": "granted"}

        service = ConsentService()
    """

    config: CanonServiceConfig

    # Optional OPA integration
    _policy_engine: OPAPolicyEngine | None = None
    _policy_index: PolicyIndex | None = None

    def __init__(
        self,
        policy_engine: OPAPolicyEngine | None = None,
        policy_index: PolicyIndex | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize service with optional OPA policy engine."""
        super().__init__(**kwargs)
        self._policy_engine = policy_engine
        self._policy_index = policy_index

    @property
    def event_type(self) -> type[Calling]:
        """Return CanonCalling for this backend."""
        return CanonCalling

    @property
    def service_name(self) -> str:
        """Service name from config."""
        return self.config.name

    def create_calling(
        self,
        action: str,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> CanonCalling:
        """Create a CanonCalling event."""
        ctx.action = action
        ctx.service_name = self.service_name
        return CanonCalling(
            backend=self,
            action=action,
            payload=payload,
            ctx=ctx,
        )

    def create_hook_registry(self) -> HookRegistry:
        """Create HookRegistry with evidence emission hook."""
        return HookRegistry(
            hooks={
                HookPhase.PostInvocation: self._canon_post_invoke_hook,
            }
        )

    async def _canon_post_invoke_hook(self, calling: CanonCalling, **_kw: Any) -> CanonCalling:
        """Post-invocation hook: evidence emission."""
        from kron.types import is_sentinel

        if self.config.skip_evidence:
            return calling

        # Get evidence type from @action decorator or default
        handler = getattr(self, calling.action, None)
        evidence_type = f"{self.service_name}.{calling.action}"

        if handler:
            canon_meta = get_canon_action_meta(handler)
            if canon_meta:
                if canon_meta.skip_evidence:
                    return calling
                if canon_meta.evidence_type:
                    evidence_type = canon_meta.evidence_type

        # Log evidence (actual persistence TBD)
        ctx = calling.ctx
        response = calling.response

        response_status = None
        if not is_sentinel(response) and response is not None:
            response_status = response.status == "success"

        logger.info(
            "Evidence: %s tenant=%s action=%s success=%s",
            evidence_type,
            ctx.tenant_id,
            calling.action,
            response_status,
        )

        return calling
