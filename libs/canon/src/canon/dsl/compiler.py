"""Charter DSL compiler — end-to-end compilation pipeline.

Orchestrates lexer -> parser -> resolver to produce a CompiledCharter,
the validated, executable representation of a charter document.

Usage:
    from canon.dsl.compiler import compile_charter

    compiled = compile_charter(source_text, catalog=my_catalog)
    # compiled.phase_order["pip_workflow"]  -> ("eligibility", "notice", ...)
    # compiled.feature_names                -> frozenset({"verify_consent", ...})
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .ast import CharterNode, RoleNode, SituationNode
from .catalog import SchemaCatalog
from .lexer import Lexer
from .parser import Parser
from .resolver import FeatureRegistry, PackageRegistry, PolicyRegistry, Resolver

__all__ = (
    "CompiledCharter",
    "compile_charter",
)


@dataclass(frozen=True, slots=True)
class CompiledCharter:
    """Validated, resolved charter ready for execution.

    This is the output of the compilation pipeline. It holds the
    original AST plus all resolved references and phase ordering.
    The mapping to Kron Graph/Operations happens at execution time
    when runtime parameters (subject_id, case_id) become available.

    Attributes:
        name: Charter name.
        version: Charter version string.
        ast: The original parsed CharterNode.
        feature_names: All vocabulary features referenced.
        schema_types: Resolved output type_name -> Python type.
        phase_order: Topologically sorted phase names per workflow.
        policy_ids: All policy IDs referenced.
        situations: Situational constraint nodes.
        roles: Role definition nodes.
    """

    name: str
    version: str
    ast: CharterNode
    feature_names: frozenset[str]
    schema_types: Mapping[str, type]  # Immutable via MappingProxyType
    phase_order: Mapping[str, tuple[str, ...]]  # Immutable via MappingProxyType
    policy_ids: frozenset[str]
    package_names: frozenset[str]
    situations: tuple[SituationNode, ...]
    roles: tuple[RoleNode, ...]

    @property
    def workflow_names(self) -> tuple[str, ...]:
        """Names of all workflows in declaration order."""
        return tuple(w.name for w in self.ast.workflows)


def compile_charter(
    source: str,
    *,
    catalog: SchemaCatalog | None = None,
    feature_registry: FeatureRegistry | None = None,
    policy_registry: PolicyRegistry | None = None,
    package_registry: PackageRegistry | None = None,
) -> CompiledCharter:
    """Compile charter source text to a validated CompiledCharter.

    Pipeline: source -> Lexer -> Parser -> Resolver -> CompiledCharter

    Args:
        source: Charter DSL source text.
        catalog: Schema catalog for output type validation.
        feature_registry: Vocabulary registry for feature validation.
        policy_registry: Policy registry for policy ID validation.
        package_registry: Package registry for vocabulary package validation.

    Returns:
        CompiledCharter with validated AST and resolved references.

    Raises:
        LexError: Tokenization failure.
        ParseError: Syntax error.
        ExceptionGroup[ResolveError]: Semantic validation failures.
    """
    # Stage 1: Lex
    tokens = Lexer(source).tokenize()

    # Stage 2: Parse
    ast = Parser(tokens).parse()

    # Stage 3: Resolve
    resolver = Resolver(
        catalog=catalog,
        feature_registry=feature_registry,
        policy_registry=policy_registry,
        package_registry=package_registry,
    )
    resolved = resolver.resolve(ast)

    # Stage 4: Build compiled charter
    return CompiledCharter(
        name=resolved.ast.name,
        version=resolved.ast.version,
        ast=resolved.ast,
        feature_names=resolved.feature_names,
        schema_types=resolved.schema_types,
        phase_order=resolved.phase_order,
        policy_ids=resolved.policy_ids,
        package_names=resolved.package_names,
        situations=resolved.ast.situations,
        roles=resolved.ast.roles,
    )
