"""DataOrchestrator - builds OPA input documents from data sources.

Implements the Data Requirements DSL execution:
1. Parse data plan from PolicyAdapter.data_sources
2. Execute sources in waves (base → derived)
3. Build normalized input document
4. Handle missing data (fail-closed)

Reference: .khive/workspaces/20260111/review_core/synthesis.md Section 14
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from canon.exceptions import DataFetchError, DataSourceCycleError
from kron.utils import alcall, concurrency, now_utc


class DataSourceType(str, Enum):
    """Types of data sources in the DSL."""

    EVIDENCE = "evidence"  # Fetch from evidence store
    DB = "db"  # Fetch from database
    EXTERNAL = "external"  # External API call
    DERIVED = "derived"  # Computed from other values
    CONSTANT = "constant"  # Static value


class CacheScope(str, Enum):
    """Cache scope for data sources."""

    REQUEST = "request"  # Per-request cache
    PROCESS = "process"  # Process-level cache
    SHARED = "shared"  # Shared cache (Redis, etc.)


class RedactionLevel(str, Enum):
    """Redaction level for audit storage."""

    FULL = "full"  # Store complete value
    HASH_ONLY = "hash_only"  # Store only hash
    POINTER = "pointer"  # Store reference only


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Cache configuration for a data source."""

    scope: CacheScope = CacheScope.REQUEST
    ttl_ms: int = 60000
    key: str | None = None


@dataclass(frozen=True, slots=True)
class RedactionConfig:
    """Redaction configuration for audit storage."""

    store: RedactionLevel = RedactionLevel.FULL
    pii: str = "none"  # none, low, high


@dataclass(frozen=True, slots=True)
class DataSourceSpec:
    """Specification for a data source in the DSL.

    Attributes:
        id: Unique identifier within the policy adapter
        type: Type of data source
        required: Whether source is required (fail-closed if missing)
        into: JSON path in output document (e.g., "evidence.fair_chance.notice")
        timeout_ms: Timeout for fetching this source
        requires: List of source IDs that must complete before this one
        cache: Cache configuration
        redact: Redaction configuration
        spec: Type-specific configuration
    """

    id: str
    type: DataSourceType
    required: bool
    into: str
    timeout_ms: int = 20
    requires: tuple[str, ...] = ()
    cache: CacheConfig = field(default_factory=CacheConfig)
    redact: RedactionConfig = field(default_factory=RedactionConfig)
    spec: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataSourceSpec:
        """Parse from dictionary representation."""
        cache_data = data.get("cache", {})
        redact_data = data.get("redact", {})

        return cls(
            id=data["id"],
            type=DataSourceType(data["type"]),
            required=data.get("required", True),
            into=data["into"],
            timeout_ms=data.get("timeout_ms", 20),
            requires=tuple(data.get("requires", [])),
            cache=CacheConfig(
                scope=CacheScope(cache_data.get("scope", "request")),
                ttl_ms=cache_data.get("ttl_ms", 60000),
                key=cache_data.get("key"),
            ),
            redact=RedactionConfig(
                store=RedactionLevel(redact_data.get("store", "full")),
                pii=redact_data.get("pii", "none"),
            ),
            spec={
                k: v
                for k, v in data.items()
                if k
                not in (
                    "id",
                    "type",
                    "required",
                    "into",
                    "timeout_ms",
                    "requires",
                    "cache",
                    "redact",
                )
            },
        )


def _detect_cycle(specs: Sequence[DataSourceSpec]) -> list[str] | None:
    """Detect cycles in data source dependencies using DFS.

    Returns the cycle path if found, None otherwise.
    """
    by_id = {s.id: s for s in specs}
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {s.id: WHITE for s in specs}
    parent: dict[str, str | None] = {s.id: None for s in specs}

    def dfs(node_id: str) -> list[str] | None:
        color[node_id] = GRAY
        spec = by_id.get(node_id)
        if spec:
            for dep_id in spec.requires:
                if dep_id not in by_id:
                    continue  # External dependency, skip
                if color[dep_id] == GRAY:
                    # Found cycle - reconstruct path
                    cycle = [dep_id, node_id]
                    cur = parent[node_id]
                    while cur and cur != dep_id:
                        cycle.append(cur)
                        cur = parent[cur]
                    cycle.append(dep_id)
                    return list(reversed(cycle))
                if color[dep_id] == WHITE:
                    parent[dep_id] = node_id
                    result = dfs(dep_id)
                    if result:
                        return result
        color[node_id] = BLACK
        return None

    for spec in specs:
        if color[spec.id] == WHITE:
            result = dfs(spec.id)
            if result:
                return result
    return None


def _topological_sort(specs: list[DataSourceSpec]) -> list[DataSourceSpec]:
    """Sort specs by dependency order (dependencies first)."""
    by_id = {s.id: s for s in specs}
    in_degree: dict[str, int] = {s.id: 0 for s in specs}

    # Count incoming edges (only for deps within this set)
    for spec in specs:
        for dep_id in spec.requires:
            if dep_id in by_id:
                in_degree[spec.id] += 1

    # Start with nodes that have no dependencies
    queue = [s for s in specs if in_degree[s.id] == 0]
    result: list[DataSourceSpec] = []

    while queue:
        # Pop spec with no remaining dependencies
        spec = queue.pop(0)
        result.append(spec)

        # Reduce in-degree for specs that depend on this one
        for other in specs:
            if spec.id in other.requires and other.id in by_id:
                in_degree[other.id] -= 1
                if in_degree[other.id] == 0:
                    queue.append(other)

    return result


@dataclass
class DataPlan:
    """Compiled data plan from DSL.

    Separates sources into execution waves with dependency ordering.
    """

    base_sources: list[DataSourceSpec]  # evidence, db, external, constant
    derived_sources: list[DataSourceSpec]  # computed from base

    @classmethod
    def from_specs(cls, specs: Sequence[DataSourceSpec]) -> DataPlan:
        """Compile plan from specifications.

        Raises:
            DataSourceCycleError: If cyclic dependencies detected
        """
        # Check for cycles across all specs
        cycle = _detect_cycle(specs)
        if cycle:
            raise DataSourceCycleError(cycle)

        # Separate by type
        base = [s for s in specs if s.type != DataSourceType.DERIVED]
        derived = [s for s in specs if s.type == DataSourceType.DERIVED]

        # Sort each wave by dependencies
        return cls(
            base_sources=_topological_sort(base),
            derived_sources=_topological_sort(derived),
        )


@dataclass
class OPAInputDocument:
    """Standardized OPA input document.

    Structure:
        ctx: Request context subset
        policy_config: PolicyDefinition + Constitution overrides
        evidence: Evidence objects
        facts: Normalized facts
        derived: Computed values
        meta: Audit metadata
    """

    ctx: dict[str, Any] = field(default_factory=dict)
    policy_config: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    facts: dict[str, Any] = field(default_factory=dict)
    derived: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for OPA."""
        return {
            "ctx": self.ctx,
            "policy_config": self.policy_config,
            "evidence": self.evidence,
            "facts": self.facts,
            "derived": self.derived,
            "meta": self.meta,
        }

    def set_path(self, path: str, value: Any) -> None:
        """Set value at dot-separated path."""
        parts = path.split(".")
        target = self.to_dict()

        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]

        target[parts[-1]] = value

    def get_path(self, path: str) -> Any:
        """Get value at dot-separated path."""
        parts = path.split(".")
        target = self.to_dict()

        for part in parts:
            if isinstance(target, dict) and part in target:
                target = target[part]
            else:
                return None

        return target


class EvidenceStore:
    """Protocol for evidence store."""

    async def get_latest(
        self,
        evidence_type: str,
        selector: dict[str, Any],
        project: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Get latest evidence matching selector."""
        raise NotImplementedError


class DerivedLibrary:
    """Protocol for derived computation library."""

    async def compute(
        self,
        fn: str,
        args: dict[str, Any],
    ) -> Any:
        """Compute derived value."""
        raise NotImplementedError


class DefaultDerivedLibrary(DerivedLibrary):
    """Default derived computation library.

    Supports common computations:
    - business_days_between: Count business days between dates
    - days_since: Days since a date
    - is_after/is_before: Date comparisons

    CS-075 Human Review Bypass derived facts:
    - verify_calibration: Check model calibration is validated
    - verify_monitoring_config: Check monitoring configuration is verified
    - verify_dpia: Check DPIA covers automated decision-making
    - verify_legal_basis: Check legal basis is documented
    - verify_accuracy: Check model accuracy is validated and recent
    - verify_fallback_tested: Check fallback mechanism was tested recently
    - verify_appeal_documented: Check appeal procedure is documented
    """

    def __init__(self) -> None:
        self._functions: dict[str, Callable[..., Any]] = {
            "business_days_between": self._business_days_between,
            "days_since": self._days_since,
            "is_after": self._is_after,
            "is_before": self._is_before,
            # CS-075 Human Review Bypass derived facts
            "verify_calibration": self._verify_calibration,
            "verify_monitoring_config": self._verify_monitoring_config,
            "verify_dpia": self._verify_dpia,
            "verify_legal_basis": self._verify_legal_basis,
            "verify_accuracy": self._verify_accuracy,
            "verify_fallback_tested": self._verify_fallback_tested,
            "verify_appeal_documented": self._verify_appeal_documented,
        }

    async def compute(self, fn: str, args: dict[str, Any]) -> Any:
        """Compute derived value."""
        if fn not in self._functions:
            raise ValueError(f"Unknown derived function: {fn}")
        return self._functions[fn](**args)

    def _business_days_between(
        self,
        start: str | datetime,
        end: str | datetime,
        calendar: str = "US",
    ) -> int:
        """Count business days between dates (simplified)."""
        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if isinstance(end, str):
            end = datetime.fromisoformat(end.replace("Z", "+00:00"))

        # Simplified: count weekdays
        days = 0
        current = start
        from datetime import timedelta

        while current < end:
            if current.weekday() < 5:  # Mon-Fri
                days += 1
            current += timedelta(days=1)
        return days

    def _days_since(self, date: str | datetime) -> int:
        """Days since a date."""
        if isinstance(date, str):
            date = datetime.fromisoformat(date.replace("Z", "+00:00"))
        delta = now_utc() - date
        return delta.days

    def _is_after(self, date: str | datetime, threshold: str | datetime) -> bool:
        """Check if date is after threshold."""
        if isinstance(date, str):
            date = datetime.fromisoformat(date.replace("Z", "+00:00"))
        if isinstance(threshold, str):
            threshold = datetime.fromisoformat(threshold.replace("Z", "+00:00"))
        return date > threshold

    def _is_before(self, date: str | datetime, threshold: str | datetime) -> bool:
        """Check if date is before threshold."""
        if isinstance(date, str):
            date = datetime.fromisoformat(date.replace("Z", "+00:00"))
        if isinstance(threshold, str):
            threshold = datetime.fromisoformat(threshold.replace("Z", "+00:00"))
        return date < threshold

    # =========================================================================
    # CS-075 Human Review Bypass Derived Facts
    # =========================================================================

    def _verify_calibration(
        self,
        calibration_report: dict[str, Any] | None,
        tolerance: float = 0.1,
    ) -> bool:
        """Verify model calibration is validated.

        CS-075 derived fact: calibration_validated
        Checks that calibration report exists and calibration curve is within tolerance.

        Args:
            calibration_report: Calibration report evidence object
            tolerance: Maximum allowed deviation between predicted/actual (default 0.1)

        Returns:
            True if calibration is validated, False otherwise
        """
        if not calibration_report:
            return False

        # Check report is present and complete
        if not calibration_report.get("completed", False):
            return False

        # Check calibration error is within tolerance
        calibration_error = calibration_report.get("calibration_error")
        if calibration_error is None:
            return False

        return abs(calibration_error) <= tolerance

    def _verify_monitoring_config(
        self,
        monitoring_configuration: dict[str, Any] | None,
    ) -> bool:
        """Verify monitoring configuration is set up.

        CS-075 derived fact: monitoring_config_verified
        Checks that monitoring configuration exists and has alerting thresholds.

        Args:
            monitoring_configuration: Monitoring config evidence object

        Returns:
            True if monitoring is configured, False otherwise
        """
        if not monitoring_configuration:
            return False

        # Check required monitoring elements are present
        has_alert_thresholds = monitoring_configuration.get("alerting_thresholds") is not None
        has_metrics = monitoring_configuration.get("metrics_enabled", False)

        return has_alert_thresholds and has_metrics

    def _verify_dpia(
        self,
        dpia: dict[str, Any] | None,
    ) -> bool:
        """Verify DPIA covers automated decision-making.

        CS-075 derived fact: dpia_complete
        Checks that DPIA exists and explicitly covers automated decision-making.

        Args:
            dpia: Data Protection Impact Assessment evidence object

        Returns:
            True if DPIA is complete and covers ADM, False otherwise
        """
        if not dpia:
            return False

        # Check DPIA is complete
        if not dpia.get("completed", False):
            return False

        # Check DPIA covers automated decision-making
        covers_adm = dpia.get("covers_automated_decision_making", False)
        return covers_adm

    def _verify_legal_basis(
        self,
        legal_basis_memo: dict[str, Any] | None,
    ) -> bool:
        """Verify legal basis is documented.

        CS-075 derived fact: legal_basis_documented
        Checks that legal basis memo exists and cites valid GDPR Art. 22 exception.

        Args:
            legal_basis_memo: Legal basis memo evidence object

        Returns:
            True if legal basis is documented, False otherwise
        """
        if not legal_basis_memo:
            return False

        # Check memo is present and cites Art. 22 exception
        has_memo = legal_basis_memo.get("content") is not None
        cites_art22 = legal_basis_memo.get("cites_gdpr_art22_exception", False)

        return has_memo and cites_art22

    def _verify_accuracy(
        self,
        accuracy_report: dict[str, Any] | None,
        min_accuracy: float = 0.9,
        max_age_days: int = 90,
    ) -> bool:
        """Verify model accuracy is validated and recent.

        CS-075 derived fact: accuracy_validated
        Checks accuracy report exists, accuracy exceeds threshold, and report is recent.

        Args:
            accuracy_report: Model accuracy report evidence object
            min_accuracy: Minimum required accuracy (default 0.9 = 90%)
            max_age_days: Maximum age of report in days (default 90)

        Returns:
            True if accuracy is validated, False otherwise
        """
        if not accuracy_report:
            return False

        # Check accuracy meets threshold
        accuracy = accuracy_report.get("accuracy")
        if accuracy is None or accuracy < min_accuracy:
            return False

        # Check report is recent
        validated_at = accuracy_report.get("validated_at")
        if validated_at:
            if isinstance(validated_at, str):
                validated_at = datetime.fromisoformat(validated_at.replace("Z", "+00:00"))
            days_since = (now_utc() - validated_at).days
            if days_since > max_age_days:
                return False

        return True

    def _verify_fallback_tested(
        self,
        fallback_test_results: dict[str, Any] | None,
        max_age_days: int = 30,
    ) -> bool:
        """Verify fallback mechanism was tested recently.

        CS-075 derived fact: fallback_mechanism_tested
        Checks fallback test results exist and are within required window.

        Args:
            fallback_test_results: Fallback test results evidence object
            max_age_days: Maximum age of test in days (default 30)

        Returns:
            True if fallback was tested recently, False otherwise
        """
        if not fallback_test_results:
            return False

        # Check test passed
        if not fallback_test_results.get("passed", False):
            return False

        # Check test is recent
        tested_at = fallback_test_results.get("tested_at")
        if tested_at:
            if isinstance(tested_at, str):
                tested_at = datetime.fromisoformat(tested_at.replace("Z", "+00:00"))
            days_since = (now_utc() - tested_at).days
            if days_since > max_age_days:
                return False

        return True

    def _verify_appeal_documented(
        self,
        appeal_procedure: dict[str, Any] | None,
    ) -> bool:
        """Verify appeal procedure is documented.

        CS-075 derived fact: appeal_process_documented
        Checks appeal procedure exists and is accessible to affected parties.

        Args:
            appeal_procedure: Appeal procedure evidence object

        Returns:
            True if appeal is documented, False otherwise
        """
        if not appeal_procedure:
            return False

        # Check procedure is documented
        has_content = appeal_procedure.get("content") is not None
        is_accessible = appeal_procedure.get("accessible_to_affected", False)

        return has_content and is_accessible


class DataOrchestrator:
    """Orchestrates data fetching and builds OPA input documents.

    Usage:
        orchestrator = DataOrchestrator(evidence_store=store)
        doc = await orchestrator.build_input(
            ctx=request_context,
            policy_config=config,
            data_sources=adapter.data_sources,
            meta={"policy_id": "..."},
        )
    """

    def __init__(
        self,
        evidence_store: EvidenceStore | None = None,
        derived_lib: DerivedLibrary | None = None,
        request_cache: dict[str, Any] | None = None,
    ):
        """Initialize orchestrator.

        Args:
            evidence_store: Store for fetching evidence
            derived_lib: Library for derived computations
            request_cache: Per-request cache (optional)
        """
        self._evidence = evidence_store
        self._derived = derived_lib or DefaultDerivedLibrary()
        self._cache = request_cache or {}

    async def build_input(
        self,
        *,
        ctx: dict[str, Any],
        policy_config: dict[str, Any],
        data_sources: Sequence[DataSourceSpec | dict[str, Any]],
        meta: dict[str, Any],
    ) -> OPAInputDocument:
        """Build OPA input document from data sources.

        Args:
            ctx: Request context
            policy_config: Policy configuration
            data_sources: Data source specifications
            meta: Metadata for audit

        Returns:
            Populated OPAInputDocument

        Raises:
            DataFetchError: If required source fails
        """
        # Parse specs if needed
        specs = [
            s if isinstance(s, DataSourceSpec) else DataSourceSpec.from_dict(s)
            for s in data_sources
        ]

        # Compile plan
        plan = DataPlan.from_specs(specs)

        # Initialize document
        doc = OPAInputDocument(
            ctx=ctx,
            policy_config=policy_config,
            meta=meta,
        )

        # Wave 1: Execute base sources
        await self._execute_wave(doc, plan.base_sources)

        # Wave 2: Execute derived sources
        await self._execute_wave(doc, plan.derived_sources)

        return doc

    async def _execute_wave(
        self,
        doc: OPAInputDocument,
        sources: list[DataSourceSpec],
    ) -> None:
        """Execute a wave of data sources in dependency layers.

        Sources are executed in layers respecting their `requires` dependencies.
        Within each layer, independent sources run in parallel.
        """
        if not sources:
            return

        # Build dependency tracking
        source_ids = {s.id for s in sources}
        completed: set[str] = set()
        remaining = list(sources)

        while remaining:
            # Find sources whose dependencies are all completed
            # (or dependencies are external to this wave)
            ready: list[DataSourceSpec] = []
            still_waiting: list[DataSourceSpec] = []

            for spec in remaining:
                # Check if all internal dependencies are satisfied
                internal_deps = set(spec.requires) & source_ids
                if internal_deps <= completed:
                    ready.append(spec)
                else:
                    still_waiting.append(spec)

            if not ready:
                # No progress - circular dependency or bug
                waiting_ids = [s.id for s in still_waiting]
                raise DataFetchError(
                    waiting_ids[0],
                    f"Dependency deadlock: {waiting_ids} waiting on unresolved deps",
                )

            # Execute ready sources in parallel
            results = await alcall(
                ready,
                self._execute_one,
                doc=doc,
                return_exceptions=True,
            )

            for spec, result in zip(ready, results, strict=True):
                if isinstance(result, Exception):
                    if spec.required:
                        raise DataFetchError(spec.id, str(result))
                    # Optional: record error
                    doc.facts[f"_errors_{spec.id}"] = str(result)
                # Mark as completed regardless of success (prevents infinite loop)
                completed.add(spec.id)

            remaining = still_waiting

    async def _execute_one(
        self,
        spec: DataSourceSpec,
        doc: OPAInputDocument,
    ) -> None:
        """Execute a single data source."""
        # Check cache
        cache_key = f"{spec.id}:{spec.cache.key or 'default'}"
        if cache_key in self._cache:
            doc.set_path(spec.into, self._cache[cache_key])
            return

        # Execute with timeout
        timeout = spec.timeout_ms / 1000.0

        async def _do() -> Any:
            if spec.type == DataSourceType.CONSTANT:
                return spec.spec.get("value")

            if spec.type == DataSourceType.EVIDENCE:
                return await self._fetch_evidence(doc, spec)

            if spec.type == DataSourceType.DERIVED:
                return await self._compute_derived(doc, spec)

            if spec.type == DataSourceType.DB:
                return await self._fetch_db(doc, spec)

            raise ValueError(f"Unknown data source type: {spec.type}")

        try:
            with concurrency.fail_after(timeout):
                value = await _do()
        except TimeoutError:
            raise TimeoutError(f"Data source {spec.id} timed out after {spec.timeout_ms}ms")

        # B2.3 fix: Fail-closed on required sources returning None
        if spec.required and value is None:
            raise DataFetchError(
                spec.id,
                f"Required data source '{spec.id}' returned None (fail-closed)",
            )

        # Cache result
        if spec.cache.scope == CacheScope.REQUEST:
            self._cache[cache_key] = value

        # Set in document
        doc.set_path(spec.into, value)

    async def _fetch_evidence(
        self,
        doc: OPAInputDocument,
        spec: DataSourceSpec,
    ) -> Any:
        """Fetch from evidence store."""
        if not self._evidence:
            raise ValueError("Evidence store not configured")

        selector = self._resolve_templates(doc, spec.spec.get("selector", {}))
        evidence_type = spec.spec.get("evidence_type")
        project = spec.spec.get("project")

        return await self._evidence.get_latest(evidence_type, selector, project)

    async def _compute_derived(
        self,
        doc: OPAInputDocument,
        spec: DataSourceSpec,
    ) -> Any:
        """Compute derived value."""
        fn = spec.spec.get("fn")
        if not fn:
            raise ValueError(f"Derived source {spec.id} missing 'fn'")

        args = self._resolve_templates(doc, spec.spec.get("args", {}))
        return await self._derived.compute(fn, args)

    async def _fetch_db(
        self,
        doc: OPAInputDocument,
        spec: DataSourceSpec,
    ) -> Any:
        """Fetch from database.

        Spec format:
            table: str - Table name to query (required)
            where: dict - Conditions with template resolution (optional)
            columns: list[str] - Columns to select (optional, defaults to *)
            one: bool - Return single row vs list (default: True)
            schema: str - Schema name (default: "public")

        Template resolution:
            Values starting with $ are resolved from doc paths.
            Example: {"tenant_id": "$ctx.tenant_id"}
        """
        from canon.db import select, select_one
        from canon.db.validation import validate_identifier

        table = spec.spec.get("table")
        if not table:
            raise ValueError(f"DB source {spec.id} missing required 'table' field")

        # Validate table name to prevent SQL injection
        validate_identifier(table, "table")

        schema = spec.spec.get("schema", "public")
        validate_identifier(schema, "schema")

        # Resolve where clause templates
        where = spec.spec.get("where", {})
        resolved_where = self._resolve_templates(doc, where)

        # Determine if we want one row or many
        fetch_one = spec.spec.get("one", True)

        if fetch_one:
            return await select_one(
                table,
                where=resolved_where,
                schema=schema,
            )
        else:
            order_by = spec.spec.get("order_by")
            limit = spec.spec.get("limit")
            return await select(
                table,
                where=resolved_where,
                order_by=order_by,
                limit=limit,
                schema=schema,
            )

    def _resolve_templates(self, doc: OPAInputDocument, obj: Any) -> Any:
        """Resolve template references like $ctx.tenant_id."""
        if isinstance(obj, str) and obj.startswith("$"):
            path = obj[1:]  # Remove $
            return doc.get_path(path)

        if isinstance(obj, dict):
            return {k: self._resolve_templates(doc, v) for k, v in obj.items()}

        if isinstance(obj, list):
            return [self._resolve_templates(doc, v) for v in obj]

        return obj


__all__ = [
    "CacheConfig",
    "CacheScope",
    "DataFetchError",
    "DataOrchestrator",
    "DataPlan",
    "DataSourceCycleError",
    "DataSourceSpec",
    "DataSourceType",
    "DefaultDerivedLibrary",
    "DerivedLibrary",
    "EvidenceStore",
    "OPAInputDocument",
    "RedactionConfig",
    "RedactionLevel",
]
