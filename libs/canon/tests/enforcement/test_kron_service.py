"""Tests for KronService core infrastructure.

Covers:
- kron_action decorator and ActionMeta
- get_action_meta retrieval
- _to_pascal utility
- RequestContext metadata attribute access (__getattr__)
- KronService._register_actions() method scanning
- KronService.call() action dispatch
- KronService pre/post hook invocation
- KronService policy evaluation flow
- canon_action decorator and CanonActionMeta
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from canon.enforcement.config import KronConfig
from canon.enforcement.context import RequestContext
from canon.enforcement.policy import EnforcementLevel, ResolvedPolicy
from canon.enforcement.service import (
    ActionMeta,
    CanonActionMeta,
    KronService,
    _to_pascal,
    action,
    canon_action,
    get_action_meta,
    get_canon_action_meta,
    kron_action,
)

# =============================================================================
# Helpers
# =============================================================================

_DEFAULT_CONFIG = KronConfig(
    provider="test_provider",
    name="test_service",
    use_policies=False,
)


def _make_ctx(name: str = "test", **kwargs: Any) -> RequestContext:
    """Create a minimal RequestContext for testing."""
    return RequestContext(name=name, **kwargs)


def _make_config(**overrides: Any) -> KronConfig:
    """Create a KronConfig with sensible test defaults, overriding as needed."""
    defaults = {
        "provider": "test_provider",
        "name": "test_service",
        "use_policies": False,
    }
    defaults.update(overrides)
    return KronConfig(**defaults)


# =============================================================================
# _to_pascal Tests
# =============================================================================


class TestToPascal:
    """Tests for _to_pascal conversion utility."""

    def test_dot_separated(self):
        assert _to_pascal("consent.grant") == "ConsentGrant"

    def test_underscore_separated(self):
        assert _to_pascal("consent_grant") == "ConsentGrant"

    def test_mixed_separators(self):
        assert _to_pascal("consent.grant_token") == "ConsentGrantToken"

    def test_single_word(self):
        assert _to_pascal("grant") == "Grant"

    def test_already_capitalized_parts(self):
        # Each part is independently capitalized
        assert _to_pascal("CONSENT.GRANT") == "ConsentGrant"


# =============================================================================
# ActionMeta and kron_action decorator Tests
# =============================================================================


class TestActionMeta:
    """Tests for ActionMeta dataclass."""

    def test_defaults(self):
        meta = ActionMeta(name="test.action")
        assert meta.name == "test.action"
        assert meta.inputs == frozenset()
        assert meta.outputs == frozenset()
        assert meta.pre_hooks == ()
        assert meta.post_hooks == ()
        assert meta._options_type is None
        assert meta._result_type is None

    def test_with_inputs_outputs(self):
        meta = ActionMeta(
            name="consent.grant",
            inputs=frozenset({"subject_id", "scope"}),
            outputs=frozenset({"consent_id", "granted_at"}),
        )
        assert "subject_id" in meta.inputs
        assert "scope" in meta.inputs
        assert "consent_id" in meta.outputs
        assert "granted_at" in meta.outputs

    def test_with_hooks(self):
        meta = ActionMeta(
            name="test.action",
            pre_hooks=("validate", "authorize"),
            post_hooks=("emit_evidence",),
        )
        assert meta.pre_hooks == ("validate", "authorize")
        assert meta.post_hooks == ("emit_evidence",)

    def test_frozen(self):
        meta = ActionMeta(name="test.action")
        with pytest.raises(AttributeError):
            meta.name = "changed"


class TestKronActionDecorator:
    """Tests for @kron_action decorator."""

    def test_decorates_function(self):
        @kron_action(name="test.action")
        async def _handler(self, options, ctx):
            pass

        meta = get_action_meta(_handler)
        assert meta is not None
        assert meta.name == "test.action"

    def test_preserves_function_identity(self):
        async def _original(self, options, ctx):
            pass

        decorated = kron_action(name="test.action")(_original)
        # Decorator returns the same function object
        assert decorated is _original

    def test_sets_inputs_outputs(self):
        @kron_action(
            name="consent.grant",
            inputs={"subject_id", "scope"},
            outputs={"consent_id"},
        )
        async def _handler(self, options, ctx):
            pass

        meta = get_action_meta(_handler)
        assert meta.inputs == frozenset({"subject_id", "scope"})
        assert meta.outputs == frozenset({"consent_id"})

    def test_sets_hooks(self):
        @kron_action(
            name="test.action",
            pre_hooks=["validate"],
            post_hooks=["emit"],
        )
        async def _handler(self, options, ctx):
            pass

        meta = get_action_meta(_handler)
        assert meta.pre_hooks == ("validate",)
        assert meta.post_hooks == ("emit",)

    def test_defaults_to_empty(self):
        @kron_action(name="test.action")
        async def _handler(self, options, ctx):
            pass

        meta = get_action_meta(_handler)
        assert meta.inputs == frozenset()
        assert meta.outputs == frozenset()
        assert meta.pre_hooks == ()
        assert meta.post_hooks == ()


class TestGetActionMeta:
    """Tests for get_action_meta retrieval."""

    def test_returns_meta_for_decorated(self):
        @kron_action(name="test.action")
        async def _handler(self, options, ctx):
            pass

        assert get_action_meta(_handler) is not None

    def test_returns_none_for_undecorated(self):
        async def _plain_handler(self, options, ctx):
            pass

        assert get_action_meta(_plain_handler) is None

    def test_returns_none_for_non_callable(self):
        assert get_action_meta("not_a_callable") is None


# =============================================================================
# RequestContext __getattr__ Tests
# =============================================================================


class TestRequestContextGetattr:
    """Tests for RequestContext metadata attribute access fallback."""

    def test_slot_attribute_access(self):
        ctx = RequestContext(name="test.action")
        assert ctx.name == "test.action"
        assert ctx.conn is None
        assert ctx.session_id is None

    def test_metadata_via_kwargs(self):
        tenant_id = uuid4()
        ctx = RequestContext(name="test", tenant_id=tenant_id, actor_id="alice")
        assert ctx.tenant_id == tenant_id
        assert ctx.actor_id == "alice"

    def test_missing_attribute_raises(self):
        ctx = RequestContext(name="test")
        with pytest.raises(AttributeError, match="no attribute 'nonexistent'"):
            _ = ctx.nonexistent

    def test_hasattr_works_for_missing(self):
        ctx = RequestContext(name="test")
        assert not hasattr(ctx, "nonexistent")

    def test_hasattr_works_for_present_metadata(self):
        ctx = RequestContext(name="test", custom_field="value")
        assert hasattr(ctx, "custom_field")

    def test_underscore_attr_raises_immediately(self):
        ctx = RequestContext(name="test")
        with pytest.raises(AttributeError):
            _ = ctx._private_thing

    def test_slot_mutation(self):
        ctx = RequestContext(name="original")
        ctx.name = "updated"
        assert ctx.name == "updated"

    def test_metadata_dict_access(self):
        ctx = RequestContext(name="test", foo="bar", count=42)
        assert ctx.metadata == {"foo": "bar", "count": 42}

    def test_metadata_mutation_reflected_in_getattr(self):
        ctx = RequestContext(name="test")
        ctx.metadata["dynamic"] = "value"
        assert ctx.dynamic == "value"


# =============================================================================
# KronService test subclasses
# =============================================================================


class _ServiceWithActions(KronService):
    """Test service with decorated action handlers."""

    @kron_action(name="do_something")
    async def _handle_do_something(self, options: Any, ctx: RequestContext) -> dict:
        return {"status": "done"}

    @kron_action(name="do_other")
    async def _handle_do_other(self, options: Any, ctx: RequestContext) -> dict:
        return {"status": "other"}

    # This should NOT be registered (no decorator)
    async def _undecorated_method(self, options: Any, ctx: RequestContext) -> dict:
        return {"status": "not_registered"}

    # This should NOT be registered (public, not scanned by _register_actions)
    @kron_action(name="public_action")
    async def public_but_not_private(self, options: Any, ctx: RequestContext) -> dict:
        return {"status": "public"}


class _HookedService(KronService):
    """Service with pre and post hooks for testing hook order."""

    @kron_action(
        name="with_hooks",
        pre_hooks=["pre_validate"],
        post_hooks=["post_emit"],
    )
    async def _handle_with_hooks(self, options: Any, ctx: RequestContext) -> dict:
        return {"status": "ok"}


class _PolicyTestService(KronService):
    """Service for policy evaluation tests."""

    @kron_action(name="protected")
    async def _handle_protected(self, options: Any, ctx: RequestContext) -> dict:
        return {"access": "granted"}


# =============================================================================
# KronService._register_actions() Tests
# =============================================================================


class TestRegisterActions:
    """Tests for KronService._register_actions() method scanning."""

    def test_discovers_decorated_private_methods(self):
        service = _ServiceWithActions(config=_make_config())
        assert "do_something" in service._action_registry
        assert "do_other" in service._action_registry

    def test_ignores_undecorated_methods(self):
        service = _ServiceWithActions(config=_make_config())
        # _undecorated_method has no @kron_action, should not appear
        registered_names = set(service._action_registry.keys())
        assert "undecorated_method" not in registered_names

    def test_only_scans_private_methods(self):
        """_register_actions only scans methods starting with '_'."""
        service = _ServiceWithActions(config=_make_config())
        # public_but_not_private starts without _, so never scanned
        assert "public_action" not in service._action_registry

    def test_registry_contains_handler_and_meta(self):
        service = _ServiceWithActions(config=_make_config())
        handler, meta = service._action_registry["do_something"]
        assert callable(handler)
        assert isinstance(meta, ActionMeta)
        assert meta.name == "do_something"

    def test_empty_service_has_empty_registry(self):
        """A service with no @kron_action methods has an empty registry."""

        class _EmptyService(KronService):
            pass

        service = _EmptyService(config=_make_config(name="empty_service"))
        assert service._action_registry == {}

    def test_registry_handler_is_bound_method(self):
        """Handler in registry is a bound method of the service instance."""
        service = _ServiceWithActions(config=_make_config())
        handler, _ = service._action_registry["do_something"]
        # Bound method: calling it does not require passing self
        assert hasattr(handler, "__self__")
        assert handler.__self__ is service


# =============================================================================
# KronService.call() Tests
# =============================================================================


class TestKronServiceCall:
    """Tests for KronService.call() dispatching."""

    @pytest.mark.anyio
    async def test_dispatches_to_handler(self):
        service = _ServiceWithActions(config=_make_config())
        ctx = _make_ctx()
        result = await service.call("do_something", {}, ctx)
        assert result == {"status": "done"}

    @pytest.mark.anyio
    async def test_unknown_action_raises_value_error(self):
        service = _ServiceWithActions(config=_make_config())
        ctx = _make_ctx()
        with pytest.raises(ValueError, match="Unknown action: nonexistent"):
            await service.call("nonexistent", {}, ctx)

    @pytest.mark.anyio
    async def test_sets_ctx_name(self):
        service = _ServiceWithActions(config=_make_config())
        ctx = _make_ctx(name="original")
        await service.call("do_something", {}, ctx)
        assert ctx.name == "do_something"

    @pytest.mark.anyio
    async def test_handler_receives_options_and_ctx(self):
        received = {}

        class _CapturingService(KronService):
            @kron_action(name="capture")
            async def _handle(self, options: Any, ctx: RequestContext) -> dict:
                received["options"] = options
                received["ctx"] = ctx
                return {}

        service = _CapturingService(config=_make_config(name="capturing"))
        ctx = _make_ctx()
        payload = {"key": "value"}
        await service.call("capture", payload, ctx)
        assert received["options"] == payload
        assert received["ctx"] is ctx

    @pytest.mark.anyio
    async def test_returns_handler_result(self):
        class _ReturningService(KronService):
            @kron_action(name="ret")
            async def _handle(self, options: Any, ctx: RequestContext) -> dict:
                return {"computed": options.get("x", 0) * 2}

        service = _ReturningService(config=_make_config(name="returning"))
        ctx = _make_ctx()
        result = await service.call("ret", {"x": 21}, ctx)
        assert result == {"computed": 42}


# =============================================================================
# KronService Hook Tests
# =============================================================================


class TestKronServiceHooks:
    """Tests for pre/post hook invocation in KronService.call()."""

    @pytest.mark.anyio
    async def test_pre_hook_runs_before_handler(self):
        order: list[str] = []

        async def pre_validate(service, options, ctx, result):
            order.append("pre_validate")

        async def post_emit(service, options, ctx, result):
            order.append("post_emit")

        service = _HookedService(
            config=_make_config(
                name="hooked_svc",
                hooks={"pre_validate": pre_validate, "post_emit": post_emit},
            ),
        )

        # Replace the handler to track execution order in the same list
        meta = service._action_registry["with_hooks"][1]

        async def tracked_handler(options, ctx):
            order.append("handler")
            return {"status": "ok"}

        service._action_registry["with_hooks"] = (tracked_handler, meta)

        ctx = _make_ctx()
        await service.call("with_hooks", {}, ctx)

        assert order == ["pre_validate", "handler", "post_emit"]

    @pytest.mark.anyio
    async def test_post_hook_receives_result(self):
        captured_result = {}

        async def post_emit(service, options, ctx, result):
            captured_result["value"] = result

        service = _HookedService(
            config=_make_config(
                name="hooked_svc",
                hooks={"pre_validate": AsyncMock(), "post_emit": post_emit},
            ),
        )
        ctx = _make_ctx()
        await service.call("with_hooks", {}, ctx)

        assert captured_result["value"] == {"status": "ok"}

    @pytest.mark.anyio
    async def test_pre_hook_receives_none_result(self):
        """Pre-hooks are called with result=None (no handler result yet)."""
        captured = {}

        async def pre_validate(service, options, ctx, result):
            captured["result"] = result

        service = _HookedService(
            config=_make_config(
                name="hooked_svc",
                hooks={"pre_validate": pre_validate, "post_emit": AsyncMock()},
            ),
        )
        ctx = _make_ctx()
        await service.call("with_hooks", {}, ctx)

        assert captured["result"] is None

    @pytest.mark.anyio
    async def test_missing_hook_logs_warning(self, caplog):
        """When a hook name is not in config.hooks, a warning is logged."""
        # Create service with hooks declared in action but not in config.hooks
        service = _HookedService(
            config=_make_config(name="hooked_svc", hooks={}),
        )
        ctx = _make_ctx()

        with caplog.at_level(logging.WARNING):
            await service.call("with_hooks", {}, ctx)

        assert any("pre_validate" in r.message and "not found" in r.message for r in caplog.records)

    @pytest.mark.anyio
    async def test_hook_exception_is_logged_not_raised(self, caplog):
        """Hook failures are logged but do not stop execution."""

        async def failing_hook(service, options, ctx, result):
            raise RuntimeError("hook crashed")

        service = _HookedService(
            config=_make_config(
                name="hooked_svc",
                hooks={"pre_validate": failing_hook, "post_emit": AsyncMock()},
            ),
        )
        ctx = _make_ctx()

        with caplog.at_level(logging.ERROR):
            # call() should complete despite hook failure
            result = await service.call("with_hooks", {}, ctx)

        assert result == {"status": "ok"}
        assert any("pre_validate" in r.message and "failed" in r.message for r in caplog.records)

    @pytest.mark.anyio
    async def test_action_without_hooks_skips_hook_phase(self):
        """An action with no pre/post hooks proceeds directly."""

        class _NoHookService(KronService):
            @kron_action(name="plain")
            async def _handle(self, options: Any, ctx: RequestContext) -> dict:
                return {"plain": True}

        service = _NoHookService(config=_make_config(name="no_hooks"))
        ctx = _make_ctx()
        result = await service.call("plain", {}, ctx)
        assert result == {"plain": True}


# =============================================================================
# KronService Policy Evaluation Tests
# =============================================================================


@dataclass
class _MockPolicyResult:
    """Mock policy evaluation result."""

    policy_id: str
    enforcement: str = ""
    message: str = ""


class _MockPolicyEngine:
    """Mock policy engine implementing PolicyEngine protocol."""

    def __init__(self, results: list[_MockPolicyResult] | None = None):
        self._results = results or []

    async def evaluate(self, policy_id: str, input_data: dict, **options: Any) -> Any:
        for r in self._results:
            if r.policy_id == policy_id:
                return r
        return _MockPolicyResult(policy_id=policy_id)

    async def evaluate_batch(
        self, policy_ids: Sequence[str], input_data: dict, **options: Any
    ) -> list[Any]:
        return self._results


class _MockPolicyResolver:
    """Mock policy resolver implementing PolicyResolver protocol."""

    def __init__(self, policies: list[ResolvedPolicy] | None = None):
        self._policies = policies or []

    def resolve(self, ctx: RequestContext) -> Sequence[ResolvedPolicy]:
        return self._policies


class TestKronServicePolicyEvaluation:
    """Tests for policy evaluation flow in KronService.call()."""

    @pytest.mark.anyio
    async def test_policies_evaluated_when_enabled(self):
        """Policies are evaluated when use_policies=True and engine+resolver present."""
        engine = _MockPolicyEngine(results=[])
        resolver = _MockPolicyResolver(policies=[ResolvedPolicy(policy_id="pol_1")])

        service = _PolicyTestService(
            config=_make_config(name="policy_svc", use_policies=True),
            policy_engine=engine,
            policy_resolver=resolver,
        )
        ctx = _make_ctx()
        result = await service.call("protected", {}, ctx)
        assert result == {"access": "granted"}

    @pytest.mark.anyio
    async def test_blocking_policy_raises_permission_error(self):
        """A blocking policy result raises PermissionError."""
        blocking_result = _MockPolicyResult(
            policy_id="pol_block",
            enforcement=EnforcementLevel.HARD_MANDATORY.value,
            message="Access denied by policy",
        )
        engine = _MockPolicyEngine(results=[blocking_result])
        resolver = _MockPolicyResolver(policies=[ResolvedPolicy(policy_id="pol_block")])

        service = _PolicyTestService(
            config=_make_config(name="policy_svc", use_policies=True),
            policy_engine=engine,
            policy_resolver=resolver,
        )
        ctx = _make_ctx()

        with pytest.raises(PermissionError, match="pol_block"):
            await service.call("protected", {}, ctx)

    @pytest.mark.anyio
    async def test_soft_mandatory_also_blocks(self):
        """SOFT_MANDATORY enforcement also blocks the action."""
        soft_block = _MockPolicyResult(
            policy_id="pol_soft",
            enforcement=EnforcementLevel.SOFT_MANDATORY.value,
            message="Soft block",
        )
        engine = _MockPolicyEngine(results=[soft_block])
        resolver = _MockPolicyResolver(policies=[ResolvedPolicy(policy_id="pol_soft")])

        service = _PolicyTestService(
            config=_make_config(name="policy_svc", use_policies=True),
            policy_engine=engine,
            policy_resolver=resolver,
        )
        ctx = _make_ctx()

        with pytest.raises(PermissionError):
            await service.call("protected", {}, ctx)

    @pytest.mark.anyio
    async def test_advisory_policy_allows_action(self):
        """ADVISORY enforcement does not block the action."""
        advisory_result = _MockPolicyResult(
            policy_id="pol_adv",
            enforcement=EnforcementLevel.ADVISORY.value,
            message="Just a warning",
        )
        engine = _MockPolicyEngine(results=[advisory_result])
        resolver = _MockPolicyResolver(policies=[ResolvedPolicy(policy_id="pol_adv")])

        service = _PolicyTestService(
            config=_make_config(name="policy_svc", use_policies=True),
            policy_engine=engine,
            policy_resolver=resolver,
        )
        ctx = _make_ctx()
        result = await service.call("protected", {}, ctx)
        assert result == {"access": "granted"}

    @pytest.mark.anyio
    async def test_skips_when_use_policies_false(self):
        """No policy evaluation when use_policies=False."""
        blocking = _MockPolicyResult(
            policy_id="pol_block",
            enforcement=EnforcementLevel.HARD_MANDATORY.value,
            message="Should not fire",
        )
        engine = _MockPolicyEngine(results=[blocking])
        resolver = _MockPolicyResolver(policies=[ResolvedPolicy(policy_id="pol_block")])

        service = _PolicyTestService(
            config=_make_config(name="policy_svc", use_policies=False),
            policy_engine=engine,
            policy_resolver=resolver,
        )
        ctx = _make_ctx()
        # Should succeed because policies are disabled
        result = await service.call("protected", {}, ctx)
        assert result == {"access": "granted"}

    @pytest.mark.anyio
    async def test_skips_when_no_engine(self):
        """No policy evaluation when engine is None."""
        service = _PolicyTestService(
            config=_make_config(name="policy_svc", use_policies=True),
            policy_engine=None,
            policy_resolver=None,
        )
        ctx = _make_ctx()
        result = await service.call("protected", {}, ctx)
        assert result == {"access": "granted"}

    @pytest.mark.anyio
    async def test_skips_when_no_resolver(self):
        """Evaluation skipped inside _evaluate_policies when resolver is None."""
        engine = _MockPolicyEngine()

        service = _PolicyTestService(
            config=_make_config(name="policy_svc", use_policies=True),
            policy_engine=engine,
            policy_resolver=None,
        )
        ctx = _make_ctx()
        result = await service.call("protected", {}, ctx)
        assert result == {"access": "granted"}

    @pytest.mark.anyio
    async def test_empty_resolved_policies_skips(self):
        """When resolver returns empty list, no evaluation happens."""
        engine = _MockPolicyEngine()
        resolver = _MockPolicyResolver(policies=[])

        service = _PolicyTestService(
            config=_make_config(name="policy_svc", use_policies=True),
            policy_engine=engine,
            policy_resolver=resolver,
        )
        ctx = _make_ctx()
        result = await service.call("protected", {}, ctx)
        assert result == {"access": "granted"}

    @pytest.mark.anyio
    async def test_fail_open_on_engine_error(self, caplog):
        """When fail_open=True, engine error allows action to proceed."""

        class _FailingEngine:
            async def evaluate(self, policy_id, input_data, **opts):
                raise RuntimeError("Engine down")

            async def evaluate_batch(self, policy_ids, input_data, **opts):
                raise RuntimeError("Engine down")

        resolver = _MockPolicyResolver(policies=[ResolvedPolicy(policy_id="pol_1")])

        service = _PolicyTestService(
            config=_make_config(
                name="policy_svc",
                use_policies=True,
                fail_open_on_engine_error=True,
            ),
            policy_engine=_FailingEngine(),
            policy_resolver=resolver,
        )
        ctx = _make_ctx()

        with caplog.at_level(logging.ERROR):
            result = await service.call("protected", {}, ctx)

        assert result == {"access": "granted"}

    @pytest.mark.anyio
    async def test_fail_closed_on_engine_error(self):
        """When fail_open=False (default), engine error raises PermissionError."""

        class _FailingEngine:
            async def evaluate(self, policy_id, input_data, **opts):
                raise RuntimeError("Engine down")

            async def evaluate_batch(self, policy_ids, input_data, **opts):
                raise RuntimeError("Engine down")

        resolver = _MockPolicyResolver(policies=[ResolvedPolicy(policy_id="pol_1")])

        service = _PolicyTestService(
            config=_make_config(
                name="policy_svc",
                use_policies=True,
                fail_open_on_engine_error=False,
            ),
            policy_engine=_FailingEngine(),
            policy_resolver=resolver,
        )
        ctx = _make_ctx()

        with pytest.raises(PermissionError, match="Policy engine error"):
            await service.call("protected", {}, ctx)


# =============================================================================
# KronService Properties Tests
# =============================================================================


class TestKronServiceProperties:
    """Tests for KronService property accessors."""

    def test_provider_from_config(self):
        service = _ServiceWithActions(config=_make_config())
        assert service.provider == "test_provider"

    def test_name_from_config(self):
        service = _ServiceWithActions(config=_make_config(name="my_service"))
        assert service.name == "my_service"

    def test_version_default_none(self):
        service = _ServiceWithActions(config=_make_config())
        assert service.version is None

    def test_version_from_config(self):
        service = _PolicyTestService(
            config=_make_config(name="versioned", version="1.2.3"),
        )
        assert service.version == "1.2.3"

    def test_tags_empty_default(self):
        service = _ServiceWithActions(config=_make_config())
        assert service.tags == set()

    def test_tags_from_config(self):
        service = _PolicyTestService(
            config=_make_config(name="tagged_svc", tags=["compliance", "consent"]),
        )
        assert service.tags == {"compliance", "consent"}

    def test_has_engine_false_by_default(self):
        service = _ServiceWithActions(config=_make_config())
        assert service.has_engine is False

    def test_has_engine_true_when_set(self):
        service = _PolicyTestService(
            config=_make_config(name="policy_svc"),
            policy_engine=_MockPolicyEngine(),
        )
        assert service.has_engine is True

    def test_has_resolver_false_by_default(self):
        service = _ServiceWithActions(config=_make_config())
        assert service.has_resolver is False

    def test_has_resolver_true_when_set(self):
        service = _PolicyTestService(
            config=_make_config(name="policy_svc"),
            policy_resolver=_MockPolicyResolver(),
        )
        assert service.has_resolver is True


# =============================================================================
# canon_action Decorator and CanonActionMeta Tests
# =============================================================================


class TestCanonActionMeta:
    """Tests for CanonActionMeta dataclass."""

    def test_defaults(self):
        meta = CanonActionMeta(name="grant")
        assert meta.name == "grant"
        assert meta.evidence_type is None
        assert meta.skip_evidence is False

    def test_with_evidence_type(self):
        meta = CanonActionMeta(name="grant", evidence_type="consent.grant")
        assert meta.evidence_type == "consent.grant"

    def test_skip_evidence(self):
        meta = CanonActionMeta(name="verify", skip_evidence=True)
        assert meta.skip_evidence is True

    def test_frozen(self):
        meta = CanonActionMeta(name="grant")
        with pytest.raises(AttributeError):
            meta.name = "changed"


class TestCanonActionDecorator:
    """Tests for @canon_action (and @action alias) decorator."""

    def test_canon_action_with_name(self):
        @canon_action(name="grant")
        async def grant(self, payload, ctx):
            pass

        meta = get_canon_action_meta(grant)
        assert meta is not None
        assert meta.name == "grant"

    def test_canon_action_defaults_name_to_func_name(self):
        @canon_action()
        async def my_action(self, payload, ctx):
            pass

        meta = get_canon_action_meta(my_action)
        assert meta.name == "my_action"

    def test_canon_action_with_evidence_type(self):
        @canon_action(evidence_type="consent.grant")
        async def grant(self, payload, ctx):
            pass

        meta = get_canon_action_meta(grant)
        assert meta.evidence_type == "consent.grant"

    def test_canon_action_skip_evidence(self):
        @canon_action(skip_evidence=True)
        async def verify(self, payload, ctx):
            pass

        meta = get_canon_action_meta(verify)
        assert meta.skip_evidence is True

    def test_action_alias_same_as_canon_action(self):
        """The 'action' name is an alias for canon_action."""
        assert action is canon_action

    def test_action_alias_works(self):
        @action(evidence_type="my.type")
        async def do_thing(self, payload, ctx):
            pass

        meta = get_canon_action_meta(do_thing)
        assert meta is not None
        assert meta.evidence_type == "my.type"

    def test_get_canon_action_meta_returns_none_for_undecorated(self):
        async def plain(self, payload, ctx):
            pass

        assert get_canon_action_meta(plain) is None

    def test_preserves_function_identity(self):
        async def original(self, payload, ctx):
            pass

        decorated = canon_action(name="test")(original)
        assert decorated is original


# =============================================================================
# EnforcementLevel Tests
# =============================================================================


class TestEnforcementLevel:
    """Tests for EnforcementLevel.is_blocking and is_advisory."""

    def test_hard_mandatory_is_blocking(self):
        result = _MockPolicyResult(policy_id="p", enforcement=EnforcementLevel.HARD_MANDATORY.value)
        assert EnforcementLevel.is_blocking(result) is True

    def test_soft_mandatory_is_blocking(self):
        result = _MockPolicyResult(policy_id="p", enforcement=EnforcementLevel.SOFT_MANDATORY.value)
        assert EnforcementLevel.is_blocking(result) is True

    def test_advisory_is_not_blocking(self):
        result = _MockPolicyResult(policy_id="p", enforcement=EnforcementLevel.ADVISORY.value)
        assert EnforcementLevel.is_blocking(result) is False

    def test_empty_enforcement_is_not_blocking(self):
        result = _MockPolicyResult(policy_id="p", enforcement="")
        assert EnforcementLevel.is_blocking(result) is False

    def test_advisory_is_advisory(self):
        result = _MockPolicyResult(policy_id="p", enforcement=EnforcementLevel.ADVISORY.value)
        assert EnforcementLevel.is_advisory(result) is True

    def test_hard_mandatory_is_not_advisory(self):
        result = _MockPolicyResult(policy_id="p", enforcement=EnforcementLevel.HARD_MANDATORY.value)
        assert EnforcementLevel.is_advisory(result) is False


# =============================================================================
# KronService._fetch_handler Tests
# =============================================================================


class TestFetchHandler:
    """Tests for KronService._fetch_handler()."""

    def test_returns_handler_and_meta(self):
        service = _ServiceWithActions(config=_make_config())
        handler, meta = service._fetch_handler("do_something")
        assert callable(handler)
        assert meta.name == "do_something"

    def test_unknown_action_raises(self):
        service = _ServiceWithActions(config=_make_config())
        with pytest.raises(ValueError, match="Unknown action: bogus"):
            service._fetch_handler("bogus")


# =============================================================================
# Multiple Actions Interaction Tests
# =============================================================================


class TestMultipleActions:
    """Tests for services with multiple registered actions."""

    @pytest.mark.anyio
    async def test_dispatch_to_correct_handler(self):
        service = _ServiceWithActions(config=_make_config())
        ctx1 = _make_ctx()
        ctx2 = _make_ctx()

        r1 = await service.call("do_something", {}, ctx1)
        r2 = await service.call("do_other", {}, ctx2)

        assert r1 == {"status": "done"}
        assert r2 == {"status": "other"}

    @pytest.mark.anyio
    async def test_each_call_updates_ctx_name(self):
        service = _ServiceWithActions(config=_make_config())
        ctx = _make_ctx(name="initial")

        await service.call("do_something", {}, ctx)
        assert ctx.name == "do_something"

        await service.call("do_other", {}, ctx)
        assert ctx.name == "do_other"
