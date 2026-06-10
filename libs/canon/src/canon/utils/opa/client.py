"""OPA (Open Policy Agent) integration for declarative policy evaluation.

Canon uses OPA with Rego for policy enforcement. This provides:
- Industry-standard policy evaluation (same as Kubernetes, Terraform)
- Declarative rules that Legal can audit
- Separation of policy logic from application code

Dual-mode support:
- Embedded mode: Uses regorus (Rust OPA) for low-latency hot-path evaluation
- Remote mode: Uses httpx to OPA REST API for debugging and audit logging

Key Invariant: Fail-closed on any error (evaluation error = deny).

Critical Parsing Invariants (F-01/F-02 fix):
- NEVER use bool(raw_result) to interpret a policy decision
- Undefined/empty results => deny (fail-closed)
- deny_reasons is ALWAYS list[str] (never dicts)

Reference:
- docs/v2/architecture/policy.md Section 4 (OPA/Rego Integration)
- docs/policy-contract.md
- https://www.openpolicyagent.org/
"""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from canon.exceptions import BundleError, PolicyEvaluationError
from kron.utils import compute_hash, concurrency, now_utc

from .decoder import decode_policy

if TYPE_CHECKING:
    import httpx


@dataclass(frozen=True, slots=True)
class OPAConfig:
    """Configuration for OPA integration.

    Attributes:
        mode: Evaluation mode - "embedded" (regorus) or "remote" (HTTP)
        bundle_path: Path to policy bundle (embedded mode)
        bundle_refresh_interval: Seconds between bundle refresh checks
        opa_url: OPA server URL (remote mode)
        timeout: HTTP timeout in seconds (remote mode)
        fail_closed: Always deny on errors (required for compliance)
        enable_metrics: Track evaluation metrics
        enable_decision_logging: Log all decisions for audit
    """

    mode: Literal["embedded", "remote"] = "embedded"
    bundle_path: str | None = None
    bundle_refresh_interval: int = 300
    opa_url: str = "http://localhost:8181"
    timeout: float = 5.0
    fail_closed: bool = True
    enable_metrics: bool = True
    enable_decision_logging: bool = True

    @classmethod
    def from_env(cls) -> OPAConfig:
        """Load configuration from environment variables."""
        return cls(
            mode=os.getenv("OPA_MODE", "embedded"),  # type: ignore[arg-type]
            bundle_path=os.getenv("OPA_BUNDLE_PATH"),
            bundle_refresh_interval=int(os.getenv("OPA_BUNDLE_REFRESH", "300")),
            opa_url=os.getenv("OPA_URL", "http://localhost:8181"),
            timeout=float(os.getenv("OPA_TIMEOUT", "5.0")),
            fail_closed=os.getenv("OPA_FAIL_CLOSED", "true").lower() == "true",
        )


@dataclass(frozen=True, slots=True)
class BundleInfo:
    """Information about a loaded policy bundle.

    Attributes:
        revision: Bundle revision string (e.g., "2026.01.11-a7f3c821")
        path: Path to bundle on disk
        loaded_at: When bundle was loaded
        policy_count: Number of policies in bundle
        roots: Rego package roots
        metadata: Additional bundle metadata
    """

    revision: str
    path: str
    loaded_at: datetime
    policy_count: int = 0
    roots: tuple[str, ...] = ("canon",)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def hash(self) -> str:
        """Policy library hash for evidence."""
        return f"sha256:{self.revision}"


@dataclass(frozen=True, slots=True)
class OPAInput:
    """Input document for OPA evaluation.

    This is the context passed to Rego for policy evaluation.
    Maps to `input.*` in Rego policies.
    """

    # Action context
    action_type: str
    tenant_id: str
    jurisdiction: str | None = None

    # Subject context
    subject_id: str | None = None

    # Domain-specific data (varies by policy)
    data: dict[str, Any] = field(default_factory=dict)

    # Timestamp for temporal rules
    evaluated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to OPA input document.

        Note: Reserved keys (action_type, tenant_id, etc.) always win over
        any keys in self.data to prevent policy bypass via data injection.
        """
        # Start with data, then override with reserved keys (reserved wins)
        base = {
            "action_type": self.action_type,
            "tenant_id": self.tenant_id,
            "jurisdiction": self.jurisdiction,
            "subject_id": self.subject_id,
            "evaluated_at": self.evaluated_at or now_utc().isoformat(),
        }
        return {**self.data, **base}


@dataclass(frozen=True, slots=True)
class OPAResult:
    """Result from OPA policy evaluation.

    Binary decision with audit trail information.
    """

    allow: bool
    deny_reasons: tuple[str, ...] = field(default_factory=tuple)

    # For audit trail
    package: str | None = None
    input_hash: str | None = None
    evaluated_at: datetime | None = None
    metrics: dict[str, Any] | None = None


class OPAClientBase(ABC):
    """Abstract base class for OPA policy evaluation clients.

    Implementations:
    - EmbeddedOPAClient: Uses regorus (Rust) via asyncio.to_thread
    - RemoteOPAClient: Uses httpx to OPA REST API

    Key Invariant: Fail-closed on any error (evaluation error = deny).
    """

    @abstractmethod
    async def evaluate(
        self,
        package: str,
        input: OPAInput,
        rule: str = "allow",
    ) -> OPAResult:
        """Evaluate a policy package against input.

        Args:
            package: Rego package name (e.g., "canon.statutory.nyc.fair_chance")
            input: Input document for evaluation
            rule: Rule to query (default: "allow")

        Returns:
            OPAResult with allow/deny and reasons

        Raises:
            PolicyEvaluationError: On any OPA error (triggers fail-closed)
        """
        ...

    @abstractmethod
    async def load_bundle(self, bundle_path: str) -> BundleInfo:
        """Load policy bundle into engine.

        Args:
            bundle_path: Path to bundle (.tar.gz or directory)

        Returns:
            BundleInfo with revision and metadata

        Raises:
            BundleError: On bundle load failure
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if OPA engine is healthy.

        Returns:
            True if engine is operational
        """
        ...

    @abstractmethod
    def get_bundle_info(self) -> BundleInfo | None:
        """Get currently loaded bundle info.

        Returns:
            BundleInfo or None if no bundle loaded
        """
        ...


class EmbeddedOPAClient(OPAClientBase):
    """OPAClient using regorus (Rust OPA) for embedded evaluation.

    Uses asyncio.to_thread() to run sync regorus calls without blocking.

    Performance characteristics:
    - Cold start: ~50ms (policy compilation)
    - Warm evaluation: 0.5-5ms per decision
    - Memory: ~50MB for typical policy bundle

    Note: regorus must be installed separately (not on PyPI).
    Build with: maturin build --release (from regorus/bindings/python)
    """

    def __init__(
        self,
        bundle_path: str | None = None,
        config: OPAConfig | None = None,
    ):
        """Initialize embedded OPA client.

        Args:
            bundle_path: Path to policy bundle (optional)
            config: OPA configuration (optional)
        """
        self._config = config or OPAConfig()
        self._bundle_info: BundleInfo | None = None
        self._lock = concurrency.Lock()
        self._rego_cache: dict[str, str] = {}  # Policy cache for engine recreation
        self._data_cache: dict[str, Any] | None = None  # Data cache for engine recreation

        # Lazy-initialize engine in worker thread (regorus.Engine is not thread-safe)
        self._engine: Any = None
        self._engine_thread_id: int | None = None

        # Load bundle if provided
        if bundle_path:
            # Defer to async load - mark as pending
            self._pending_bundle = bundle_path
        else:
            self._pending_bundle = None

    async def evaluate(
        self,
        package: str,
        input: OPAInput,
        rule: str = "allow",
    ) -> OPAResult:
        """Evaluate via regorus with async wrapper."""
        input_dict = input.to_dict()
        input_hash = compute_hash(input_dict)

        try:
            # Run sync regorus call in thread pool
            result = await concurrency.run_sync(
                self._evaluate_sync,
                package,
                input_dict,
                rule,
                input_hash,
            )
            return result

        except PolicyEvaluationError:
            # Re-raise OPA errors as-is
            raise
        except Exception as e:
            # Fail-closed: any error = deny
            raise PolicyEvaluationError(package, str(e), input_hash=input_hash) from e

    def _ensure_engine(self) -> None:
        """Ensure engine is initialized in current thread.

        regorus.Engine is not thread-safe and must be created in the
        same thread where it will be used.

        H2 Fix: Reloads all cached policies and data when engine is
        recreated in a new thread. Caches are populated by load_bundle().
        """
        import threading

        import regorus

        current_thread = threading.get_ident()
        if self._engine is None or self._engine_thread_id != current_thread:
            self._engine = regorus.Engine()
            self._engine_thread_id = current_thread
            # H2: Reload all cached policies (from bundle + individual loads)
            for filename, content in self._rego_cache.items():
                self._engine.add_policy(filename, content)
            # H2: Reload cached data (from bundle)
            if self._data_cache is not None:
                self._engine.add_data(self._data_cache)

    def _evaluate_sync(
        self,
        package: str,
        input_dict: dict[str, Any],
        rule: str,
        input_hash: str,
    ) -> OPAResult:
        """Sync evaluation (called in thread pool).

        Note: This runs in a separate thread, so it's safe to use
        blocking operations like regorus.Engine.eval_rule().

        F-01/F-02 Fix: Uses decode_policy() instead of bool(raw_result).
        - Handles "default allow := false" returning truthy envelope with false
        - Handles undefined results (fail-closed)
        - Ensures deny_reasons is always list[str] (never dicts)
        """
        self._ensure_engine()

        try:
            self._engine.set_input(input_dict)

            # Prefer structured decision object when evaluating allow semantics.
            # Backward compatible: if decision is undefined, fall back to allow/deny rules.
            decision_raw = None
            if rule == "allow":
                try:
                    decision_raw = self._engine.eval_rule(f"data.{package}.decision")
                except Exception:
                    # decision is optional; ignore and fall back to allow/deny
                    decision_raw = None

            # Evaluate allow rule (legacy path)
            allow_query = f"data.{package}.{rule}"
            try:
                allow_raw = self._engine.eval_rule(allow_query)
            except Exception as e:
                raise PolicyEvaluationError(
                    package,
                    f"Failed to evaluate {allow_query}: {e}",
                    input_hash=input_hash,
                ) from e

            # Get deny reasons (optional, best-effort).
            # Prefer deny_reasons, fall back to deny if deny_reasons undefined.
            deny_raw = None
            if rule == "allow":
                for deny_rule in ("deny_reasons", "deny"):
                    try:
                        candidate = self._engine.eval_rule(f"data.{package}.{deny_rule}")
                        # keep it even if empty; decoder will interpret empties as []
                        deny_raw = candidate
                        break
                    except Exception:
                        continue

            # Use defensive decoder (F-01/F-02 fix)
            decoded = decode_policy(
                decision_raw=decision_raw,
                allow_raw=allow_raw,
                deny_raw=deny_raw,
                deny_field_name="deny_reasons",
            )

            return OPAResult(
                allow=decoded.allow,
                deny_reasons=tuple(decoded.deny_reasons),
                package=package,
                input_hash=input_hash,
                evaluated_at=now_utc(),
            )

        except PolicyEvaluationError:
            raise
        except Exception as e:
            raise PolicyEvaluationError(package, str(e), input_hash=input_hash) from e

    async def load_bundle(self, bundle_path: str) -> BundleInfo:
        """Load policy bundle into embedded engine."""
        async with self._lock:
            try:
                # Load bundle in thread pool
                info = await concurrency.run_sync(
                    self._load_bundle_sync,
                    bundle_path,
                )
                self._bundle_info = info
                return info

            except BundleError:
                raise
            except Exception as e:
                raise BundleError(bundle_path, str(e)) from e

    def _load_bundle_sync(self, bundle_path: str) -> BundleInfo:
        """Sync bundle loading (called in thread pool).

        H2 Fix: Cache policies and data so they survive engine recreation
        in different threads. All policies are stored in _rego_cache,
        data in _data_cache, then applied to current engine.
        """
        import json
        from pathlib import Path

        path = Path(bundle_path)

        if path.is_dir():
            # Load from directory
            manifest_path = path / ".manifest"
            revision = "unknown"
            metadata: dict[str, Any] = {}

            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
                    revision = manifest.get("revision", "unknown")
                    metadata = manifest.get("metadata", {})

            # Load all .rego files - cache then apply (H2 fix)
            policy_count = 0
            for rego_file in path.rglob("*.rego"):
                with open(rego_file) as f:
                    content = f.read()
                    filename = str(rego_file)
                    # H2: Cache for engine recreation
                    self._rego_cache[filename] = content
                    # Apply to current engine if available
                    if self._engine:
                        self._engine.add_policy(filename, content)
                    policy_count += 1

            # Load data.json if present - cache then apply (H2 fix)
            data_path = path / "data.json"
            if data_path.exists():
                with open(data_path) as f:
                    data = json.load(f)
                    # H2: Cache for engine recreation
                    self._data_cache = data
                    # Apply to current engine if available
                    if self._engine:
                        self._engine.add_data(data)

        elif path.suffix == ".tar.gz" or path.suffixes == [".tar", ".gz"]:
            # Load from tarball
            import tarfile

            with tarfile.open(bundle_path, "r:gz") as tar:
                manifest_member = None
                try:
                    manifest_member = tar.getmember(".manifest")
                except KeyError:
                    pass

                revision = "unknown"
                metadata = {}

                if manifest_member:
                    f = tar.extractfile(manifest_member)
                    if f:
                        manifest = json.load(f)
                        revision = manifest.get("revision", "unknown")
                        metadata = manifest.get("metadata", {})

                # H2: Load and cache all .rego files from tarball
                policy_count = 0
                for member in tar.getmembers():
                    if member.name.endswith(".rego"):
                        f = tar.extractfile(member)
                        if f:
                            content = f.read().decode("utf-8")
                            # H2: Cache for engine recreation
                            self._rego_cache[member.name] = content
                            # Apply to current engine if available
                            if self._engine:
                                self._engine.add_policy(member.name, content)
                            policy_count += 1

                # H2: Load and cache data.json from tarball
                try:
                    data_member = tar.getmember("data.json")
                    f = tar.extractfile(data_member)
                    if f:
                        data = json.load(f)
                        self._data_cache = data
                        if self._engine:
                            self._engine.add_data(data)
                except KeyError:
                    pass  # data.json is optional
        else:
            raise BundleError(bundle_path, f"Unsupported bundle format: {path.suffix}")

        return BundleInfo(
            revision=revision,
            path=bundle_path,
            loaded_at=now_utc(),
            policy_count=policy_count,
            metadata=metadata,
        )

    async def health_check(self) -> bool:
        """Check if embedded engine is healthy."""
        try:
            import regorus

            return True
        except ImportError:
            return False

    def get_bundle_info(self) -> BundleInfo | None:
        """Get currently loaded bundle info."""
        return self._bundle_info

    def load_rego(self, package: str, rego_content: str) -> None:
        """Load Rego policy from string (for testing).

        Args:
            package: Package name
            rego_content: Rego source code
        """
        # H2: Cache for later when engine is created/recreated in worker thread
        filename = f"{package}.rego"
        self._rego_cache[filename] = rego_content


class RemoteOPAClient(OPAClientBase):
    """OPAClient using HTTP REST API to OPA server.

    Useful for:
    - Development (can inspect decisions in OPA logs)
    - Debugging (OPA's explain mode)
    - Audit trail (OPA decision logs)

    Requires: httpx (pip install httpx)
    """

    def __init__(
        self,
        opa_url: str = "http://localhost:8181",
        timeout: float = 5.0,
        config: OPAConfig | None = None,
    ):
        """Initialize remote OPA client.

        Args:
            opa_url: OPA server URL
            timeout: HTTP timeout in seconds
            config: OPA configuration (optional)
        """
        self._config = config or OPAConfig(mode="remote", opa_url=opa_url)
        self._base_url = opa_url.rstrip("/")
        self._timeout = timeout
        self._client: Any = None  # httpx.AsyncClient, lazy initialized
        self._bundle_info: BundleInfo | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def evaluate(
        self,
        package: str,
        input: OPAInput,
        rule: str = "allow",
    ) -> OPAResult:
        """Evaluate via OPA REST API.

        F-01/F-02 Fix: Uses decode_policy() instead of bool(raw_result).
        - Handles "default allow := false" returning truthy envelope with false
        - Handles undefined results (fail-closed)
        - Ensures deny_reasons is always list[str] (never dicts)
        """
        import httpx

        input_dict = input.to_dict()
        input_hash = compute_hash(input_dict)

        path = package.replace(".", "/")
        params = {"metrics": "true"} if self._config.enable_metrics else None

        try:
            client = await self._get_client()

            # Try decision endpoint first (preferred contract)
            decision_raw = None
            if rule == "allow":
                try:
                    decision_url = f"{self._base_url}/v1/data/{path}/decision"
                    resp = await client.post(
                        decision_url,
                        json={"input": input_dict},
                        params=params,
                    )
                    if resp.status_code == 200:
                        decision_raw = resp.json().get("result")
                except httpx.HTTPError:
                    # decision is optional; fall back to allow/deny
                    decision_raw = None

            # Fetch allow rule
            allow_url = f"{self._base_url}/v1/data/{path}/{rule}"
            response = await client.post(
                allow_url,
                json={"input": input_dict},
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            allow_raw = data.get("result")
            metrics = data.get("metrics")

            # Fetch deny_reasons (optional, best-effort)
            deny_raw = None
            if rule == "allow":
                for deny_rule in ("deny_reasons", "deny"):
                    try:
                        deny_url = f"{self._base_url}/v1/data/{path}/{deny_rule}"
                        resp = await client.post(
                            deny_url,
                            json={"input": input_dict},
                        )
                        if resp.status_code == 200:
                            deny_raw = resp.json().get("result")
                            break
                    except httpx.HTTPError:
                        continue

            # Use defensive decoder (F-01/F-02 fix) - same as EmbeddedOPAClient
            decoded = decode_policy(
                decision_raw=decision_raw,
                allow_raw=allow_raw,
                deny_raw=deny_raw,
                deny_field_name="deny_reasons",
            )

            return OPAResult(
                allow=decoded.allow,
                deny_reasons=tuple(decoded.deny_reasons),
                package=package,
                input_hash=input_hash,
                evaluated_at=now_utc(),
                metrics=metrics,
            )

        except httpx.HTTPStatusError as e:
            raise PolicyEvaluationError(
                package,
                f"HTTP {e.response.status_code}: {e.response.text}",
                input_hash=input_hash,
            ) from e
        except httpx.TimeoutException as e:
            raise PolicyEvaluationError(
                package,
                f"Request timeout after {self._timeout}s",
                input_hash=input_hash,
                retryable=True,  # Transient: timeout may resolve on retry
            ) from e
        except httpx.RequestError as e:
            raise PolicyEvaluationError(
                package,
                f"Request failed: {e}",
                input_hash=input_hash,
                retryable=True,  # Transient: network issues may resolve
            ) from e
        except Exception as e:
            raise PolicyEvaluationError(package, str(e), input_hash=input_hash) from e

    async def load_bundle(self, bundle_path: str) -> BundleInfo:
        """Load bundle - remote mode relies on OPA server's bundle management.

        For remote mode, bundles are typically configured on the OPA server itself
        via -b flag or bundle configuration. This method is provided for API
        compatibility but may not upload bundles depending on OPA server config.
        """
        import httpx

        # Try to get bundle status from OPA server
        try:
            client = await self._get_client()
            response = await client.get(f"{self._base_url}/v1/status")
            response.raise_for_status()

            status = response.json()
            bundles = status.get("result", {}).get("bundles", {})

            # Get first bundle info if available
            revision = "unknown"
            metadata: dict[str, Any] = {}

            for bundle_name, bundle_status in bundles.items():
                if bundle_status.get("active_revision"):
                    revision = bundle_status["active_revision"]
                    metadata["bundle_name"] = bundle_name
                    break

            info = BundleInfo(
                revision=revision,
                path=bundle_path,
                loaded_at=now_utc(),
                metadata=metadata,
            )
            self._bundle_info = info
            return info

        except httpx.HTTPError as e:
            raise BundleError(bundle_path, f"Failed to get bundle status: {e}") from e

    async def health_check(self) -> bool:
        """Check OPA server health."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self._base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    def get_bundle_info(self) -> BundleInfo | None:
        """Get bundle info from last status check."""
        return self._bundle_info

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


def create_opa_client(config: OPAConfig | None = None) -> OPAClientBase:
    """Create OPA client based on configuration.

    Args:
        config: OPA configuration (uses OPAConfig.from_env() if None)

    Returns:
        EmbeddedOPAClient or RemoteOPAClient based on config.mode
    """
    if config is None:
        config = OPAConfig.from_env()

    if config.mode == "remote":
        return RemoteOPAClient(
            opa_url=config.opa_url,
            timeout=config.timeout,
            config=config,
        )
    else:
        return EmbeddedOPAClient(
            bundle_path=config.bundle_path,
            config=config,
        )


_opa_client: OPAClientBase | None = None
_opa_config: OPAConfig | None = None
_opa_lock = threading.Lock()  # H3: Thread-safe singleton


def get_opa_client(config: OPAConfig | None = None) -> OPAClientBase:
    """Get the global OPA client instance.

    H3 Fix: Thread-safe singleton with proper cleanup on config change.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        OPAClientBase instance (EmbeddedOPAClient or RemoteOPAClient)
    """
    global _opa_client, _opa_config

    # H3: Thread-safe double-checked locking
    if _opa_client is None or (config is not None and config != _opa_config):
        with _opa_lock:
            # Check again inside lock
            if _opa_client is None or (config is not None and config != _opa_config):
                # H3: Clean up old client before creating new one
                if _opa_client is not None:
                    _cleanup_client_sync(_opa_client)
                _opa_config = config
                _opa_client = create_opa_client(config)

    return _opa_client


def _cleanup_client_sync(client: OPAClientBase) -> None:
    """Synchronously clean up a client (best effort).

    H3 Fix: Proper cleanup when config changes or on reset.
    RemoteOPAClient has async close(), but we may be in sync context.
    """
    if isinstance(client, RemoteOPAClient) and client._client is not None:
        # Best effort: try to close httpx client synchronously
        # In async context, caller should use reset_opa_client_async()
        try:
            import asyncio

            # Try to run close in event loop if one exists
            try:
                loop = asyncio.get_running_loop()
                # We're in async context - can't block, schedule cleanup
                loop.create_task(client.close())
            except RuntimeError:
                # No running loop - run sync
                asyncio.run(client.close())
        except Exception:
            pass  # Best effort cleanup


def reset_opa_client() -> None:
    """Reset the global OPA client (for testing).

    H3 Fix: Thread-safe with proper cleanup.
    """
    global _opa_client, _opa_config

    with _opa_lock:
        if _opa_client is not None:
            _cleanup_client_sync(_opa_client)
        _opa_client = None
        _opa_config = None


async def reset_opa_client_async() -> None:
    """Async reset of global OPA client with proper cleanup.

    H3 Fix: For async contexts where proper cleanup is needed.
    Note: Close happens outside lock to avoid blocking event loop.
    """
    global _opa_client, _opa_config

    client_to_close: RemoteOPAClient | None = None
    with _opa_lock:
        if _opa_client is not None:
            if isinstance(_opa_client, RemoteOPAClient):
                client_to_close = _opa_client
        _opa_client = None
        _opa_config = None

    # Close outside lock to avoid blocking event loop
    if client_to_close is not None:
        await client_to_close.close()


__all__ = [
    "BundleError",
    "BundleInfo",
    "EmbeddedOPAClient",
    "OPAClientBase",
    "OPAConfig",
    "OPAInput",
    "OPAResult",
    "PolicyEvaluationError",
    "RemoteOPAClient",
    "create_opa_client",
    "get_opa_client",
    "reset_opa_client",
    "reset_opa_client_async",  # H3: Async cleanup
]
