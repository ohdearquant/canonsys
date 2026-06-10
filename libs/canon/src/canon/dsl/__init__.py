"""Charter DSL — declarative compliance workflow specification.

The Charter DSL lets domain experts author compliance workflows
that compile to validated DAGs executable by Kron's
DependencyAwareExecutor.

Public API:
    compile_charter(source, catalog=...) -> CompiledCharter
    parse_charter(source) -> CharterNode  (lex + parse only)

Example:
    from canon.dsl import compile_charter, SchemaCatalog

    catalog = SchemaCatalog()
    catalog.register("canon.hr", "2026.01", "PIPReport", PIPReport)

    compiled = compile_charter(source_text, catalog=catalog)
"""

from __future__ import annotations

from .ast import (
    ActionNode,
    ArgNode,
    BuiltinRefNode,
    CertifyNode,
    CharterNode,
    EvidenceNode,
    FeatureCallNode,
    OutputNode,
    PackageRefNode,
    PhaseNode,
    PhaseRefNode,
    PolicyNode,
    PredicateNode,
    RequireNode,
    RoleNode,
    SchemaRefNode,
    SituationNode,
    WaitingPeriodNode,
    WorkflowNode,
)
from .catalog import CatalogEntry, SchemaCatalog
from .compiler import CompiledCharter, compile_charter
from .errors import (
    CharterDSLError,
    CyclicDependencyError,
    DuplicatePhaseError,
    DuplicateWorkflowError,
    InvalidRoleError,
    InvalidWaitingPeriodError,
    LexError,
    ParseError,
    ResolveError,
    UnknownFeatureError,
    UnknownPackageError,
    UnknownPhaseError,
    UnknownPolicyError,
    UnknownSchemaError,
)
from .lexer import Lexer
from .parser import Parser, parse_charter
from .resolver import PackageRegistry, ResolvedCharter, Resolver

__all__ = (
    # Compiler (primary API)
    "compile_charter",
    "CompiledCharter",
    # Parser (lex + parse only)
    "parse_charter",
    # Lexer
    "Lexer",
    # Parser
    "Parser",
    # Resolver
    "Resolver",
    "ResolvedCharter",
    # Catalog
    "SchemaCatalog",
    "CatalogEntry",
    # AST nodes
    "CharterNode",
    "WorkflowNode",
    "PhaseNode",
    "RequireNode",
    "ActionNode",
    "OutputNode",
    "CertifyNode",
    "EvidenceNode",
    "FeatureCallNode",
    "PhaseRefNode",
    "BuiltinRefNode",
    "ArgNode",
    "SituationNode",
    "PredicateNode",
    "WaitingPeriodNode",
    "RoleNode",
    "SchemaRefNode",
    "PackageRefNode",
    "PolicyNode",
    # Resolver protocols
    "PackageRegistry",
    # Errors
    "CharterDSLError",
    "LexError",
    "ParseError",
    "ResolveError",
    "UnknownFeatureError",
    "UnknownSchemaError",
    "UnknownPackageError",
    "UnknownPhaseError",
    "CyclicDependencyError",
    "UnknownPolicyError",
    "InvalidRoleError",
    "DuplicateWorkflowError",
    "DuplicatePhaseError",
    "InvalidWaitingPeriodError",
)
