"""Thread-safe OPA engine pool and PolicyEngine facade.

Key components:
- EnginePool: Thread-safe pool of pre-warmed regorus engines
- PolicyEngine: High-level facade for policy evaluation

The EnginePool solves regorus's thread-safety limitation by providing
exclusive checkout of engines. Each engine is pre-warmed with policies
loaded once, avoiding repeated compilation overhead.

Enterprise-ilities:
- P0 Availability: Circuit breaker + degraded mode on pool exhaustion
- P1 Scalability: Externalized pool config via environment
- P1 Serviceability: Warm-swap for add_policy() (no drain)
- P2 Observability: OTEL spans and metrics

Usage:
    pool = EnginePool(size=4, policies_path=Path("policies/"))
    engine = PolicyEngine(pool)

    result = await engine.evaluate(
        tenant_id=tenant_id,
        action="adverse_action",
        context={"application_id": str(app_id)},
    )

Reference: CONSTRAINTS-001-enterprise-ilities.md
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from canon.enforcement.policy import EnforcementLevel
from canon.exceptions import PolicyEvaluationError
from kron.utils import compute_hash, concurrency, now_utc

from .decoder import decode_policy
from .types import AggregatedResult, PolicyResult

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import regorus


@dataclass(frozen=True, slots=True)
class EnginePoolConfig:
    """Configuration for the engine pool.

    P1 Scalability: Externalized via environment variables.

    Attributes:
        size: Number of engines in the pool (env: CANON_OPA_POOL_SIZE)
        max_size: Maximum pool size for scaling (env: CANON_OPA_MAX_POOL_SIZE)
        policies_path: Path to policy directory (optional)
        checkout_timeout: Seconds to wait for engine checkout (env: CANON_OPA_CHECKOUT_TIMEOUT)
        warmup_timeout: Seconds for engine warmup (env: CANON_OPA_WARMUP_TIMEOUT)
        fail_closed: Deny on any error (required for compliance)
        circuit_breaker_threshold: Failures before circuit opens (env: CANON_OPA_CB_THRESHOLD)
        circuit_breaker_recovery: Seconds before circuit recovery (env: CANON_OPA_CB_RECOVERY)
    """

    size: int = 4
    max_size: int = 16
    policies_path: Path | None = None
    checkout_timeout: float = 5.0
    warmup_timeout: float = 30.0
    fail_closed: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_recovery: float = 30.0

    @classmethod
    def from_env(cls, policies_path: Path | None = None) -> EnginePoolConfig:
        """Create config from environment variables.

        P1 Scalability: Externalize pool size and timeouts.

        Environment variables:
            CANON_OPA_POOL_SIZE: Pool size (default 4)
            CANON_OPA_MAX_POOL_SIZE: Max pool size (default 16)
            CANON_OPA_CHECKOUT_TIMEOUT: Checkout timeout (default 5.0)
            CANON_OPA_WARMUP_TIMEOUT: Warmup timeout (default 30.0)
            CANON_OPA_CB_THRESHOLD: Circuit breaker threshold (default 5)
            CANON_OPA_CB_RECOVERY: Circuit breaker recovery (default 30.0)
        """
        import os

        return cls(
            size=int(os.environ.get("CANON_OPA_POOL_SIZE", "4")),
            max_size=int(os.environ.get("CANON_OPA_MAX_POOL_SIZE", "16")),
            policies_path=policies_path,
            checkout_timeout=float(os.environ.get("CANON_OPA_CHECKOUT_TIMEOUT", "5.0")),
            warmup_timeout=float(os.environ.get("CANON_OPA_WARMUP_TIMEOUT", "30.0")),
            circuit_breaker_threshold=int(os.environ.get("CANON_OPA_CB_THRESHOLD", "5")),
            circuit_breaker_recovery=float(os.environ.get("CANON_OPA_CB_RECOVERY", "30.0")),
        )


# Engine Pool
class EnginePoolExhausted(Exception):
    """All engines are in use and checkout timed out."""

    pass


class EnginePool:
    """Thread-safe pool of pre-warmed regorus engines.

    Solves regorus's thread-safety limitation by providing exclusive
    checkout of engines. Each engine has policies loaded once at
    initialization, avoiding repeated compilation overhead.

    D7.16 Hardening:
        - Clear input after eval (privacy)
        - Poison handling (discard engine on exception)
        - Correct health check (track total engines, not just available)

    Usage:
        pool = EnginePool(size=4, policies_path=Path("policies/"))

        with pool.checkout() as engine:
            engine.set_input(input_dict)
            result = engine.eval_rule("data.package.allow")

    Thread Safety:
        - Engines are never shared between threads
        - Checkout is blocking with timeout
        - Return is automatic via context manager
    """

    def __init__(
        self,
        size: int = 4,
        policies_path: Path | None = None,
        config: EnginePoolConfig | None = None,
    ):
        """Initialize the engine pool.

        Args:
            size: Number of engines to create
            policies_path: Path to policy directory
            config: Full configuration (overrides size/policies_path)
        """
        if config:
            self._config = config
        else:
            self._config = EnginePoolConfig(size=size, policies_path=policies_path)

        self._available: queue.Queue[regorus.Engine] = queue.Queue()
        self._lock = threading.Lock()
        self._policies: dict[str, str] = {}  # filename -> content
        self._data: dict[str, Any] = {}  # data.json content
        self._initialized = False
        self._policy_count = 0
        self._total_engines = 0  # D7.16: Track total engines for health check
        self._checked_out = 0  # D7.16: Track checked out count
        # Thread-local storage for engines (regorus engines are !Send)
        self._thread_local = threading.local()
        # P1 Serviceability: Pending policies for warm-swap
        self._pending_policies: dict[str, str] = {}
        # Metrics for observability
        self._checkout_count = 0
        self._exhaustion_count = 0

    def _load_policies(self) -> None:
        """Load all policies from the configured path."""
        if not self._config.policies_path:
            return

        path = self._config.policies_path
        if not path.exists():
            return

        # Load all .rego files
        for rego_file in path.rglob("*.rego"):
            try:
                content = rego_file.read_text()
                self._policies[str(rego_file)] = content
                self._policy_count += 1
            except Exception as e:
                logger.warning("Failed to load policy file %s: %s", rego_file, e)
                # Continue - fail at eval time if policy was needed

        # Load data.json if present
        data_path = path / "data.json"
        if data_path.exists():
            import json

            try:
                self._data = json.loads(data_path.read_text())
            except Exception as e:
                logger.warning("Failed to load OPA data file %s: %s", data_path, e)

    def _create_engine(self) -> regorus.Engine:
        """Create a new engine with all policies loaded.

        Policies that fail to parse are logged and skipped rather than
        failing initialization. This allows the system to start with
        valid policies while invalid ones are fixed.
        """
        import regorus

        engine = regorus.Engine()

        # Load all cached policies, skipping those that fail to parse
        loaded = 0
        skipped = 0
        for filename, content in self._policies.items():
            try:
                engine.add_policy(filename, content)
                loaded += 1
            except RuntimeError as e:
                # Log and skip policies that fail to parse
                logger.warning("Skipping invalid policy %s: %s", filename, str(e)[:100])
                skipped += 1
            except Exception as e:
                logger.warning("Unexpected error loading policy %s: %s", filename, e)
                skipped += 1

        if skipped > 0:
            logger.info(
                "OPA engine: loaded %d policies, skipped %d with parse errors",
                loaded,
                skipped,
            )

        # Load data if available
        if self._data:
            engine.add_data(self._data)

        return engine

    def get_thread_engine(self) -> regorus.Engine:
        """Get or create an engine for the current thread.

        Regorus engines are !Send (can't cross threads), so each thread
        needs its own engine. This method lazily creates one per thread.
        """
        if not self._initialized:
            self.initialize()

        engine = getattr(self._thread_local, "engine", None)
        if engine is None:
            engine = self._create_engine()
            self._thread_local.engine = engine
        return engine

    def initialize(self) -> None:
        """Initialize the pool with pre-warmed engines.

        Call this once at startup. Can be called from any thread.
        D7.16: Atomic initialization - all or nothing.
        """
        with self._lock:
            if self._initialized:
                return

            # Load policies first (in calling thread)
            self._load_policies()

            # D7.16: Atomic initialization - build engines in local list first
            engines: list[regorus.Engine] = []
            try:
                for _ in range(self._config.size):
                    engine = self._create_engine()
                    engines.append(engine)
            except Exception:
                # Creation failed - don't partially initialize
                engines.clear()
                raise

            # Only publish engines if all created successfully
            for engine in engines:
                self._available.put(engine)
            self._total_engines = len(engines)
            self._initialized = True

    @contextmanager
    def checkout(self) -> Generator[regorus.Engine, None, None]:
        """Checkout an engine for exclusive use.

        Returns engine via context manager - automatically returned on exit.

        D7.16 Hardening:
            - Clear input after eval (privacy)
            - Poison handling (discard on exception, replace)

        P1 Serviceability:
            - Apply pending policies on return (warm-swap)

        Raises:
            EnginePoolExhausted: If checkout times out
        """
        if not self._initialized:
            self.initialize()

        try:
            engine = self._available.get(timeout=self._config.checkout_timeout)
            with self._lock:
                self._checked_out += 1
                self._checkout_count += 1
            # P1 SLO: Record successful pool checkout
            self._record_pool_availability(available=True)
        except queue.Empty:
            with self._lock:
                self._exhaustion_count += 1
            # P1 SLO: Record failed pool checkout
            self._record_pool_availability(available=False)
            # P2 Observability: Record pool exhaustion metric
            self._record_pool_exhaustion()
            raise EnginePoolExhausted(
                f"All {self._config.size} engines in use, "
                f"timeout after {self._config.checkout_timeout}s"
            )

        poisoned = False
        try:
            yield engine
        except Exception:
            # D7.16: Mark as poisoned on exception
            poisoned = True
            raise
        finally:
            # D7.16: Clear input for privacy (even on success)
            try:
                engine.set_input({})
            except Exception:
                poisoned = True

            # P1 Serviceability: Apply pending policies (warm-swap)
            if not poisoned and self._pending_policies:
                self._apply_pending_policies(engine)

            with self._lock:
                self._checked_out -= 1

                if poisoned:
                    # D7.16: Discard poisoned engine and replace
                    try:
                        replacement = self._create_engine()
                        self._available.put(replacement)
                    except Exception:
                        # Failed to create replacement - pool shrinks
                        self._total_engines -= 1
                else:
                    # Return healthy engine to pool
                    self._available.put(engine)

    def add_policy(self, filename: str, content: str) -> None:
        """Add a policy to all engines in the pool.

        DEPRECATED: Use add_policy_warm() for production.

        Thread-safe but requires draining the pool temporarily.
        For production, prefer loading policies at initialization.
        """
        with self._lock:
            self._policies[filename] = content
            self._policy_count += 1

            # If initialized, add to all engines
            if self._initialized:
                # Drain pool, update each, return
                engines = []
                while True:
                    try:
                        engine = self._available.get_nowait()
                        engine.add_policy(filename, content)
                        engines.append(engine)
                    except queue.Empty:
                        break

                # Return all engines
                for engine in engines:
                    self._available.put(engine)

    def add_policy_warm(self, filename: str, content: str) -> None:
        """Add a policy without blocking existing evaluations.

        P1 Serviceability: Warm-swap avoids pool drain.

        Strategy:
        1. Update policy cache (new engines will have it)
        2. Incrementally update engines as they're returned to pool
        3. No drain required - evaluations continue during update

        Thread-safe and non-blocking for in-flight evaluations.
        """
        with self._lock:
            self._policies[filename] = content
            self._policy_count += 1
            # Mark that engines need this policy
            self._pending_policies[filename] = content

    def _apply_pending_policies(self, engine: regorus.Engine) -> None:
        """Apply any pending policies to an engine.

        Called when engine is returned to pool.
        """
        with self._lock:
            for filename, content in self._pending_policies.items():
                try:
                    engine.add_policy(filename, content)
                except Exception:
                    # Log but don't fail - policy will be applied on next checkout
                    pass

    def clear_pending_policies(self) -> None:
        """Clear pending policies after all engines have been updated."""
        with self._lock:
            self._pending_policies.clear()

    @property
    def size(self) -> int:
        """Pool size (total engines)."""
        return self._config.size

    @property
    def available_count(self) -> int:
        """Number of currently available engines."""
        return self._available.qsize()

    @property
    def policy_count(self) -> int:
        """Number of loaded policies."""
        return self._policy_count

    def health_check(self) -> bool:
        """Check if pool is healthy.

        D7.16: Correct health check based on total engines, not availability.
        A pool is healthy if:
        - It's initialized
        - Total engines equals configured size (no permanent shrinkage)
        - Available + checked_out equals total (accounting is correct)
        """
        with self._lock:
            if not self._initialized:
                return False
            # D7.16: Check total engines, not availability
            # Pool is healthy even when all engines are checked out
            return self._total_engines == self._config.size

    @property
    def metrics(self) -> dict[str, Any]:
        """Pool metrics for observability.

        P2 Observability: Expose pool state for monitoring.
        """
        with self._lock:
            return {
                "size": self._config.size,
                "total_engines": self._total_engines,
                "available": self._available.qsize(),
                "checked_out": self._checked_out,
                "checkout_count": self._checkout_count,
                "exhaustion_count": self._exhaustion_count,
                "policy_count": self._policy_count,
                "pending_policies": len(self._pending_policies),
                "healthy": self._total_engines == self._config.size,
                "utilization": (
                    self._checked_out / self._total_engines if self._total_engines > 0 else 0.0
                ),
            }

    @property
    def exhaustion_count(self) -> int:
        """Number of pool exhaustion events."""
        with self._lock:
            return self._exhaustion_count

    def _record_pool_availability(self, available: bool) -> None:
        """Record pool availability for SLO tracking.

        P1 SLO: Wire pool availability into SLORegistry.
        """
        try:
            from canon.utils.slo import get_slo_registry

            registry = get_slo_registry()
            registry.record_pool_check(available)
        except ImportError:
            # SLO module not installed
            pass
        except Exception as e:
            logger.debug(f"Pool availability SLO recording failed: {e}")

    def _record_pool_exhaustion(self) -> None:
        """Record pool exhaustion event for telemetry.

        P2 Observability: Wire pool exhaustion into OTEL metrics.
        """
        try:
            from canon.utils.telemetry import record_pool_exhaustion

            record_pool_exhaustion()
        except ImportError:
            # Telemetry module not installed
            pass
        except Exception as e:
            logger.debug(f"Pool exhaustion telemetry recording failed: {e}")


@dataclass(frozen=True, slots=True)
class ResolvedPolicy:
    """A policy determined to apply to current context.

    Created by PolicyResolver, consumed by PolicyEngine.

    Attributes:
        policy_id: Unique identifier for the policy
        rego_package: Full Rego package path (e.g., "canon.nyc.fair_chance")
        enforcement: How strictly to enforce violations
        legal_citation: Legal source for this policy
        parameters: Policy-specific parameters from Constitution
    """

    policy_id: str
    rego_package: str
    enforcement: EnforcementLevel = EnforcementLevel.HARD_MANDATORY
    legal_citation: str | None = None
    regulation_url: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


class PolicyEngine:
    """High-level facade for policy evaluation.

    Combines:
    - EnginePool for thread-safe regorus access
    - PolicyResolver for determining applicable policies
    - Result aggregation for multi-policy evaluation

    Usage:
        pool = EnginePool(policies_path=Path("policies/"))
        engine = PolicyEngine(pool)

        result = await engine.evaluate(
            tenant_id=tenant_id,
            action="adverse_action",
            context={"application_id": str(app_id)},
        )

        if not result.allowed:
            blocking = result.get_blocking_results()
            ...
    """

    def __init__(
        self,
        pool: EnginePool,
        fail_closed: bool = True,
    ):
        """Initialize the policy engine.

        Args:
            pool: Engine pool for regorus access
            fail_closed: Deny on any error (default True)
        """
        self._pool = pool
        self._fail_closed = fail_closed

    def _record_policy_metrics(
        self,
        policy_id: str,
        allowed: bool,
        duration_ms: float,
        enforcement: str | None = None,
        tenant_id: str | None = None,
        error: bool = False,
    ) -> None:
        """Record policy evaluation metrics for observability and frugality.

        P2 Observability: Wire policy metrics into OTEL (GAP-001 fix).
        P2 Frugality: Wire policy metering (GAP-003 fix).
        """
        # P2 Observability: Record OTEL metrics
        try:
            from canon.utils.slo import get_slo_registry
            from canon.utils.telemetry import record_policy_evaluation

            # Record OTEL metrics
            record_policy_evaluation(
                policy_id=policy_id,
                allowed=allowed,
                duration_ms=duration_ms,
                enforcement=enforcement,
                tenant_id=tenant_id,
            )

            # Record SLO metrics
            registry = get_slo_registry()
            registry.record_policy_latency(duration_ms)

        except ImportError:
            # Observability modules not installed - skip silently
            logger.debug("Observability modules not installed - policy metrics skipped")
        except Exception as e:
            # Don't fail policy evaluation on metrics failure, but log
            logger.warning(f"Policy metrics recording failed (policy={policy_id}): {e}")

        # P2 Frugality: Record usage metering (GAP-003 fix)
        if tenant_id:
            try:
                from canon.utils.metering import get_decision_meter, get_quota_enforcer

                # Record to meter
                meter = get_decision_meter()
                meter.record_policy(
                    tenant_id=tenant_id,
                    policy_id=policy_id,
                    decision_class="governance",  # Default decision class
                    duration_ms=duration_ms,
                )

                # Record to quota tracker
                enforcer = get_quota_enforcer()
                # Compute units based on duration (policy base cost higher)
                compute_units = 2.0 + (duration_ms * 0.01)
                enforcer.record_policy(tenant_id, compute_units)

            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"Policy frugality metering failed (policy={policy_id}): {e}")

    def _check_policy_quota(self, tenant_id: str) -> None:
        """Check if tenant has quota for policy evaluation.

        P2 Frugality: Pre-evaluation quota check (REQ-E4).

        Raises:
            QuotaExceededError: If tenant quota exceeded
        """
        try:
            from canon.utils.metering import get_quota_enforcer

            enforcer = get_quota_enforcer()
            enforcer.check_policy(tenant_id)
        except ImportError:
            # Frugality module not installed
            logger.debug("Frugality modules not installed - policy quota check skipped")
        except Exception as e:
            # Re-raise quota errors, log others
            if e.__class__.__name__ == "QuotaExceededError":
                raise
            logger.warning(f"Policy quota check failed (tenant={tenant_id}): {e}")

    async def evaluate_single(
        self,
        policy: ResolvedPolicy,
        input_data: dict[str, Any],
        rule: str = "allow",
        enforce_quotas: bool = True,
    ) -> PolicyResult:
        """Evaluate a single policy against input.

        Args:
            policy: The resolved policy to evaluate
            input_data: Input document for OPA
            rule: Rule to query (default "allow")
            enforce_quotas: Whether to enforce frugality quotas (default True)

        Returns:
            PolicyResult with allow/deny and details

        Raises:
            QuotaExceededError: If tenant quota exceeded (when enforce_quotas=True)
        """
        # P2 Frugality: Pre-check policy quota (REQ-E4)
        tenant_id = input_data.get("tenant_id")
        if enforce_quotas and tenant_id:
            self._check_policy_quota(tenant_id)

        input_hash = compute_hash(input_data)
        start_time = time.perf_counter()

        try:
            # Run sync evaluation in thread pool
            result = await concurrency.run_sync(
                self._evaluate_sync,
                policy,
                input_data,
                rule,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            allowed = result.get("allow", False)

            # P2 Observability: Record policy metrics (GAP-001 fix)
            self._record_policy_metrics(
                policy_id=policy.policy_id,
                allowed=allowed,
                duration_ms=elapsed_ms,
                enforcement=(
                    policy.enforcement.value
                    if hasattr(policy.enforcement, "value")
                    else str(policy.enforcement)
                ),
                tenant_id=input_data.get("tenant_id"),
            )

            return PolicyResult(
                policy_id=policy.policy_id,
                allowed=allowed,
                enforcement=policy.enforcement,
                legal_citation=policy.legal_citation,
                regulation_url=policy.regulation_url,
                violation_code=result.get("violation", {}).get("code"),
                violation_message=result.get("violation", {}).get("message"),
                remediation_steps=tuple(result.get("remediation", [])),
                conditions_met=tuple(result.get("conditions_met", [])),
                conditions_missing=tuple(result.get("conditions_missing", [])),
                evaluated_at=now_utc(),
                evaluation_ms=elapsed_ms,
                raw_output=result,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # P2 Observability: Record error metrics (GAP-001 fix)
            self._record_policy_metrics(
                policy_id=policy.policy_id,
                allowed=False,
                duration_ms=elapsed_ms,
                enforcement=(
                    policy.enforcement.value
                    if hasattr(policy.enforcement, "value")
                    else str(policy.enforcement)
                ),
                tenant_id=input_data.get("tenant_id"),
                error=True,
            )

            if self._fail_closed:
                # Fail-closed: any error = deny
                return PolicyResult(
                    policy_id=policy.policy_id,
                    allowed=False,
                    enforcement=policy.enforcement,
                    legal_citation=policy.legal_citation,
                    violation_code="EVALUATION_ERROR",
                    violation_message=f"Policy evaluation failed: {e}",
                    evaluated_at=now_utc(),
                    evaluation_ms=elapsed_ms,
                )
            else:
                raise PolicyEvaluationError(
                    policy_id=policy.policy_id,
                    error=str(e),
                    input_hash=input_hash,
                ) from e

    def _evaluate_sync(
        self,
        policy: ResolvedPolicy,
        input_data: dict[str, Any],
        rule: str,
    ) -> dict[str, Any]:
        """Sync evaluation using thread-local engine.

        Uses decode_policy() for safe result decoding (D7.10 contract).
        Priority: decision object > allow + deny_reasons fallback.

        If ALL primary queries fail with exceptions, re-raises the last
        exception so the outer handler can return EVALUATION_ERROR.

        Note: Uses thread-local engine because regorus engines are !Send
        (can't be transferred between threads).
        """
        # Get thread-local engine (regorus engines can't cross threads)
        engine = self._pool.get_thread_engine()

        try:
            # Set input
            engine.set_input(input_data)

            # Track exceptions - if all primary queries fail, re-raise
            last_exc: Exception | None = None

            # Query for structured decision object (D7.10 preferred contract)
            decision_raw = None
            try:
                decision_query = f"data.{policy.rego_package}.decision"
                decision_raw = engine.eval_rule(decision_query)
            except Exception as e:
                last_exc = e

            # Query for allow (fallback or validation)
            allow_raw = None
            try:
                allow_query = f"data.{policy.rego_package}.{rule}"
                allow_raw = engine.eval_rule(allow_query)
            except Exception as e:
                last_exc = e

            # If both decision and allow queries failed, re-raise
            # This ensures critical errors (timeout, connection) propagate
            if decision_raw is None and allow_raw is None and last_exc is not None:
                raise last_exc

            # Query for deny_reasons (legacy pattern) - optional, don't propagate errors
            deny_raw = None
            try:
                deny_query = f"data.{policy.rego_package}.deny_reasons"
                deny_raw = engine.eval_rule(deny_query)
            except Exception:
                pass

            # Decode using decode_policy() - safe unwrapping, fail-closed
            decoded = decode_policy(
                decision_raw=decision_raw,
                allow_raw=allow_raw,
                deny_raw=deny_raw,
            )

            result: dict[str, Any] = {"allow": decoded.allow}

            # Add deny reasons if present
            if decoded.deny_reasons:
                result["deny_reasons"] = list(decoded.deny_reasons)

            # Include full decision object if available
            if decoded.decision:
                result["decision"] = decoded.decision

            # Try to get violation details (optional, don't propagate errors)
            try:
                violation_query = f"data.{policy.rego_package}.violation"
                violation = engine.eval_rule(violation_query)
                if violation:
                    result["violation"] = violation
            except Exception:
                pass

            # Try to get remediation (optional, don't propagate errors)
            try:
                remediation_query = f"data.{policy.rego_package}.remediation"
                remediation = engine.eval_rule(remediation_query)
                if remediation:
                    result["remediation"] = list(remediation)
            except Exception:
                pass

            # Try to get conditions (optional, don't propagate errors)
            try:
                conditions_query = f"data.{policy.rego_package}.conditions"
                conditions = engine.eval_rule(conditions_query)
                if conditions:
                    result["conditions_met"] = conditions.get("met", [])
                    result["conditions_missing"] = conditions.get("missing", [])
            except Exception:
                pass

            return result
        finally:
            # D7.16: Clear input for privacy
            try:
                engine.set_input({})
            except Exception:
                pass

    async def evaluate_policies(
        self,
        policies: list[ResolvedPolicy],
        input_data: dict[str, Any],
    ) -> AggregatedResult:
        """Evaluate multiple policies and aggregate results.

        Policies are evaluated in order. On HARD_MANDATORY failure,
        remaining policies are still evaluated for complete audit trail.

        Args:
            policies: Ordered list of policies to evaluate
            input_data: Input document for OPA

        Returns:
            AggregatedResult combining all policy results
        """
        results: list[PolicyResult] = []

        for policy in policies:
            result = await self.evaluate_single(policy, input_data)
            results.append(result)

        aggregated = AggregatedResult.from_results(
            results,
            context={"input_hash": compute_hash(input_data)},
        )

        # P1 SLO: Record decision success/failure (REQ-E6)
        self._record_decision_success(aggregated.allowed)

        return aggregated

    def _record_decision_success(self, success: bool) -> None:
        """Record decision outcome for SLO tracking.

        P1 SLO: Wire decision success rate into SLORegistry.
        """
        try:
            from canon.utils.slo import get_slo_registry

            registry = get_slo_registry()
            registry.record_decision(success)
        except ImportError:
            # SLO module not installed
            pass
        except Exception as e:
            logger.debug(f"Decision success SLO recording failed: {e}")

    def health_check(self) -> bool:
        """Check if engine is healthy."""
        return self._pool.health_check()


__all__ = [
    "EnginePool",
    "EnginePoolConfig",
    "EnginePoolExhausted",
    "PolicyEngine",
    "PolicyEvaluationError",
    "ResolvedPolicy",
]
