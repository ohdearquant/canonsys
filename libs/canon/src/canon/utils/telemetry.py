"""OpenTelemetry integration for Canon governance.

P2 Fix: Observability - OTEL spans + Prometheus metrics

Provides distributed tracing and metrics export for:
- Gate evaluations (latency, pass/block, degraded)
- Policy evaluations (latency, allowed/denied, enforcement level)
- Engine pool status (utilization, exhaustion, health)
- Decision attribution (tenant, decision class, cost units)

Usage:
    from canon.utils.telemetry import init_telemetry, gate_span, record_gate_evaluation

    # Initialize at startup
    init_telemetry(service_name="canon-core", otlp_endpoint="http://localhost:4317")

    # Use in gate evaluation
    async def check(self, ctx: RequestContext) -> GateResult:
        with gate_span(self.gate_id, ctx.tenant_id) as span:
            result = await self._evaluate(ctx)
            span.set_attribute("gate.passed", result.passed)
            record_gate_evaluation(self.gate_id, result.passed, elapsed_ms)
            return result

Reference: CONSTRAINTS-001-enterprise-ilities.md §7
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

# Conditional imports - OTEL is optional
try:
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.semconv.resource import ResourceAttributes

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore
    metrics = None  # type: ignore

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter, Histogram, Meter, ObservableGauge
    from opentelemetry.trace import Span, Tracer


@dataclass
class CanonTelemetry:
    """Centralized telemetry configuration and access.

    Provides tracer and meter for governance instrumentation.
    Falls back to no-op if OTEL not installed.
    """

    service_name: str = "canon-core"
    service_version: str = "1.0.0"
    otlp_endpoint: str | None = None
    enabled: bool = True

    # Internals
    _tracer: Tracer | None = field(default=None, init=False, repr=False)
    _meter: Meter | None = field(default=None, init=False, repr=False)
    _initialized: bool = field(default=False, init=False)

    # Metrics instruments
    _gate_duration: Histogram | None = field(default=None, init=False, repr=False)
    _gate_total: Counter | None = field(default=None, init=False, repr=False)
    _policy_duration: Histogram | None = field(default=None, init=False, repr=False)
    _policy_total: Counter | None = field(default=None, init=False, repr=False)
    _pool_utilization: ObservableGauge | None = field(default=None, init=False, repr=False)
    _decisions_total: Counter | None = field(default=None, init=False, repr=False)
    _pool_exhaustion_total: Counter | None = field(default=None, init=False, repr=False)

    def initialize(self) -> None:
        """Initialize OTEL providers and instruments."""
        if self._initialized or not self.enabled:
            return

        if not OTEL_AVAILABLE:
            self._initialized = True
            return

        # Create resource
        resource = Resource.create(
            {
                ResourceAttributes.SERVICE_NAME: self.service_name,
                ResourceAttributes.SERVICE_VERSION: self.service_version,
            }
        )

        # Initialize tracer
        tracer_provider = TracerProvider(resource=resource)
        if self.otlp_endpoint:
            span_exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint)
            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)
        self._tracer = trace.get_tracer("canon.governance", self.service_version)

        # Initialize meter
        if self.otlp_endpoint:
            metric_exporter = OTLPMetricExporter(endpoint=self.otlp_endpoint)
            metric_reader = PeriodicExportingMetricReader(metric_exporter)
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        else:
            meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(meter_provider)
        self._meter = metrics.get_meter("canon.governance", self.service_version)

        # Create instruments
        self._create_instruments()
        self._initialized = True

    def _create_instruments(self) -> None:
        """Create metric instruments."""
        if not self._meter:
            return

        # Gate metrics
        self._gate_duration = self._meter.create_histogram(
            name="canon.gate.duration_ms",
            unit="ms",
            description="Gate evaluation latency in milliseconds",
        )
        self._gate_total = self._meter.create_counter(
            name="canon.gate.evaluations_total",
            unit="1",
            description="Total gate evaluations by outcome",
        )

        # Policy metrics
        self._policy_duration = self._meter.create_histogram(
            name="canon.policy.duration_ms",
            unit="ms",
            description="Policy evaluation latency in milliseconds",
        )
        self._policy_total = self._meter.create_counter(
            name="canon.policy.evaluations_total",
            unit="1",
            description="Total policy evaluations by outcome",
        )

        # Decision metrics
        self._decisions_total = self._meter.create_counter(
            name="canon.decisions_total",
            unit="1",
            description="Total governance decisions",
        )

        # Pool metrics
        self._pool_exhaustion_total = self._meter.create_counter(
            name="canon.pool.exhaustion_total",
            unit="1",
            description="Engine pool exhaustion events",
        )

    @property
    def tracer(self) -> Tracer | None:
        """Get tracer, initializing if needed."""
        if not self._initialized:
            self.initialize()
        return self._tracer

    @property
    def meter(self) -> Meter | None:
        """Get meter, initializing if needed."""
        if not self._initialized:
            self.initialize()
        return self._meter


# Singleton instance
_telemetry: CanonTelemetry | None = None


def get_telemetry() -> CanonTelemetry:
    """Get singleton telemetry instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = CanonTelemetry()
    return _telemetry


def init_telemetry(
    service_name: str = "canon-core",
    service_version: str = "1.0.0",
    otlp_endpoint: str | None = None,
    enabled: bool = True,
) -> CanonTelemetry:
    """Initialize telemetry with configuration.

    Call once at application startup.

    Args:
        service_name: Service name for OTEL resource
        service_version: Service version for OTEL resource
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        enabled: Whether to enable telemetry

    Returns:
        Configured CanonTelemetry instance
    """
    global _telemetry
    _telemetry = CanonTelemetry(
        service_name=service_name,
        service_version=service_version,
        otlp_endpoint=otlp_endpoint,
        enabled=enabled,
    )
    _telemetry.initialize()
    return _telemetry


# =============================================================================
# Span Context Managers
# =============================================================================


class NoOpSpan:
    """No-op span when OTEL is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: BaseException) -> None:
        pass

    def __enter__(self) -> NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


@contextmanager
def gate_span(
    gate_id: str,
    tenant_id: str | None = None,
    **attributes: Any,
) -> Generator[Span | NoOpSpan, None, None]:
    """Create a span for gate evaluation.

    Usage:
        with gate_span("consent.background_check", tenant_id) as span:
            result = await gate.check(ctx)
            span.set_attribute("gate.passed", result.passed)
    """
    telemetry = get_telemetry()
    tracer = telemetry.tracer

    if not tracer:
        yield NoOpSpan()
        return

    with tracer.start_as_current_span("gate.evaluate") as span:
        span.set_attribute("gate.id", gate_id)
        if tenant_id:
            span.set_attribute("tenant.id", tenant_id)
        for key, value in attributes.items():
            span.set_attribute(f"gate.{key}", value)
        yield span


@contextmanager
def policy_span(
    policy_id: str,
    tenant_id: str | None = None,
    enforcement: str | None = None,
    **attributes: Any,
) -> Generator[Span | NoOpSpan, None, None]:
    """Create a span for policy evaluation.

    Usage:
        with policy_span("nyc_fair_chance", tenant_id, enforcement="hard_mandatory") as span:
            result = await engine.evaluate_single(policy, input_data)
            span.set_attribute("policy.allowed", result.allowed)
    """
    telemetry = get_telemetry()
    tracer = telemetry.tracer

    if not tracer:
        yield NoOpSpan()
        return

    with tracer.start_as_current_span("policy.evaluate") as span:
        span.set_attribute("policy.id", policy_id)
        if tenant_id:
            span.set_attribute("tenant.id", tenant_id)
        if enforcement:
            span.set_attribute("policy.enforcement", enforcement)
        for key, value in attributes.items():
            span.set_attribute(f"policy.{key}", value)
        yield span


@contextmanager
def decision_span(
    decision_scope: str,
    tenant_id: str | None = None,
    decision_class: str | None = None,
    **attributes: Any,
) -> Generator[Span | NoOpSpan, None, None]:
    """Create a span for a governance decision.

    Usage:
        with decision_span("adverse_action", tenant_id, decision_class="hr") as span:
            result = await engine.evaluate_policies(policies, input_data)
            span.set_attribute("decision.allowed", result.allowed)
    """
    telemetry = get_telemetry()
    tracer = telemetry.tracer

    if not tracer:
        yield NoOpSpan()
        return

    with tracer.start_as_current_span("decision.evaluate") as span:
        span.set_attribute("decision.scope", decision_scope)
        if tenant_id:
            span.set_attribute("tenant.id", tenant_id)
        if decision_class:
            span.set_attribute("decision.class", decision_class)
        for key, value in attributes.items():
            span.set_attribute(f"decision.{key}", value)
        yield span


# =============================================================================
# Metric Recording
# =============================================================================


def record_gate_evaluation(
    gate_id: str,
    passed: bool,
    duration_ms: float,
    tenant_id: str | None = None,
    degraded: bool = False,
) -> None:
    """Record gate evaluation metrics.

    Args:
        gate_id: Gate identifier
        passed: Whether gate passed
        duration_ms: Evaluation duration in milliseconds
        tenant_id: Optional tenant identifier
        degraded: Whether result was from degraded mode (fail-open)
    """
    telemetry = get_telemetry()
    if not telemetry._gate_duration or not telemetry._gate_total:
        return

    attributes = {
        "gate.id": gate_id,
        "gate.outcome": "passed" if passed else "blocked",
        "gate.degraded": str(degraded).lower(),
    }
    if tenant_id:
        attributes["tenant.id"] = tenant_id

    telemetry._gate_duration.record(duration_ms, attributes)
    telemetry._gate_total.add(1, attributes)


def record_policy_evaluation(
    policy_id: str,
    allowed: bool,
    duration_ms: float,
    enforcement: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Record policy evaluation metrics.

    Args:
        policy_id: Policy identifier
        allowed: Whether policy allowed the action
        duration_ms: Evaluation duration in milliseconds
        enforcement: Enforcement level (hard_mandatory, soft_mandatory, advisory)
        tenant_id: Optional tenant identifier
    """
    telemetry = get_telemetry()
    if not telemetry._policy_duration or not telemetry._policy_total:
        return

    attributes = {
        "policy.id": policy_id,
        "policy.outcome": "allowed" if allowed else "denied",
    }
    if enforcement:
        attributes["policy.enforcement"] = enforcement
    if tenant_id:
        attributes["tenant.id"] = tenant_id

    telemetry._policy_duration.record(duration_ms, attributes)
    telemetry._policy_total.add(1, attributes)


def record_pool_metrics(
    pool_size: int,
    available: int,
    checked_out: int,
    healthy: bool,
) -> None:
    """Record engine pool metrics.

    Args:
        pool_size: Total pool size
        available: Available engines
        checked_out: Checked out engines
        healthy: Whether pool is healthy
    """
    # Pool metrics are typically recorded via observable gauge callbacks
    # This function is for manual recording if needed
    pass


def record_pool_exhaustion(tenant_id: str | None = None) -> None:
    """Record pool exhaustion event.

    Args:
        tenant_id: Optional tenant identifier
    """
    telemetry = get_telemetry()
    if not telemetry._pool_exhaustion_total:
        return

    attributes = {}
    if tenant_id:
        attributes["tenant.id"] = tenant_id

    telemetry._pool_exhaustion_total.add(1, attributes)


def record_decision(
    decision_scope: str,
    allowed: bool,
    tenant_id: str | None = None,
    decision_class: str | None = None,
    degraded: bool = False,
) -> None:
    """Record governance decision metrics.

    Args:
        decision_scope: Decision scope (e.g., "adverse_action")
        allowed: Whether decision was allowed
        tenant_id: Optional tenant identifier
        decision_class: Optional decision class for attribution
        degraded: Whether decision was made in degraded mode
    """
    telemetry = get_telemetry()
    if not telemetry._decisions_total:
        return

    attributes = {
        "decision.scope": decision_scope,
        "decision.outcome": "allowed" if allowed else "blocked",
        "decision.degraded": str(degraded).lower(),
    }
    if tenant_id:
        attributes["tenant.id"] = tenant_id
    if decision_class:
        attributes["decision.class"] = decision_class

    telemetry._decisions_total.add(1, attributes)
