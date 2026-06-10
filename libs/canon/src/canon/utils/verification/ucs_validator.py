"""UCS-v1 certificate validator wrapping ucs_validator.rego via PolicyEngine.

Provides Python interface to the OPA/Rego UCS validator with:
- ValidationStatus enum: APPROVED | BLOCKED | ESCALATION_REQUIRED
- ValidationResult dataclass with status, reason, details
- Fail-closed semantics (any error = BLOCKED)

Usage:
    pool = EnginePool(policies_path=Path("validators/opa/"))
    engine = PolicyEngine(pool)
    provider = UCSDataProvider()

    validator = UCSValidator(engine, provider)
    result = validator.validate_certificate(ucs_dict)

    if result.status == ValidationStatus.BLOCKED:
        raise CertificateBlocked(result.reason)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from canon.utils.opa.engine import ResolvedPolicy
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.utils.opa.engine import PolicyEngine
    from canon.utils.verification.opa_data_provider import UCSDataProvider


class ValidationStatus(str, Enum):
    """UCS certificate validation status.

    APPROVED: Certificate passes all checks, action may proceed.
    BLOCKED: Certificate fails validation, action must not proceed.
    ESCALATION_REQUIRED: Certificate requires human review before proceeding.
    """

    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result from UCS certificate validation.

    Attributes:
        status: Validation outcome (APPROVED, BLOCKED, or ESCALATION_REQUIRED).
        reason: Human-readable explanation of the result.
        details: Additional context from OPA evaluation (conditions, checks, etc.).
        evaluated_at: When validation was performed.
        evaluation_ms: How long validation took in milliseconds.
    """

    status: ValidationStatus
    reason: str
    details: dict[str, Any] = field(default_factory=dict)
    evaluated_at: datetime = field(default_factory=now_utc)
    evaluation_ms: float = 0.0

    @property
    def is_approved(self) -> bool:
        """Whether certificate is approved for action."""
        return self.status == ValidationStatus.APPROVED

    @property
    def is_blocked(self) -> bool:
        """Whether certificate is blocked."""
        return self.status == ValidationStatus.BLOCKED

    @property
    def requires_escalation(self) -> bool:
        """Whether certificate requires human escalation."""
        return self.status == ValidationStatus.ESCALATION_REQUIRED


# ResolvedPolicy for ucs.validator Rego package
_UCS_POLICY = ResolvedPolicy(
    policy_id="ucs.validator",
    rego_package="ucs.validator",
)


class UCSValidator:
    """Validates UCS-v1 certificates via OPA/Rego policy engine.

    Wraps ucs_validator.rego, providing Python-native interface with:
    - Type-safe ValidationStatus enum
    - Structured ValidationResult with reason and details
    - Fail-closed semantics (any error = BLOCKED)

    The validator requires:
    1. PolicyEngine with ucs_validator.rego loaded
    2. UCSDataProvider populated with CEPs and signing keys

    Architecture:
        UCS dict -> UCSValidator -> PolicyEngine -> ucs.validator.rego
                                         |
                              UCSDataProvider.build_opa_data() -> data context

    Example:
        provider = UCSDataProvider()
        provider.add_cep("cep-123", hash="abc...", cep_type="POLICY_SIGN_OFF")
        provider.add_signing_key("key-456", valid_from_utc=datetime(...))

        validator = UCSValidator(engine, provider)
        result = await validator.validate_certificate(ucs_dict)

        match result.status:
            case ValidationStatus.APPROVED:
                proceed_with_action()
            case ValidationStatus.BLOCKED:
                raise CertificateBlocked(result.reason)
            case ValidationStatus.ESCALATION_REQUIRED:
                route_to_human_review(result)
    """

    def __init__(
        self,
        engine: PolicyEngine,
        data_provider: UCSDataProvider,
    ) -> None:
        """Initialize UCS validator.

        Args:
            engine: PolicyEngine with ucs_validator.rego loaded.
            data_provider: UCSDataProvider for CEPs and signing keys.
        """
        self._engine = engine
        self._data_provider = data_provider

    async def validate_certificate(
        self,
        certificate: dict[str, Any],
    ) -> ValidationResult:
        """Validate a UCS-v1 certificate.

        Evaluates the certificate against ucs_validator.rego with data context
        from the configured UCSDataProvider.

        Args:
            certificate: UCS-v1 certificate dict with meta, context, authority,
                        assertions, evidence_pointers, and seal blocks.

        Returns:
            ValidationResult with status, reason, and details.

        Note:
            Fail-closed semantics: any evaluation error returns BLOCKED status.
            This is required for compliance-critical validation.
        """
        import time

        start_time = time.perf_counter()

        try:
            # Build OPA data context and inject into pool
            opa_data = self._data_provider.build_opa_data()
            self._inject_data_into_pool(opa_data)

            # Evaluate via PolicyEngine
            result = await self._engine.evaluate_single(
                policy=_UCS_POLICY,
                input_data=certificate,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Map PolicyResult to ValidationResult
            return self._map_policy_result(result, elapsed_ms)

        except Exception as e:
            # Fail-closed: any error = BLOCKED
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return ValidationResult(
                status=ValidationStatus.BLOCKED,
                reason=f"Validation error: {e}",
                details={"error": str(e), "error_type": type(e).__name__},
                evaluated_at=now_utc(),
                evaluation_ms=elapsed_ms,
            )

    def _inject_data_into_pool(self, opa_data: dict[str, Any]) -> None:
        """Inject OPA data context into the engine pool.

        Updates the pool's shared data which is loaded into all engines.
        This is thread-safe as it updates the pool's _data dict and
        re-initializes engines with the new data on next checkout.

        For per-evaluation data (CEPs, signing_keys), this should be called
        before each validate_certificate() call with fresh data.

        Args:
            opa_data: Dict with roles, ceps, signing_keys for OPA evaluation.
        """
        pool = self._engine._pool

        # Update pool's internal data dict
        # This affects newly created engines and add_data calls
        if hasattr(pool, "_data"):
            pool._data.update(opa_data)

        # For already-initialized thread-local engines, we need to add data
        # directly. This is done lazily when get_thread_engine() is called.
        # Since thread-local engines are created per-thread, and we're about
        # to evaluate (which will use the same thread via to_thread), the
        # data injection happens at evaluation time in _evaluate_sync.
        #
        # Note: For production, consider using EnginePool.add_data_to_all()
        # or similar method if concurrent evaluations need fresh data.

    def validate_certificate_sync(
        self,
        certificate: dict[str, Any],
    ) -> ValidationResult:
        """Synchronous wrapper for validate_certificate.

        Convenience method for non-async contexts. Runs the async validation
        in an event loop.

        Args:
            certificate: UCS-v1 certificate dict.

        Returns:
            ValidationResult with status, reason, and details.
        """
        return asyncio.get_event_loop().run_until_complete(self.validate_certificate(certificate))

    def _map_policy_result(
        self,
        result: Any,  # PolicyResult
        elapsed_ms: float,
    ) -> ValidationResult:
        """Map PolicyResult to ValidationResult.

        Mapping:
            PolicyResult.allowed=True -> APPROVED
            PolicyResult.allowed=False -> BLOCKED (default)
            decision.status from raw_output overrides if present

        The Rego policy returns:
            allow: bool
            decision: {status: "APPROVED"|"BLOCKED", reason: "..."}
        """
        # Extract decision object from raw_output if available
        raw = result.raw_output or {}
        decision = raw.get("decision", {})

        # Default reason from violation_message or decision.reason
        reason = (
            decision.get("reason")
            or result.violation_message
            or ("OK" if result.allowed else "DEFAULT_DENY")
        )

        # Map status
        if result.allowed:
            status = ValidationStatus.APPROVED
        else:
            # Check for ESCALATION_REQUIRED from Rego (future extension)
            rego_status = decision.get("status", "BLOCKED")
            if rego_status == "ESCALATION_REQUIRED":
                status = ValidationStatus.ESCALATION_REQUIRED
            else:
                status = ValidationStatus.BLOCKED

        # Build details dict
        details: dict[str, Any] = {}

        if decision:
            details["decision"] = decision

        if result.violation_code:
            details["violation_code"] = result.violation_code

        if result.conditions_met:
            details["conditions_met"] = list(result.conditions_met)

        if result.conditions_missing:
            details["conditions_missing"] = list(result.conditions_missing)

        # Include deny_reasons if present
        if raw.get("deny_reasons"):
            details["deny_reasons"] = raw["deny_reasons"]

        return ValidationResult(
            status=status,
            reason=reason,
            details=details,
            evaluated_at=result.evaluated_at,
            evaluation_ms=elapsed_ms,
        )

    def set_data_provider(self, provider: UCSDataProvider) -> None:
        """Update the data provider.

        Use when switching between different CEP/key contexts.

        Args:
            provider: New UCSDataProvider instance.
        """
        self._data_provider = provider

    @property
    def data_provider(self) -> UCSDataProvider:
        """Get current data provider (read-only access)."""
        return self._data_provider


__all__ = [
    "UCSValidator",
    "ValidationResult",
    "ValidationStatus",
]
