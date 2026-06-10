"""Hub: top-level facade binding registry + catalogs + execution."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from canon.dsl.catalog import SchemaCatalog
from canon.dsl.compiler import CompiledCharter, compile_charter

from .domain_registry import DomainRegistry
from .executor import CharterExecutor, PhaseResult, PhraseResolver, WorkflowResult
from .package import VocabularyPackage
from .registry import PackageRegistry

__all__ = ("Hub", "build_hub")


class Hub:
    """Top-level facade: packages + catalogs + compilation + execution."""

    def __init__(
        self,
        registry: PackageRegistry,
        catalog: SchemaCatalog,
        packages: tuple[VocabularyPackage, ...] = (),
        domain_registry: DomainRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.catalog = catalog
        self._packages = packages
        self.domain_registry = domain_registry

    def compile(
        self,
        source: str,
        *,
        policy_registry: Any | None = None,
    ) -> CompiledCharter:
        """Compile charter source with full vocabulary validation."""
        return compile_charter(
            source,
            catalog=self.catalog,
            feature_registry=self.registry,
            policy_registry=policy_registry,
            package_registry=self.registry,
        )

    def build_executor(self) -> CharterExecutor:
        """Build a CharterExecutor with resolved phrase callables."""
        resolver = PhraseResolver(self._packages)
        return CharterExecutor(resolver)

    async def execute(
        self,
        source: str,
        workflow_name: str,
        ctx: Any,
        *,
        policy_registry: Any | None = None,
        max_concurrent: int = 1,
        stop_on_error: bool = True,
    ) -> WorkflowResult:
        """Compile and execute a charter workflow end-to-end.

        Returns a WorkflowResult with per-phase outcomes.
        """
        compiled = self.compile(source, policy_registry=policy_registry)
        executor = self.build_executor()
        return await executor.execute(
            compiled,
            workflow_name,
            ctx,
            max_concurrent=max_concurrent,
            stop_on_error=stop_on_error,
        )

    async def stream_execute(
        self,
        source: str,
        workflow_name: str,
        ctx: Any,
        *,
        policy_registry: Any | None = None,
        max_concurrent: int = 1,
        stop_on_error: bool = True,
    ) -> AsyncGenerator[PhaseResult, None]:
        """Compile and execute a charter workflow, yielding phase results."""
        compiled = self.compile(source, policy_registry=policy_registry)
        executor = self.build_executor()
        async for pr in executor.stream_execute(
            compiled,
            workflow_name,
            ctx,
            max_concurrent=max_concurrent,
            stop_on_error=stop_on_error,
        ):
            yield pr


def build_hub(*, with_domains: bool = True) -> Hub:
    """Construct a Hub with all default packages, catalogs, and optionally domains.

    Args:
        with_domains: If True, discover and load domain manifests from
            hub/domains/ and hub/foundation/. Defaults to True.
    """
    from .catalogs import build_canon_hr_catalog, build_canonsys_catalog
    from .packages import ALL_PACKAGES

    registry = PackageRegistry(ALL_PACKAGES)

    catalog = SchemaCatalog()
    build_canonsys_catalog(catalog)
    build_canon_hr_catalog(catalog)

    domain_reg = None
    if with_domains:
        domain_reg = _build_domain_registry(registry)

    return Hub(
        registry=registry,
        catalog=catalog,
        packages=ALL_PACKAGES,
        domain_registry=domain_reg,
    )


def _build_domain_registry(
    package_registry: PackageRegistry,
) -> DomainRegistry | None:
    """Discover domains and build a DomainRegistry.

    Returns None if no domain manifests are found (graceful degradation).
    """
    import logging

    from .domain_loader import discover_domains
    from .packages import get_packages_dir

    logger = logging.getLogger(__name__)

    # get_packages_dir() now returns hub/ directly
    hub_dir = get_packages_dir()
    domains_dir = hub_dir / "domains"
    foundation_dir = hub_dir / "foundation"

    manifests = discover_domains(domains_dir, foundation_dir)
    if not manifests:
        return None

    try:
        domain_reg = DomainRegistry(manifests, package_registry)
    except ValueError:
        logger.warning("Domain registry construction failed", exc_info=True)
        return None

    unassigned = domain_reg.unassigned_packages()
    if unassigned:
        logger.info("Packages not assigned to any domain: %s", ", ".join(unassigned))

    return domain_reg
