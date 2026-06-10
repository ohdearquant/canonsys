"""Charter DSL resolver — semantic validation pass.

Validates a parsed CharterNode against:
1. Vocabulary registry (feature names exist)
2. Schema catalog (output types exist in pinned version)
3. Phase references (named phases exist in workflow)
4. Policy registry (policy IDs exist)
5. Role actions (subset of workflow action names)
6. DAG acyclicity (topological sort via Kahn's algorithm)

Usage:
    from canon.dsl.resolver import Resolver, ResolvedCharter

    resolver = Resolver(catalog=my_catalog)
    resolved = resolver.resolve(charter_ast)
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from .ast import (
    AwaitRefNode,
    BuiltinRefNode,
    CharterNode,
    FeatureCallNode,
    PhaseNode,
    PhaseRefNode,
    RequireNode,
    SituationNode,
    WorkflowNode,
)
from .catalog import SchemaCatalog
from .errors import (
    CyclicDependencyError,
    DuplicatePhaseError,
    DuplicateWorkflowError,
    InvalidGrantTTLError,
    InvalidRoleError,
    InvalidWaitingPeriodError,
    ResolveError,
    UndeclaredPhraseError,
    UnknownDocumentTypeError,
    UnknownFeatureError,
    UnknownPackageError,
    UnknownPhaseError,
    UnknownPolicyError,
    UnknownSchemaError,
    UnknownTriggerError,
)

__all__ = (
    "FeatureRegistry",
    "PackageRegistry",
    "PolicyRegistry",
    "ResolvedCharter",
    "Resolver",
)


# -----------------------------------------------------------------
# Registry protocols (dependency injection)
# -----------------------------------------------------------------


@runtime_checkable
class FeatureRegistry(Protocol):
    """Minimal interface for vocabulary feature lookup."""

    def get_feature(self, name: str) -> Any | None:
        """Return feature spec or None if unknown."""
        ...

    def get_all_feature_names(self) -> frozenset[str]:
        """Return all known feature names for suggestions."""
        ...


@runtime_checkable
class PackageRegistry(Protocol):
    """Minimal interface for vocabulary package lookup."""

    def has_package(self, name: str) -> bool:
        """Return True if package name is known."""
        ...

    def get_package_phrases(self, name: str) -> frozenset[str] | None:
        """Return set of phrase names exported by package, or None if unknown."""
        ...


@runtime_checkable
class PolicyRegistry(Protocol):
    """Minimal interface for policy lookup."""

    def has_policy(self, policy_id: str) -> bool:
        """Return True if policy_id is known."""
        ...


# -----------------------------------------------------------------
# Resolved charter
# -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResolvedCharter:
    """Validated charter with resolved references.

    Attributes:
        ast: The original parsed CharterNode.
        feature_names: Set of all feature names referenced.
        schema_types: Immutable map of output type_name -> resolved Python type.
        phase_order: Immutable map of workflow_name -> topologically sorted phases.
        policy_ids: Set of all policy IDs referenced.
    """

    ast: CharterNode
    feature_names: frozenset[str]
    schema_types: Mapping[str, type]  # Immutable via MappingProxyType
    phase_order: Mapping[str, tuple[str, ...]]  # Immutable via MappingProxyType
    policy_ids: frozenset[str]
    package_names: frozenset[str]


# -----------------------------------------------------------------
# Known builtins
# -----------------------------------------------------------------

_KNOWN_BUILTINS = frozenset(
    {
        "all_phases_passed",
        "integrity_threshold_met",
    }
)

# Known document types for JIT access grants
_KNOWN_DOCUMENT_TYPES = frozenset(
    {
        "resume",
        "cover_letter",
        "background_report",
        "offer_letter",
        "employment_contract",
        "performance_review",
        "pip_document",
        "termination_letter",
        "reference_letter",
        "id_verification",
        "tax_form",
        "benefits_enrollment",
        "nda",
        "ip_agreement",
        "handbook_acknowledgment",
    }
)

# Grant TTL constraints (in minutes)
_GRANT_TTL_MIN = 1
_GRANT_TTL_MAX = 1440  # 24 hours


# -----------------------------------------------------------------
# Resolver
# -----------------------------------------------------------------


class Resolver:
    """Semantic validator for parsed Charter ASTs.

    Accepts optional registries for dependency injection. When
    registries are not provided, the corresponding checks are
    skipped (useful for parse-only workflows and testing).
    """

    def __init__(
        self,
        catalog: SchemaCatalog | None = None,
        feature_registry: FeatureRegistry | None = None,
        policy_registry: PolicyRegistry | None = None,
        package_registry: PackageRegistry | None = None,
    ) -> None:
        self._catalog = catalog
        self._feature_registry = feature_registry
        self._policy_registry = policy_registry
        self._package_registry = package_registry

    def resolve(self, charter: CharterNode) -> ResolvedCharter:
        """Validate charter and return resolved representation.

        Collects all errors and raises ExceptionGroup if any
        validation fails.

        Raises:
            ExceptionGroup: Contains all ResolveError instances found.
        """
        errors: list[ResolveError] = []
        feature_names: set[str] = set()
        schema_types: dict[str, type] = {}
        phase_order: dict[str, tuple[str, ...]] = {}
        policy_ids: set[str] = set()
        package_names: set[str] = set()

        # 0. Collect and validate package references, build allowed phrases
        allowed_phrases: set[str] = set()
        for pkg_node in charter.packages:
            package_names.add(pkg_node.name)
            if self._package_registry is not None:
                if not self._package_registry.has_package(pkg_node.name):
                    errors.append(UnknownPackageError(pkg_node.name))
                else:
                    # Collect phrases from this package
                    pkg_phrases = self._package_registry.get_package_phrases(pkg_node.name)
                    if pkg_phrases:
                        allowed_phrases.update(pkg_phrases)

        # 1. Collect and validate policy references
        for policy_node in charter.policies:
            policy_ids.add(policy_node.policy_id)
            if self._policy_registry is not None:
                if not self._policy_registry.has_policy(policy_node.policy_id):
                    errors.append(UnknownPolicyError(policy_node.policy_id))

        # 2. Validate workflows (check for duplicate names)
        seen_workflow_names: set[str] = set()
        for workflow in charter.workflows:
            if workflow.name in seen_workflow_names:
                errors.append(DuplicateWorkflowError(workflow.name))
            seen_workflow_names.add(workflow.name)

            wf_errors, wf_features, wf_schemas, wf_order = self._resolve_workflow(
                charter, workflow, allowed_phrases, package_names
            )
            errors.extend(wf_errors)
            feature_names.update(wf_features)
            schema_types.update(wf_schemas)
            phase_order[workflow.name] = wf_order

        # 3. Validate situations (feature refs and waiting periods)
        for situation in charter.situations:
            sit_errors, sit_features = self._resolve_situation(
                situation, allowed_phrases, package_names
            )
            errors.extend(sit_errors)
            feature_names.update(sit_features)

            # Validate waiting period range
            if situation.waiting_period is not None:
                wp = situation.waiting_period
                if wp.min_value < 0:
                    errors.append(
                        InvalidWaitingPeriodError(
                            wp.min_value, wp.max_value, "min_value cannot be negative"
                        )
                    )
                elif wp.max_value < 0:
                    errors.append(
                        InvalidWaitingPeriodError(
                            wp.min_value, wp.max_value, "max_value cannot be negative"
                        )
                    )
                elif wp.min_value > wp.max_value:
                    errors.append(
                        InvalidWaitingPeriodError(
                            wp.min_value,
                            wp.max_value,
                            "min_value cannot exceed max_value",
                        )
                    )

        # 4. Validate roles
        all_action_names = self._collect_action_names(charter)
        for role in charter.roles:
            invalid = tuple(a for a in role.actions if a not in all_action_names)
            if invalid:
                errors.append(InvalidRoleError(role.name, invalid))

        if errors:
            raise ExceptionGroup(
                f"Charter '{charter.name}' has {len(errors)} resolution error(s)",
                errors,
            )

        return ResolvedCharter(
            ast=charter,
            feature_names=frozenset(feature_names),
            schema_types=MappingProxyType(schema_types),
            phase_order=MappingProxyType(phase_order),
            policy_ids=frozenset(policy_ids),
            package_names=frozenset(package_names),
        )

    # -----------------------------------------------------------------
    # Workflow resolution
    # -----------------------------------------------------------------

    def _resolve_workflow(
        self,
        charter: CharterNode,
        workflow: WorkflowNode,
        allowed_phrases: set[str],
        declared_packages: set[str],
    ) -> tuple[list[ResolveError], set[str], dict[str, type], tuple[str, ...]]:
        """Validate a single workflow.

        Returns:
            (errors, feature_names, schema_types, phase_order)
        """
        errors: list[ResolveError] = []
        feature_names: set[str] = set()
        schema_types: dict[str, type] = {}

        # Check for duplicate phase names
        seen_phase_names: set[str] = set()
        phase_names: set[str] = set()
        for phase in workflow.phases:
            if phase.name in seen_phase_names:
                errors.append(DuplicatePhaseError(phase.name, workflow.name))
            seen_phase_names.add(phase.name)
            phase_names.add(phase.name)

        # Validate each phase
        for phase in workflow.phases:
            pe, pf, ps = self._resolve_phase(
                charter,
                workflow,
                phase,
                phase_names,
                allowed_phrases,
                declared_packages,
            )
            errors.extend(pe)
            feature_names.update(pf)
            schema_types.update(ps)

        # DAG acyclicity check
        try:
            order = self._topological_sort(workflow)
        except CyclicDependencyError as e:
            errors.append(e)
            order = tuple(p.name for p in workflow.phases)

        return errors, feature_names, schema_types, order

    def _resolve_phase(
        self,
        charter: CharterNode,
        workflow: WorkflowNode,
        phase: PhaseNode,
        phase_names: set[str],
        allowed_phrases: set[str],
        declared_packages: set[str],
    ) -> tuple[list[ResolveError], set[str], dict[str, type]]:
        """Validate a single phase.

        Returns:
            (errors, feature_names, schema_types)
        """
        errors: list[ResolveError] = []
        feature_names: set[str] = set()
        schema_types: dict[str, type] = {}

        # Collect trigger names for await validation
        trigger_names = frozenset(t.name for t in charter.triggers)

        # Validate await statements (must reference declared triggers)
        for await_node in phase.awaits:
            if await_node.trigger not in trigger_names:
                errors.append(
                    UnknownTriggerError(
                        await_node.trigger,
                        declared_triggers=(tuple(sorted(trigger_names)) if trigger_names else None),
                    )
                )

        # Validate requires
        for req in phase.requires:
            req_errors, req_features = self._resolve_require(
                req,
                workflow.name,
                phase_names,
                trigger_names,
                allowed_phrases,
                declared_packages,
            )
            errors.extend(req_errors)
            feature_names.update(req_features)

        # Validate actions
        for action in phase.actions:
            act_errors, act_features = self._resolve_feature_call(
                action.call, allowed_phrases, declared_packages
            )
            errors.extend(act_errors)
            feature_names.update(act_features)

        # Validate inline when blocks
        for when_block in phase.when_blocks:
            # Validate awaits within when block
            for await_node in when_block.awaits:
                if await_node.trigger not in trigger_names:
                    errors.append(
                        UnknownTriggerError(
                            await_node.trigger,
                            declared_triggers=(
                                tuple(sorted(trigger_names)) if trigger_names else None
                            ),
                        )
                    )
            # Validate requires within when block
            for req in when_block.requires:
                req_errors, req_features = self._resolve_require(
                    req,
                    workflow.name,
                    phase_names,
                    trigger_names,
                    allowed_phrases,
                    declared_packages,
                )
                errors.extend(req_errors)
                feature_names.update(req_features)
            # Validate actions within when block
            for action in when_block.actions:
                act_errors, act_features = self._resolve_feature_call(
                    action.call, allowed_phrases, declared_packages
                )
                errors.extend(act_errors)
                feature_names.update(act_features)

        # Validate outputs against schema catalog(s)
        if charter.schemas and self._catalog is not None:
            for output in phase.outputs:
                resolved_type: type | None = None
                # Search across all declared schemas in declaration order
                for schema_ref in charter.schemas:
                    found = self._catalog.get(
                        schema_ref.namespace,
                        schema_ref.version,
                        output.type_name,
                    )
                    if found is not None:
                        resolved_type = found
                        break
                if resolved_type is not None:
                    schema_types[output.type_name] = resolved_type
                else:
                    # Report against first schema for error context
                    first = charter.schemas[0]
                    errors.append(
                        UnknownSchemaError(
                            output.type_name,
                            first.namespace,
                            first.version,
                        )
                    )

        # Validate grants (JIT document access)
        for grant in phase.grants:
            # Validate document type
            if grant.document_type not in _KNOWN_DOCUMENT_TYPES:
                errors.append(
                    UnknownDocumentTypeError(
                        grant.document_type,
                        known_types=tuple(sorted(_KNOWN_DOCUMENT_TYPES)),
                    )
                )
            # Validate TTL range (None = phase-scoped, skip validation)
            if grant.ttl_minutes is not None:
                if grant.ttl_minutes < _GRANT_TTL_MIN:
                    errors.append(
                        InvalidGrantTTLError(
                            grant.ttl_minutes,
                            f"must be at least {_GRANT_TTL_MIN} minute",
                        )
                    )
                elif grant.ttl_minutes > _GRANT_TTL_MAX:
                    errors.append(
                        InvalidGrantTTLError(
                            grant.ttl_minutes,
                            f"cannot exceed {_GRANT_TTL_MAX} minutes (24 hours)",
                        )
                    )

        return errors, feature_names, schema_types

    def _resolve_require(
        self,
        req: RequireNode,
        workflow_name: str,
        phase_names: set[str],
        trigger_names: set[str] | None = None,
        allowed_phrases: set[str] | None = None,
        declared_packages: set[str] | None = None,
    ) -> tuple[list[ResolveError], set[str]]:
        """Validate a require statement reference."""
        errors: list[ResolveError] = []
        features: set[str] = set()

        ref = req.ref
        if isinstance(ref, FeatureCallNode):
            e, f = self._resolve_feature_call(ref, allowed_phrases, declared_packages)
            errors.extend(e)
            features.update(f)
        elif isinstance(ref, PhaseRefNode):
            if ref.phase not in phase_names:
                errors.append(UnknownPhaseError(ref.phase, workflow_name))
        elif isinstance(ref, AwaitRefNode):
            # Validate trigger name if triggers are declared
            if trigger_names is not None and ref.trigger not in trigger_names:
                errors.append(
                    UnknownTriggerError(
                        ref.trigger,
                        declared_triggers=(tuple(sorted(trigger_names)) if trigger_names else None),
                    )
                )
        elif isinstance(ref, BuiltinRefNode):
            if ref.name not in _KNOWN_BUILTINS:
                # Not a known builtin — might be a feature
                if self._feature_registry is not None:
                    spec = self._feature_registry.get_feature(ref.name)
                    if spec is not None:
                        features.add(ref.name)
                    else:
                        suggestion = self._find_similar_feature(ref.name)
                        errors.append(UnknownFeatureError(ref.name, suggestion=suggestion))

        return errors, features

    def _resolve_feature_call(
        self,
        call: FeatureCallNode,
        allowed_phrases: set[str] | None = None,
        declared_packages: set[str] | None = None,
    ) -> tuple[list[ResolveError], set[str]]:
        """Validate a feature call against the vocabulary registry and package namespace.

        When allowed_phrases is provided, validates that the phrase is from a
        declared package (namespace enforcement).
        """
        errors: list[ResolveError] = []
        features: set[str] = set()

        features.add(call.name)

        # Namespace enforcement: phrase must be from declared packages
        # Only enforced when: 1) package registry exists, 2) packages are declared (allowed_phrases non-empty)
        if allowed_phrases and self._package_registry is not None:
            if call.name not in allowed_phrases:
                # Find which package contains this phrase for suggestion
                suggested_pkg = self._find_package_for_phrase(call.name)
                errors.append(
                    UndeclaredPhraseError(
                        call.name,
                        declared_packages=(
                            tuple(sorted(declared_packages)) if declared_packages else None
                        ),
                        suggested_package=suggested_pkg,
                    )
                )
                # Skip feature registry check since we've already flagged namespace issue
                return errors, features

        # Feature registry validation (phrase exists in vocabulary)
        if self._feature_registry is not None:
            spec = self._feature_registry.get_feature(call.name)
            if spec is None:
                suggestion = self._find_similar_feature(call.name)
                errors.append(UnknownFeatureError(call.name, suggestion=suggestion))

        return errors, features

    def _find_package_for_phrase(self, phrase_name: str) -> str | None:
        """Find which package exports a given phrase, for error suggestions."""
        if self._package_registry is None:
            return None

        # Check if package registry can list all packages
        try:
            # Try common package names to find one that exports this phrase
            common_packages = [
                "consent",
                "evidence",
                "certification",
                "compliance",
                "identity",
                "authorization",
                "audit",
                "policy",
                "data_protection",
                "incident",
                "deployment",
                "lifecycle",
            ]
            for pkg_name in common_packages:
                if self._package_registry.has_package(pkg_name):
                    phrases = self._package_registry.get_package_phrases(pkg_name)
                    if phrases and phrase_name in phrases:
                        return pkg_name
        except (AttributeError, NotImplementedError):
            pass

        return None

    def _find_similar_feature(self, name: str) -> str | None:
        """Find the most similar feature name for suggestions."""
        if self._feature_registry is None:
            return None

        try:
            all_names = self._feature_registry.get_all_feature_names()
        except (AttributeError, NotImplementedError):
            return None

        if not all_names:
            return None

        # Strategy 1: Exact prefix match (e.g., verify_consent → verify_consent_token)
        prefix_matches = [f for f in all_names if f.startswith(name)]
        if prefix_matches:
            return min(prefix_matches, key=len)  # Shortest match

        # Strategy 2: Common prefix (e.g., assess_eligibility → assess_control_coverage)
        name_parts = name.split("_")
        if name_parts:
            prefix = name_parts[0] + "_"
            prefix_matches = [f for f in all_names if f.startswith(prefix)]
            if prefix_matches:
                # Return the one with the most similar length
                return min(prefix_matches, key=lambda f: abs(len(f) - len(name)))

        # Strategy 3: Substring match
        for feature in sorted(all_names):
            if name in feature or feature in name:
                return feature

        return None

    def _resolve_situation(
        self,
        situation: SituationNode,
        allowed_phrases: set[str] | None = None,
        declared_packages: set[str] | None = None,
    ) -> tuple[list[ResolveError], set[str]]:
        """Validate feature references in situation requires."""
        errors: list[ResolveError] = []
        features: set[str] = set()

        for req in situation.requires:
            ref = req.ref
            if isinstance(ref, FeatureCallNode):
                e, f = self._resolve_feature_call(ref, allowed_phrases, declared_packages)
                errors.extend(e)
                features.update(f)
            elif isinstance(ref, BuiltinRefNode):
                if ref.name not in _KNOWN_BUILTINS:
                    if self._feature_registry is not None:
                        spec = self._feature_registry.get_feature(ref.name)
                        if spec is not None:
                            features.add(ref.name)
                        else:
                            suggestion = self._find_similar_feature(ref.name)
                            errors.append(UnknownFeatureError(ref.name, suggestion=suggestion))

        return errors, features

    # -----------------------------------------------------------------
    # DAG acyclicity (Kahn's algorithm)
    # -----------------------------------------------------------------

    def _topological_sort(
        self,
        workflow: WorkflowNode,
    ) -> tuple[str, ...]:
        """Topologically sort phases by their require dependencies.

        Uses Kahn's algorithm. Phase refs (phase.passed, phase.complete)
        define edges in the dependency graph.

        Raises:
            CyclicDependencyError: If the dependency graph has a cycle.
        """
        # Build adjacency list
        graph: dict[str, set[str]] = {p.name: set() for p in workflow.phases}
        in_degree: dict[str, int] = {p.name: 0 for p in workflow.phases}

        for phase in workflow.phases:
            for req in phase.requires:
                if isinstance(req.ref, PhaseRefNode):
                    dep = req.ref.phase
                    if dep in graph:
                        graph[dep].add(phase.name)
                        in_degree[phase.name] += 1

        # Kahn's algorithm
        queue: deque[str] = deque(name for name, degree in in_degree.items() if degree == 0)
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in sorted(graph[node]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(graph):
            # Find the cycle for error reporting
            remaining = {n for n, d in in_degree.items() if d > 0}
            cycle = self._find_cycle(graph, remaining)
            raise CyclicDependencyError(cycle)

        return tuple(order)

    @staticmethod
    def _find_cycle(
        graph: dict[str, set[str]],
        remaining: set[str],
    ) -> tuple[str, ...]:
        """Find a cycle in the remaining nodes for error reporting."""
        # Simple DFS cycle detection
        visited: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()

        def dfs(node: str) -> tuple[str, ...] | None:
            if node in path_set:
                # Found cycle — extract it
                idx = path.index(node)
                return tuple(path[idx:]) + (node,)
            if node in visited:
                return None
            visited.add(node)
            path.append(node)
            path_set.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor in remaining:
                    result = dfs(neighbor)
                    if result is not None:
                        return result
            path.pop()
            path_set.discard(node)
            return None

        for start in remaining:
            result = dfs(start)
            if result is not None:
                return result

        # Fallback: just return remaining as the "cycle"
        return tuple(sorted(remaining))

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _collect_action_names(charter: CharterNode) -> set[str]:
        """Collect all action feature names from all workflows."""
        names: set[str] = set()
        for workflow in charter.workflows:
            for phase in workflow.phases:
                for action in phase.actions:
                    names.add(action.call.name)
                # Also collect actions from inline when blocks
                for when_block in phase.when_blocks:
                    for action in when_block.actions:
                        names.add(action.call.name)
        return names
