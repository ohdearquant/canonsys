"""Vocabulary Registry - declarative feature metadata using kron Spec/Operable.

The vocabulary layer is CanonSys's core abstraction: atomic compliance operations
mapped 1:1 to regulatory requirements. This module provides:

1. Feature registration via @vocabulary decorator
2. Type-safe metadata (input/output types, regulatory basis)
3. Composition into Operables for workflow DAG planning
4. Feature discovery API (by category, pattern, regulation)

Architecture:
    @vocabulary registers metadata WITHOUT modifying the function.
    The function remains a plain async function.
    The registry enables introspection, composition, and validation.

Usage:
    from canon.enforcement.vocabulary import vocabulary, get_feature, compose_workflow

    @vocabulary(
        category="consent",
        pattern="query",
        regulatory_basis="FCRA § 1681b(b)(3)",
    )
    async def verify_consent(options: VerifyOptions, ctx: RequestContext) -> ConsentResult:
        ...

    # Discover features
    consent_features = list_features(category="consent")

    # Compose workflow
    workflow = compose_workflow("verify_consent", "create_cep", "seal_cep")
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

__all__ = [
    "FeaturePattern",
    "FeatureSpec",
    "WorkflowSpec",
    "WorkflowStep",
    "compose_workflow",
    "get_feature",
    "list_categories",
    "list_features",
    "vocabulary",
]

# Feature pattern types
FeaturePattern = Literal["query", "mutation", "requirement", "cascade"]


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """Metadata for a vocabulary feature.

    Captures the regulatory semantics of a compliance primitive:
    - What it does (name, category, pattern)
    - What it operates on (input_type, output_type)
    - Why it exists (regulatory_basis, description)
    - How it composes (dependencies)

    The actual function reference is stored for introspection.
    """

    name: str
    """Feature function name (e.g., 'verify_consent')."""

    category: str
    """Domain category (e.g., 'consent', 'evidence', 'certification')."""

    pattern: FeaturePattern
    """Execution pattern: query, mutation, requirement, or cascade."""

    func: Callable[..., Any]
    """Reference to the actual async function."""

    input_type: type | None = None
    """Primary input type (options/params dataclass)."""

    output_type: type | None = None
    """Return type (frozen dataclass result)."""

    regulatory_basis: str | None = None
    """Regulatory citation (e.g., 'FCRA § 1681b(b)(3)')."""

    description: str | None = None
    """Human-readable description (from docstring if not provided)."""

    dependencies: tuple[str, ...] = ()
    """Other features this one depends on (for DAG composition)."""

    @property
    def is_query(self) -> bool:
        """True if this is a read-only check (no side effects)."""
        return self.pattern == "query"

    @property
    def is_mutation(self) -> bool:
        """True if this modifies state."""
        return self.pattern in ("mutation", "cascade")

    @property
    def is_requirement(self) -> bool:
        """True if this is an assertion gate (raises on failure)."""
        return self.pattern == "requirement"


# =============================================================================
# Registry
# =============================================================================

_vocabulary_registry: dict[str, FeatureSpec] = {}


def vocabulary(
    category: str,
    *,
    pattern: FeaturePattern = "mutation",
    regulatory_basis: str | None = None,
    input_type: type | None = None,
    output_type: type | None = None,
    dependencies: list[str] | None = None,
) -> Callable[[Callable], Callable]:
    """Decorator to register a vocabulary feature.

    Does NOT modify the function - only registers metadata.

    Args:
        category: Domain category (consent, evidence, certification, etc.)
        pattern: Execution pattern (query, mutation, requirement, cascade)
        regulatory_basis: Legal citation this feature maps to
        input_type: Primary input type (options dataclass)
        output_type: Return type (frozen result dataclass)
        dependencies: Other features this depends on

    Usage:
        @vocabulary(
            category="consent",
            pattern="query",
            regulatory_basis="FCRA § 1681b(b)(3)",
            input_type=VerifyOptions,
            output_type=ConsentVerificationResult,
        )
        async def verify_consent_token(options, ctx):
            ...
    """

    def decorator(func: Callable) -> Callable:
        spec = FeatureSpec(
            name=func.__name__,
            category=category,
            pattern=pattern,
            func=func,
            input_type=input_type,
            output_type=output_type,
            regulatory_basis=regulatory_basis,
            description=func.__doc__,
            dependencies=tuple(dependencies or []),
        )
        _vocabulary_registry[func.__name__] = spec
        return func

    return decorator


def get_feature(name: str) -> FeatureSpec | None:
    """Get feature spec by name.

    Args:
        name: Feature function name.

    Returns:
        FeatureSpec if registered, None otherwise.
    """
    return _vocabulary_registry.get(name)


def list_features(
    category: str | None = None,
    pattern: FeaturePattern | None = None,
    regulation: str | None = None,
) -> list[FeatureSpec]:
    """List registered vocabulary features with optional filters.

    Args:
        category: Filter by domain category.
        pattern: Filter by execution pattern.
        regulation: Filter by regulatory basis (substring match).

    Returns:
        List of matching FeatureSpecs.
    """
    features = list(_vocabulary_registry.values())

    if category:
        features = [f for f in features if f.category == category]
    if pattern:
        features = [f for f in features if f.pattern == pattern]
    if regulation:
        reg_lower = regulation.lower()
        features = [
            f for f in features if f.regulatory_basis and reg_lower in f.regulatory_basis.lower()
        ]

    return features


def list_categories() -> list[str]:
    """List all registered vocabulary categories.

    Returns:
        Sorted list of unique category names.
    """
    return sorted({f.category for f in _vocabulary_registry.values()})


# =============================================================================
# Workflow Composition
# =============================================================================


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """A single step in a composed workflow.

    Attributes:
        feature: The vocabulary feature spec.
        depends_on: Indices of steps this one depends on.
    """

    feature: FeatureSpec
    depends_on: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowSpec:
    """A composed workflow as a linear sequence of vocabulary features.

    Represents a compliance workflow as an ordered DAG of features.
    Steps execute in order, respecting dependency constraints.

    Attributes:
        name: Workflow name (e.g., "fcra_adverse_action").
        steps: Ordered steps with dependency info.
        regulatory_basis: Combined regulatory citations.
    """

    name: str
    steps: tuple[WorkflowStep, ...]

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Names of features in this workflow."""
        return tuple(s.feature.name for s in self.steps)

    @property
    def regulatory_basis(self) -> tuple[str, ...]:
        """All regulatory citations covered by this workflow."""
        return tuple(s.feature.regulatory_basis for s in self.steps if s.feature.regulatory_basis)

    @property
    def categories(self) -> tuple[str, ...]:
        """Unique categories touched by this workflow."""
        seen: set[str] = set()
        result: list[str] = []
        for s in self.steps:
            if s.feature.category not in seen:
                result.append(s.feature.category)
                seen.add(s.feature.category)
        return tuple(result)

    def validate(self) -> list[str]:
        """Validate workflow composition.

        Returns:
            List of validation errors (empty if valid).
        """
        errors: list[str] = []
        for i, step in enumerate(self.steps):
            for dep_idx in step.depends_on:
                if dep_idx >= i:
                    errors.append(
                        f"Step {i} ({step.feature.name}) depends on "
                        f"step {dep_idx} which hasn't executed yet"
                    )
                if dep_idx < 0 or dep_idx >= len(self.steps):
                    errors.append(
                        f"Step {i} ({step.feature.name}) has invalid dependency index {dep_idx}"
                    )
        return errors


def compose_workflow(
    name: str,
    *feature_names: str,
) -> WorkflowSpec:
    """Compose vocabulary features into a workflow specification.

    Features execute in the order given. Dependencies are inferred
    from the feature's declared dependencies list.

    Args:
        name: Workflow name for identification.
        *feature_names: Feature names in execution order.

    Returns:
        WorkflowSpec with steps and dependency info.

    Raises:
        ValueError: If any feature is not registered.

    Example:
        workflow = compose_workflow(
            "fcra_adverse_action",
            "verify_consent_token",
            "create_cep",
            "seal_cep",
            "check_waiting_period_elapsed",
            "certify_fcra_notice",
        )
    """
    steps: list[WorkflowStep] = []
    name_to_idx: dict[str, int] = {}

    for i, feat_name in enumerate(feature_names):
        feature = get_feature(feat_name)
        if not feature:
            raise ValueError(
                f"Feature '{feat_name}' not registered. "
                f"Available: {sorted(_vocabulary_registry.keys())}"
            )

        # Resolve dependencies to step indices
        deps: list[int] = []
        for dep_name in feature.dependencies:
            if dep_name in name_to_idx:
                deps.append(name_to_idx[dep_name])

        steps.append(
            WorkflowStep(
                feature=feature,
                depends_on=tuple(deps),
            )
        )
        name_to_idx[feat_name] = i

    return WorkflowSpec(name=name, steps=tuple(steps))
