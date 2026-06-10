"""Charter DSL abstract syntax tree nodes.

All nodes are frozen dataclasses with slots for immutability and
memory efficiency. The hierarchy mirrors the grammar:

    CharterNode (root)
    ├── SchemaRefNode
    ├── PolicyNode[]
    ├── TriggerNode[]          # Event trigger declarations
    ├── WorkflowNode[]
    │   └── PhaseNode[]
    │       ├── RequireNode (FeatureCallNode | PhaseRefNode | BuiltinRefNode | AwaitRefNode)
    │       ├── ActionNode (FeatureCallNode)
    │       ├── OutputNode
    │       ├── CertifyNode
    │       ├── EvidenceNode
    │       └── WhenBlockNode[]  # Inline conditional blocks
    ├── SituationNode[]
    │   ├── PredicateNode
    │   ├── WaitingPeriodNode
    │   └── RequireNode[]
    └── RoleNode[]
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    # Leaf / expression
    "ArgNode",
    "FeatureCallNode",
    "PhaseRefNode",
    "BuiltinRefNode",
    "AwaitRefNode",
    # Statement
    "RequireNode",
    "ActionNode",
    "OutputNode",
    "CertifyNode",
    "EvidenceNode",
    "AwaitNode",
    "GrantNode",
    # Block
    "PhaseNode",
    "WorkflowNode",
    "SituationNode",
    "RoleNode",
    "WhenBlockNode",
    # Support
    "SchemaRefNode",
    "PackageRefNode",
    "PolicyNode",
    "PredicateNode",
    "WaitingPeriodNode",
    "TriggerNode",
    # Root
    "CharterNode",
)


# =============================================================================
# Leaf / Expression Nodes
# =============================================================================


@dataclass(frozen=True, slots=True)
class ArgNode:
    """Function argument: positional or keyword.

    name is None for positional arguments.
    """

    name: str | None
    value: str | int | float | bool


@dataclass(frozen=True, slots=True)
class FeatureCallNode:
    """Vocabulary feature invocation: feature_name(arg1, arg2, ...)."""

    name: str
    args: tuple[ArgNode, ...]


@dataclass(frozen=True, slots=True)
class PhaseRefNode:
    """Reference to a phase result: phase_name.passed or phase_name.complete."""

    phase: str
    condition: str  # "passed" or "complete"


@dataclass(frozen=True, slots=True)
class BuiltinRefNode:
    """Reference to a builtin predicate: all_phases_passed, etc."""

    name: str


@dataclass(frozen=True, slots=True)
class AwaitRefNode:
    """Reference to an event trigger: await event_name."""

    trigger: str


@dataclass(frozen=True, slots=True)
class AwaitNode:
    """Await statement: block until external event fires.

    Standalone statement in a phase: `await event_name`
    """

    trigger: str


# =============================================================================
# Statement Nodes (within phases)
# =============================================================================


@dataclass(frozen=True, slots=True)
class RequireNode:
    """Require statement: precondition for a phase.

    ref is one of: FeatureCallNode, PhaseRefNode, BuiltinRefNode, or AwaitRefNode.
    For `require await event_name`, ref will be AwaitRefNode.
    """

    ref: FeatureCallNode | PhaseRefNode | BuiltinRefNode | AwaitRefNode


@dataclass(frozen=True, slots=True)
class ActionNode:
    """Action statement: vocabulary feature invocation in a phase."""

    call: FeatureCallNode


@dataclass(frozen=True, slots=True)
class OutputNode:
    """Output type declaration referencing a schema catalog entry."""

    type_name: str


@dataclass(frozen=True, slots=True)
class CertifyNode:
    """Certify directive (e.g., certify immutable)."""

    qualifier: str


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    """Evidence binding directive within a phase."""

    evidence_type: str


@dataclass(frozen=True, slots=True)
class GrantNode:
    """Document access grant directive within a phase.

    Declares JIT document access issued when phase activates.
    Grants auto-revoke on phase completion.

    Syntax:
        grants resume          # Phase-scoped (access while phase pending)
        grants resume for 5m   # Time-scoped (explicit TTL in minutes)

    Phase-scoped is the default and preferred pattern - access is tied
    to the assignee's pending action, not an arbitrary time window.
    """

    document_type: str
    ttl_minutes: int | None = None  # None = phase-scoped (revoke on completion)


# =============================================================================
# Block Nodes
# =============================================================================


@dataclass(frozen=True, slots=True)
class WhenBlockNode:
    """Inline conditional block within a phase.

    Allows conditional actions/requires/awaits based on predicates:
        when dispute_status == "FILED":
            await candidate_files_dispute
            require require_legal_review_complete()
            action investigate_dispute()
    """

    predicate: PredicateNode
    requires: tuple[RequireNode, ...] = ()
    actions: tuple[ActionNode, ...] = ()
    awaits: tuple[AwaitNode, ...] = ()


@dataclass(frozen=True, slots=True)
class PhaseNode:
    """Phase definition within a workflow."""

    name: str
    requires: tuple[RequireNode, ...]
    actions: tuple[ActionNode, ...]
    outputs: tuple[OutputNode, ...]
    grants: tuple[GrantNode, ...] = ()
    certify: CertifyNode | None = None
    evidence: EvidenceNode | None = None
    when_blocks: tuple[WhenBlockNode, ...] = ()
    awaits: tuple[AwaitNode, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowNode:
    """Workflow definition: ordered sequence of phases forming a DAG."""

    name: str
    phases: tuple[PhaseNode, ...]


@dataclass(frozen=True, slots=True)
class PredicateNode:
    """Conditional predicate: field operator value."""

    field: str
    operator: str  # ==, !=, >, <, >=, <=
    value: str | int | float | bool


@dataclass(frozen=True, slots=True)
class WaitingPeriodNode:
    """Waiting period range: min..max unit."""

    min_value: int
    max_value: int
    unit: str  # "days", "hours"


@dataclass(frozen=True, slots=True)
class SituationNode:
    """Situational constraint: conditional requirements."""

    predicate: PredicateNode
    waiting_period: WaitingPeriodNode | None = None
    requires: tuple[RequireNode, ...] = ()


@dataclass(frozen=True, slots=True)
class RoleNode:
    """Role definition with permitted actions."""

    name: str
    actions: tuple[str, ...]
    break_glass: bool = False
    requires_mfa: bool = True


# =============================================================================
# Support Nodes
# =============================================================================


@dataclass(frozen=True, slots=True)
class SchemaRefNode:
    """Schema catalog reference: namespace@version."""

    namespace: str  # e.g., "canon.hr"
    version: str  # e.g., "2026.01"


@dataclass(frozen=True, slots=True)
class PackageRefNode:
    """Vocabulary package reference in a charter."""

    name: str  # e.g., "consent", "certification"


@dataclass(frozen=True, slots=True)
class PolicyNode:
    """Policy reference: dotted.policy.id."""

    policy_id: str  # e.g., "employment.termination"


@dataclass(frozen=True, slots=True)
class TriggerNode:
    """Event trigger declaration.

    Triggers are external events that can activate phases via `require await`.
    """

    name: str  # e.g., "recruiter_submits_final_offer"


# =============================================================================
# Root Node
# =============================================================================


@dataclass(frozen=True, slots=True)
class CharterNode:
    """Root AST node for a complete charter document."""

    name: str
    version: str
    schemas: tuple[SchemaRefNode, ...] = ()
    packages: tuple[PackageRefNode, ...] = ()
    policies: tuple[PolicyNode, ...] = ()
    triggers: tuple[TriggerNode, ...] = ()
    workflows: tuple[WorkflowNode, ...] = ()
    situations: tuple[SituationNode, ...] = ()
    roles: tuple[RoleNode, ...] = ()
