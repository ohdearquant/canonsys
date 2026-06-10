"""PolicyResolver - determines which policies apply to a given context.

The resolver implements a 7-stage pipeline:
1. Context Extraction - tenant, jurisdiction, action, subject
2. charter Lookup - get tenant's governance document
3. Policy Filtering - filter by jurisdiction and action
4. Effective Dating - filter by effective_from/until
5. Precedence Resolution - specific > general, newer > older
6. Dependency Check - prerequisites, mutual exclusions
7. Batch Preparation - ordered list for OPA evaluation
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from canon.enforcement.policy import EnforcementLevel
from kron.utils import now_utc

from .engine import ResolvedPolicy

if TYPE_CHECKING:
    from canon.entities.charter import Charter
    from canon.entities.policy import PolicyAdapter, PolicyDefinition


@dataclass(frozen=True, slots=True)
class ResolutionContext:
    """Context for policy resolution.

    Contains everything needed to determine which policies apply.

    Attributes:
        tenant_id: Tenant identifier
        action: Action being performed (e.g., "adverse_action")
        jurisdictions: Applicable jurisdictions (e.g., ["US-NYC", "US-NY", "US"])
        subject_id: Subject of the action (optional)
        timestamp: When resolution is happening (for effective dating)
        metadata: Additional context for resolution
    """

    tenant_id: UUID
    action: str
    jurisdictions: tuple[str, ...] = ()
    subject_id: UUID | None = None
    timestamp: datetime = field(default_factory=now_utc)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PolicyIndexEntry:
    """Entry in the policy index (Two-Key binding).

    Combines PolicyDefinition (Legal Key) + PolicyAdapter (Engineering Key)
    into a single resolution unit.

    Attributes:
        policy_id: Unique identifier
        rego_package: Rego package path
        enforcement: Enforcement level
        authority: Policy authority (STATUTORY, REGULATORY, etc.)
        jurisdictions: Where this policy applies
        actions: Which actions trigger this policy
        effective_from: When policy becomes effective
        effective_until: When policy expires (None = forever)
        legal_citation: Legal citation text
        regulation_url: URL to regulation
        priority: Resolution priority (higher = more specific)
        prerequisites: Policy IDs that must pass first
        excludes: Mutually exclusive policy IDs
    """

    policy_id: str
    rego_package: str
    enforcement: EnforcementLevel = EnforcementLevel.HARD_MANDATORY
    authority: str = "INTERNAL"
    jurisdictions: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    legal_citation: str | None = None
    regulation_url: str | None = None
    priority: int = 0
    prerequisites: tuple[str, ...] = ()
    excludes: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)

    def is_effective(self, at: datetime) -> bool:
        """Check if policy is effective at given time."""
        if self.effective_from and at < self.effective_from:
            return False
        if self.effective_until and at > self.effective_until:
            return False
        return True

    def applies_to_jurisdiction(self, jurisdictions: Sequence[str]) -> bool:
        """Check if policy applies to any of the given jurisdictions."""
        if not self.jurisdictions:
            # No jurisdiction restriction = applies everywhere
            return True
        return any(j in self.jurisdictions for j in jurisdictions)

    def applies_to_action(self, action: str) -> bool:
        """Check if policy applies to given action."""
        if not self.actions:
            # No action restriction = applies to all actions
            return True
        return action in self.actions

    def to_resolved_policy(self) -> ResolvedPolicy:
        """Convert to ResolvedPolicy for engine evaluation."""
        return ResolvedPolicy(
            policy_id=self.policy_id,
            rego_package=self.rego_package,
            enforcement=self.enforcement,
            legal_citation=self.legal_citation,
            regulation_url=self.regulation_url,
            parameters=self.parameters,
        )


class PolicyIndex:
    """In-memory policy index for fast resolution.

    Built from PolicyDefinition + PolicyAdapter pairs.
    Cached per policy_library_hash.
    """

    def __init__(self) -> None:
        self._entries: dict[str, PolicyIndexEntry] = {}
        self._by_jurisdiction: dict[str, list[str]] = {}
        self._by_action: dict[str, list[str]] = {}

    def add(self, entry: PolicyIndexEntry) -> None:
        """Add entry to index."""
        self._entries[entry.policy_id] = entry

        # Index by jurisdiction
        for j in entry.jurisdictions:
            if j not in self._by_jurisdiction:
                self._by_jurisdiction[j] = []
            self._by_jurisdiction[j].append(entry.policy_id)

        # Index by action
        for a in entry.actions:
            if a not in self._by_action:
                self._by_action[a] = []
            self._by_action[a].append(entry.policy_id)

    def get(self, policy_id: str) -> PolicyIndexEntry | None:
        """Get entry by ID."""
        return self._entries.get(policy_id)

    def all_entries(self) -> list[PolicyIndexEntry]:
        """Get all entries."""
        return list(self._entries.values())

    def entries_for_jurisdiction(self, jurisdiction: str) -> list[PolicyIndexEntry]:
        """Get entries applicable to a jurisdiction."""
        policy_ids = self._by_jurisdiction.get(jurisdiction, [])
        return [self._entries[pid] for pid in policy_ids if pid in self._entries]

    def entries_for_action(self, action: str) -> list[PolicyIndexEntry]:
        """Get entries applicable to an action."""
        policy_ids = self._by_action.get(action, [])
        return [self._entries[pid] for pid in policy_ids if pid in self._entries]

    @classmethod
    def from_definitions(
        cls,
        definitions: list[PolicyDefinition],
        adapters: dict[str, PolicyAdapter],
    ) -> PolicyIndex:
        """Build index from PolicyDefinitions and PolicyAdapters."""
        index = cls()

        for defn in definitions:
            # Use policy_id (string) not id (UUID) for lookup and key
            # policy_id is stable cross-environment, used in charter
            adapter = adapters.get(defn.policy_id)
            if not adapter:
                continue

            entry = PolicyIndexEntry(
                policy_id=defn.policy_id,
                rego_package=(
                    adapter.rego_package
                    if hasattr(adapter, "rego_package")
                    else f"canon.{defn.policy_id}"
                ),
                enforcement=_parse_enforcement(getattr(defn, "enforcement", None)),
                authority=getattr(defn, "authority", "INTERNAL"),
                jurisdictions=tuple(getattr(defn, "jurisdictions", [])),
                actions=tuple(getattr(defn, "actions", [])),
                effective_from=getattr(defn, "effective_from", None),
                effective_until=getattr(defn, "effective_until", None),
                legal_citation=getattr(defn, "legal_citation", None),
                regulation_url=getattr(defn, "regulation_url", None),
                priority=getattr(defn, "priority", 0),
                prerequisites=tuple(getattr(adapter, "prerequisites", [])),
                excludes=tuple(getattr(adapter, "excludes", [])),
                parameters=getattr(adapter, "parameters", {}),
            )
            index.add(entry)

        return index


def _parse_enforcement(value: str | None) -> EnforcementLevel:
    """Parse enforcement level from string."""
    if not value:
        return EnforcementLevel.HARD_MANDATORY
    value = value.upper().replace("-", "_")
    try:
        return EnforcementLevel(value.lower())
    except ValueError:
        return EnforcementLevel.HARD_MANDATORY


class PolicyResolver:
    """Determines which policies apply to a given context.

    Implements the 7-stage resolution pipeline.

    Usage:
        resolver = PolicyResolver(index)
        policies = resolver.resolve(context)
        # policies is ordered list of ResolvedPolicy
    """

    def __init__(
        self,
        index: PolicyIndex,
        charter: Charter | None = None,
    ):
        """Initialize resolver.

        Args:
            index: Policy index for lookups
            charter: Optional tenant charter for overrides
        """
        self._index = index
        self._charter = charter

    def resolve(self, ctx: ResolutionContext) -> list[ResolvedPolicy]:
        """Resolve which policies apply to context.

        Returns ordered list of ResolvedPolicy ready for evaluation.
        """
        # Stage 1: Get all candidate entries
        candidates = self._get_candidates(ctx)

        # Stage 2: Filter by jurisdiction
        candidates = [e for e in candidates if e.applies_to_jurisdiction(ctx.jurisdictions)]

        # Stage 3: Filter by action
        candidates = [e for e in candidates if e.applies_to_action(ctx.action)]

        # Stage 4: Filter by effective dating
        candidates = [e for e in candidates if e.is_effective(ctx.timestamp)]

        # Stage 5: Apply charter overrides
        candidates = self._apply_charter(candidates, ctx)

        # Stage 6: Resolve precedence and dependencies
        candidates = self._resolve_precedence(candidates, ctx)

        # Stage 7: Convert to ResolvedPolicy and order
        policies = [e.to_resolved_policy() for e in candidates]

        return policies

    def _get_candidates(self, ctx: ResolutionContext) -> list[PolicyIndexEntry]:
        """Get initial candidate policies."""
        # Start with all entries
        # Could optimize by using indexes
        return self._index.all_entries()

    def _apply_charter(
        self,
        entries: list[PolicyIndexEntry],
        ctx: ResolutionContext,
    ) -> list[PolicyIndexEntry]:
        """Apply charter overrides to entries.

        The charter:
        1. Whitelists which policies are active (policy_ids)
        2. Can override enforcement levels via constraints
        3. Can add parameters via constraints
        """
        if not self._charter:
            return entries

        # Check if charter is effective
        if not self._charter.is_effective(ctx.timestamp):
            return entries

        # Stage 1: Filter to only policies enabled in charter
        active_policy_ids = set(self._charter.policy_ids)
        if active_policy_ids:
            entries = [e for e in entries if e.policy_id in active_policy_ids]

        # Stage 2: Apply constraint overrides (filters out disabled entries)
        constraint_overrides = self._build_constraint_overrides()
        if constraint_overrides:
            filtered: list[PolicyIndexEntry] = []
            for entry in entries:
                result = self._apply_constraint_to_entry(entry, constraint_overrides)
                if result is not None:  # Filter disabled entries (B2.1 fix)
                    filtered.append(result)
            entries = filtered

        return entries

    def _build_constraint_overrides(self) -> dict[str, dict[str, Any]]:
        """Build lookup of policy_id -> constraint overrides."""
        if not self._charter:
            return {}

        overrides: dict[str, dict[str, Any]] = {}

        for constraint in self._charter.constraints:
            # Constraint can reference a policy_id to override
            policy_id = constraint.get("policy_id")
            if not policy_id:
                continue

            if policy_id not in overrides:
                overrides[policy_id] = {}

            # Merge override settings
            if "enforcement" in constraint:
                overrides[policy_id]["enforcement"] = constraint["enforcement"]
            if "parameters" in constraint:
                overrides[policy_id].setdefault("parameters", {}).update(constraint["parameters"])
            if "disabled" in constraint:
                overrides[policy_id]["disabled"] = constraint["disabled"]

        return overrides

    def _apply_constraint_to_entry(
        self,
        entry: PolicyIndexEntry,
        overrides: dict[str, dict[str, Any]],
    ) -> PolicyIndexEntry | None:
        """Apply constraint overrides to a single entry.

        Returns None if the entry is disabled (should be filtered out).
        """
        override = overrides.get(entry.policy_id)
        if not override:
            return entry

        # Filter disabled policies immediately (B2.1 fix)
        if override.get("disabled"):
            return None

        # Build new entry with overrides
        new_enforcement = entry.enforcement
        if "enforcement" in override:
            new_enforcement = _parse_enforcement(override["enforcement"])

        new_params = dict(entry.parameters)
        if "parameters" in override:
            new_params.update(override["parameters"])

        # Create new entry with overrides (dataclass is frozen)
        return PolicyIndexEntry(
            policy_id=entry.policy_id,
            rego_package=entry.rego_package,
            enforcement=new_enforcement,
            authority=entry.authority,
            jurisdictions=entry.jurisdictions,
            actions=entry.actions,
            effective_from=entry.effective_from,
            effective_until=entry.effective_until,
            legal_citation=entry.legal_citation,
            regulation_url=entry.regulation_url,
            priority=entry.priority,
            prerequisites=entry.prerequisites,
            excludes=entry.excludes,
            parameters=new_params,
        )

    def _compute_specificity(
        self,
        entry: PolicyIndexEntry,
        ctx: ResolutionContext,
    ) -> tuple[int, int, float]:
        """Compute specificity score for sorting.

        Returns tuple for sorting (higher = more specific):
        - jurisdiction_score: based on position in context's jurisdiction list
        - action_score: 1 if explicit action match, 0 if wildcard
        - recency: timestamp for tiebreaking (newer = higher)

        Context jurisdictions are ordered most-specific-first (e.g., US-NYC, US-NY, US).
        A policy matching US-NYC gets higher score than one matching US-NY.
        Score = (len(ctx_jurisdictions) - position) for best match.
        """
        # Jurisdiction specificity: score based on position in context's ordered list
        # Context jurisdictions are ordered most-specific-first (e.g., US-NYC, US-NY, US)
        # A policy matching earlier position = more specific
        jurisdiction_score = 0
        if entry.jurisdictions and ctx.jurisdictions:
            num_ctx_jurisdictions = len(ctx.jurisdictions)
            for policy_j in entry.jurisdictions:
                for idx, ctx_j in enumerate(ctx.jurisdictions):
                    # Exact match: score based on position
                    if ctx_j == policy_j:
                        score = num_ctx_jurisdictions - idx
                        jurisdiction_score = max(jurisdiction_score, score)
                        break  # Found best match for this policy_j
                    # Policy more specific than context (e.g., policy=US-NYC-MANHATTAN, ctx=US-NYC)
                    # Treat as matching at context's level
                    if policy_j.startswith(f"{ctx_j}-"):
                        score = num_ctx_jurisdictions - idx
                        jurisdiction_score = max(jurisdiction_score, score)
                        break
        # If no jurisdictions specified, policy applies everywhere (score = 0)

        # Action specificity: explicit match > wildcard
        action_score = 1 if entry.actions and ctx.action in entry.actions else 0

        # Recency: newer effective_from = higher score (for tiebreaking)
        recency = entry.effective_from.timestamp() if entry.effective_from else 0.0

        return (jurisdiction_score, action_score, recency)

    def _resolve_precedence(
        self,
        entries: list[PolicyIndexEntry],
        ctx: ResolutionContext,
    ) -> list[PolicyIndexEntry]:
        """Resolve precedence and remove conflicts."""
        if not entries:
            return entries

        # Sort by priority (higher first), then by context-aware specificity
        entries = sorted(
            entries,
            key=lambda e: (
                -e.priority,
                *[-x for x in self._compute_specificity(e, ctx)],
            ),
        )

        # Remove mutually exclusive policies (keep higher priority)
        seen_ids: set[str] = set()
        excluded_ids: set[str] = set()
        result: list[PolicyIndexEntry] = []

        for entry in entries:
            if entry.policy_id in excluded_ids:
                continue

            result.append(entry)
            seen_ids.add(entry.policy_id)

            # Mark excluded policies
            for exc in entry.excludes:
                if exc not in seen_ids:
                    excluded_ids.add(exc)

        # Topological sort by prerequisites
        result = self._topological_sort(result)

        return result

    def _topological_sort(
        self,
        entries: list[PolicyIndexEntry],
    ) -> list[PolicyIndexEntry]:
        """Sort entries by prerequisites (dependencies first)."""
        entry_map = {e.policy_id: e for e in entries}
        included_ids = set(entry_map.keys())

        # Build adjacency list
        # If A has prerequisite B, B must come before A
        in_degree: dict[str, int] = {e.policy_id: 0 for e in entries}
        dependents: dict[str, list[str]] = {e.policy_id: [] for e in entries}

        for entry in entries:
            for prereq in entry.prerequisites:
                if prereq in included_ids:
                    in_degree[entry.policy_id] += 1
                    dependents[prereq].append(entry.policy_id)

        # Kahn's algorithm
        result: list[PolicyIndexEntry] = []
        queue = [pid for pid, deg in in_degree.items() if deg == 0]

        while queue:
            pid = queue.pop(0)
            result.append(entry_map[pid])

            for dep in dependents[pid]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        # If we didn't process all entries, there's a cycle
        # Fall back to original order
        if len(result) != len(entries):
            return entries

        return result


__all__ = [
    "PolicyIndex",
    "PolicyIndexEntry",
    "PolicyResolver",
    "ResolutionContext",
]
