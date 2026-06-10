"""Charter workflow executor: compile → resolve → execute via kron operations.

Bridges CompiledCharter to kron's DependencyAwareExecutor, enabling
end-to-end execution of charter workflows as dependency-aware DAGs.

Architecture:
    CompiledCharter (phase DAG)
        ↓ CharterExecutor._build_graph()
    kron Graph (Operation nodes + dependency edges)
        ↓ kron flow() / flow_stream()
    WorkflowResult (phase results + pass/fail)
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import AsyncGenerator, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from canon.dsl.ast import (
    ActionNode,
    BuiltinRefNode,
    FeatureCallNode,
    PhaseNode,
    PhaseRefNode,
    RequireNode,
    WorkflowNode,
)
from canon.dsl.compiler import CompiledCharter
from kron.operations import Builder, flow, flow_stream
from kron.session import Session

from .package import VocabularyPackage

__all__ = (
    "CharterExecutor",
    "PhaseGateError",
    "PhaseResult",
    "PhraseResolver",
    "WorkflowResult",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PhaseResult:
    """Result of executing a single charter phase."""

    phase_name: str
    passed: bool
    action_results: dict[str, Any] = field(default_factory=dict)
    require_results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Result of executing an entire charter workflow."""

    workflow_name: str
    charter_name: str
    phase_results: dict[str, PhaseResult] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(pr.passed for pr in self.phase_results.values())


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PhaseGateError(RuntimeError):
    """A phase require-gate was not satisfied."""

    def __init__(self, phase_name: str, gate_desc: str, detail: str = ""):
        self.phase_name = phase_name
        self.gate_desc = gate_desc
        super().__init__(
            f"Phase '{phase_name}' gate failed: {gate_desc}" + (f" ({detail})" if detail else "")
        )


# ---------------------------------------------------------------------------
# PhraseResolver
# ---------------------------------------------------------------------------


class PhraseResolver:
    """Resolve feature names to callable phrase functions.

    Scans VocabularyPackages, dynamically imports their ``phrases``
    sub-module, and maps each feature_name to the matching callable.
    """

    def __init__(self, packages: Sequence[VocabularyPackage]) -> None:
        self._callables: dict[str, Callable] = {}
        declared_count = 0
        for pkg in packages:
            if not pkg.domain_module:
                continue
            declared_count += len(pkg.feature_names)
            try:
                mod = importlib.import_module(f"{pkg.domain_module}.phrases")
            except ImportError:
                logger.warning("Cannot import phrases for package %s", pkg.name)
                continue
            for fname in pkg.feature_names:
                fn = getattr(mod, fname, None)
                if fn is not None and callable(fn):
                    self._callables[fname] = fn
                else:
                    logger.debug(
                        "Feature '%s' declared by package '%s' not found in %s.phrases",
                        fname,
                        pkg.name,
                        pkg.domain_module,
                    )
        resolved_count = len(self._callables)
        if declared_count > 0 and resolved_count < declared_count:
            logger.warning(
                "PhraseResolver: resolved %d of %d declared features (%d missing)",
                resolved_count,
                declared_count,
                declared_count - resolved_count,
            )

    @property
    def feature_names(self) -> frozenset[str]:
        return frozenset(self._callables)

    def has(self, name: str) -> bool:
        return name in self._callables

    def resolve(self, name: str) -> Callable:
        """Return the callable for *name*, or raise KeyError."""
        try:
            return self._callables[name]
        except KeyError:
            raise KeyError(
                f"Feature '{name}' not resolved. Available: {sorted(self._callables)[:10]}..."
            ) from None

    def resolve_or_none(self, name: str) -> Callable | None:
        return self._callables.get(name)

    @classmethod
    def from_callables(cls, callables: dict[str, Callable]) -> PhraseResolver:
        """Create a resolver from an explicit feature→callable mapping.

        Useful for testing without importing real package modules.
        """
        inst = cls.__new__(cls)
        inst._callables = dict(callables)
        return inst


# ---------------------------------------------------------------------------
# CharterExecutor
# ---------------------------------------------------------------------------


def _find_workflow(charter: CompiledCharter, name: str) -> WorkflowNode:
    for w in charter.ast.workflows:
        if w.name == name:
            return w
    raise KeyError(f"Workflow '{name}' not found in charter '{charter.name}'")


def _find_phase(workflow: WorkflowNode, name: str) -> PhaseNode:
    for p in workflow.phases:
        if p.name == name:
            return p
    raise KeyError(f"Phase '{name}' not found in workflow '{workflow.name}'")


def _phase_dependencies(phase: PhaseNode) -> list[str]:
    """Extract phase names this phase depends on (from require phase.passed)."""
    deps: list[str] = []
    for req in phase.requires:
        if isinstance(req.ref, PhaseRefNode):
            deps.append(req.ref.phase)
    return deps


def _build_args(call: FeatureCallNode) -> dict[str, Any]:
    """Convert FeatureCallNode args to a keyword dict.

    Positional args (name is None) are stored with keys
    ``_pos_0``, ``_pos_1``, etc.  Keyword args use their name.
    """
    args: dict[str, Any] = {}
    pos_idx = 0
    for arg in call.args:
        if arg.name is not None:
            args[arg.name] = arg.value
        else:
            args[f"_pos_{pos_idx}"] = arg.value
            pos_idx += 1
    return args


class CharterExecutor:
    """Execute a compiled charter workflow via kron's operation DAG.

    Usage::

        resolver = PhraseResolver(ALL_PACKAGES)
        executor = CharterExecutor(resolver)
        result = await executor.execute(compiled, "pip_workflow", ctx)
    """

    def __init__(self, resolver: PhraseResolver) -> None:
        self.resolver = resolver

    async def execute(
        self,
        charter: CompiledCharter,
        workflow_name: str,
        ctx: Any,
        *,
        max_concurrent: int = 1,
        stop_on_error: bool = True,
    ) -> WorkflowResult:
        """Execute a workflow to completion, return WorkflowResult."""
        workflow = _find_workflow(charter, workflow_name)
        phase_order = charter.phase_order[workflow_name]

        session, shared = self._build_session(
            workflow,
            phase_order,
            ctx,
            stop_on_error,
        )

        graph = self._build_graph(workflow, phase_order)

        results = await flow(
            session,
            graph,
            max_concurrent=max_concurrent,
            stop_on_error=stop_on_error,
        )

        # Merge flow results into shared (flow returns by op name)
        for name, result in results.items():
            if isinstance(result, PhaseResult):
                shared[name] = result

        return WorkflowResult(
            workflow_name=workflow_name,
            charter_name=charter.name,
            phase_results=dict(shared),
        )

    async def stream_execute(
        self,
        charter: CompiledCharter,
        workflow_name: str,
        ctx: Any,
        *,
        max_concurrent: int = 1,
        stop_on_error: bool = True,
    ) -> AsyncGenerator[PhaseResult, None]:
        """Execute a workflow, yielding PhaseResults as phases complete."""
        workflow = _find_workflow(charter, workflow_name)
        phase_order = charter.phase_order[workflow_name]

        session, shared = self._build_session(
            workflow,
            phase_order,
            ctx,
            stop_on_error,
        )

        graph = self._build_graph(workflow, phase_order)

        async for op_result in flow_stream(
            session,
            graph,
            max_concurrent=max_concurrent,
            stop_on_error=stop_on_error,
        ):
            pr = op_result.result
            if isinstance(pr, PhaseResult):
                shared[pr.phase_name] = pr
                yield pr

    # ----- internal --------------------------------------------------------

    def _build_session(
        self,
        workflow: WorkflowNode,
        phase_order: tuple[str, ...],
        ctx: Any,
        stop_on_error: bool,
    ) -> tuple[Session, dict[str, PhaseResult]]:
        """Create a kron Session with registered phase factories."""
        session = Session()
        shared: dict[str, PhaseResult] = {}

        for phase_name in phase_order:
            phase = _find_phase(workflow, phase_name)
            factory = self._make_phase_factory(phase, ctx, shared)
            session.operations.register(
                f"phase.{phase_name}",
                factory,
            )

        return session, shared

    def _build_graph(
        self,
        workflow: WorkflowNode,
        phase_order: tuple[str, ...],
    ):
        """Convert charter phases into a kron Operation DAG."""
        builder = Builder()

        for phase_name in phase_order:
            phase = _find_phase(workflow, phase_name)
            deps = _phase_dependencies(phase)

            builder.add(
                name=phase_name,
                operation=f"phase.{phase_name}",
                parameters={"phase_name": phase_name},
                depends_on=deps or [],
            )

        return builder.build()

    def _make_phase_factory(
        self,
        phase: PhaseNode,
        ctx: Any,
        shared: dict[str, PhaseResult],
    ):
        """Build an async factory closure for a single phase."""
        resolver = self.resolver

        async def factory(_session, _branch, _params):
            require_results: dict[str, Any] = {}
            action_results: dict[str, Any] = {}

            try:
                # --- 1. Evaluate requires ---
                for req in phase.requires:
                    await _eval_require(
                        req,
                        resolver,
                        ctx,
                        shared,
                        require_results,
                    )

                # --- 2. Execute actions ---
                for action in phase.actions:
                    result = await _exec_action(action, resolver, ctx)
                    action_results[action.call.name] = result

                pr = PhaseResult(
                    phase_name=phase.name,
                    passed=True,
                    action_results=action_results,
                    require_results=require_results,
                )

            except PhaseGateError as exc:
                logger.warning("Phase '%s' gate failed: %s", phase.name, exc)
                pr = PhaseResult(
                    phase_name=phase.name,
                    passed=False,
                    action_results=action_results,
                    require_results=require_results,
                    error=str(exc),
                )

            except Exception as exc:
                logger.exception("Phase '%s' unexpected error", phase.name)
                pr = PhaseResult(
                    phase_name=phase.name,
                    passed=False,
                    action_results=action_results,
                    require_results=require_results,
                    error=str(exc),
                )

            shared[phase.name] = pr
            return pr

        return factory


# ---------------------------------------------------------------------------
# Require / Action helpers
# ---------------------------------------------------------------------------


async def _eval_require(
    req: RequireNode,
    resolver: PhraseResolver,
    ctx: Any,
    shared: dict[str, PhaseResult],
    require_results: dict[str, Any],
) -> None:
    """Evaluate a single require statement."""
    ref = req.ref

    if isinstance(ref, PhaseRefNode):
        prev = shared.get(ref.phase)
        if prev is None:
            raise PhaseGateError("unknown", f"phase '{ref.phase}' not yet executed")
        if not prev.passed:
            raise PhaseGateError(ref.phase, f"phase '{ref.phase}' did not pass")
        require_results[f"{ref.phase}.{ref.condition}"] = True

    elif isinstance(ref, FeatureCallNode):
        # Invoke the require phrase at runtime (gate check).
        phrase_fn = resolver.resolve_or_none(ref.name)
        if phrase_fn is not None:
            args = _build_args(ref)
            result = await phrase_fn(args, ctx)
            require_results[ref.name] = result
            # Check standard gate fields (verified / satisfied)
            if isinstance(result, dict):
                if result.get("verified") is False or result.get("satisfied") is False:
                    raise PhaseGateError(
                        ref.name,
                        f"require {ref.name} returned not satisfied",
                    )
        else:
            # Feature validated at compile time but not resolvable
            # (e.g., no callable registered). Record and proceed.
            require_results[ref.name] = "compile_validated_only"

    elif isinstance(ref, BuiltinRefNode):
        if ref.name == "all_phases_passed":
            if not all(pr.passed for pr in shared.values()):
                raise PhaseGateError("builtin", "all_phases_passed: not all phases passed")
            require_results["all_phases_passed"] = True
        else:
            require_results[ref.name] = "unknown_builtin"


async def _exec_action(
    action: ActionNode,
    resolver: PhraseResolver,
    ctx: Any,
) -> Any:
    """Execute a single action (phrase invocation)."""
    call = action.call
    phrase_fn = resolver.resolve(call.name)
    args = _build_args(call)

    logger.debug("Executing action '%s' with args %s", call.name, args)
    result = await phrase_fn(args, ctx)
    return result
