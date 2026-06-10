"""Charter Runtime Engine - orchestrates compiled charter execution.

The runtime engine manages phase lifecycle, evaluates dependencies,
cascades completions, and enforces compliance gates.

Modules:
    phase_state: Phase state machine and transitions
    conditions: Predicate evaluation for when_blocks and situations
    grants: JIT document access grant lifecycle
    evidence: Automatic evidence recording
    inbox: User inbox derivation
    workflow: Workflow lifecycle operations
    registry: Compiled charter cache
    roles: Role MFA and break_glass enforcement

Public API:
    # Phase state
    PhaseState: Phase lifecycle states enum
    is_valid_transition: Validate state transitions
    InvalidPhaseTransition: Exception for invalid transitions

    # Conditions
    evaluate_predicate: Evaluate a predicate against runtime context
    evaluate_when_block: Evaluate a when_block's predicate
    evaluate_when_blocks: Evaluate all when_blocks for a phase
    evaluate_situations: Evaluate all situations against context
    ConditionResult: Result of evaluating a single predicate
    WhenBlockResult: Result of evaluating a when_block
    SituationOverrides: Aggregated result of situation evaluation

    # Grants
    create_phase_grant: Create document access grant for a phase
    revoke_phase_grants: Revoke all grants for a phase
    transfer_phase_grants: Transfer grants to another user
    get_active_grants: Get active grants for a run

    # Evidence
    record_phase_evidence: Record evidence for phase events
    record_grant_evidence: Record evidence for grant events
    record_workflow_evidence: Record evidence for workflow events
    EvidenceEventType: Types of events that generate evidence

    # Inbox
    get_user_inbox: Get all pending phases for a user
    get_inbox_count: Get count of pending phases
    get_inbox_by_role: Get pending phases for a role
    get_overdue_phases: Get overdue phases for monitoring

    # Workflow
    start_workflow: Start a new charter workflow
    complete_charter_run: Mark a charter run as completed
    cancel_charter_run: Cancel an active charter run
    get_run_status: Get current status of a charter run

    # Registry
    get_compiled_charter: Get compiled charter from registry
    register_charter: Register a pre-compiled charter
    CharterRegistry: Thread-safe registry class

Example:
    from canon.runtime import (
        start_workflow, get_user_inbox, complete_charter_run,
        create_phase_grant, revoke_phase_grants,
        record_phase_evidence, EvidenceEventType,
        PhaseState, is_valid_transition,
    )

    # Start a new workflow
    run_id = await start_workflow(
        charter_id=charter_id,
        subject_id=person_id,
        related_entity_type="exception_offer",
        related_entity_id=offer_id,
        workflow_name="approval_workflow",
        initiated_by_id=user_id,
        tenant_id=tenant_id,
        conn=conn,
    )

    # Get user's pending phases
    inbox = await get_user_inbox(user_id, tenant_id, conn)

    # Create grant when phase activates
    result = await create_phase_grant(
        run_id=run_id,
        phase_name="hm_approval",
        grant=grant_node,
        grantee_id=user_id,
        subject_id=candidate_id,
        tenant_id=tenant_id,
        conn=conn,
    )

    # Record phase completion evidence
    await record_phase_evidence(
        run_id=run_id,
        phase_name="hm_approval",
        event_type=EvidenceEventType.PHASE_COMPLETED,
        actor_id=user_id,
        tenant_id=tenant_id,
        subject_id=candidate_id,
        data={"action": "approve"},
        conn=conn,
    )

    # Revoke grants on phase completion
    await revoke_phase_grants(
        run_id=run_id,
        phase_name="hm_approval",
        user_id=user_id,
        reason="Phase completed",
        conn=conn,
    )
"""

# Phase state machine
# Cascade engine (Phase 1)
from .cascade import (
    CascadeResult,
    activate_phase,
    find_downstream_phases,
    on_phase_completed,
    on_phase_failed,
)

# Condition evaluation (when_blocks, situations)
from .conditions import (
    ConditionResult,
    SituationOverrides,
    WhenBlockResult,
    evaluate_predicate,
    evaluate_situations,
    evaluate_when_block,
    evaluate_when_blocks,
)

# Evidence recording
from .evidence import (
    EvidenceEventType,
    EvidenceResult,
    record_grant_evidence,
    record_phase_evidence,
    record_workflow_evidence,
)

# Grant lifecycle
from .grants import (
    AccessCheckResult,
    GrantResult,
    check_document_access,
    create_phase_grant,
    document_type_to_purpose,
    get_active_grants,
    record_document_access,
    revoke_phase_grants,
    transfer_phase_grants,
)

# Inbox
from .inbox import (
    OVERDUE_DAYS,
    PRIORITY_DAYS,
    InboxItem,
    get_inbox_by_role,
    get_inbox_count,
    get_overdue_phases,
    get_user_inbox,
)
from .phase_state import (
    PHASE_TRANSITIONS,
    InvalidPhaseTransition,
    PhaseState,
    get_terminal_states,
    is_valid_transition,
)

# Charter registry
from .registry import (
    CharterNotFoundError,
    CharterRegistry,
    get_compiled_charter,
    get_registry,
    register_charter,
)

# Require evaluation (Phase 1)
from .require_eval import RequireResult, evaluate_requires, evaluate_single_require

# Role enforcement
from .roles import (
    BreakGlassRequiredError,
    MFARequiredError,
    RoleCheckResult,
    enforce_role_requirements,
    find_role_for_phase,
    verify_role_requirements,
)

# Trigger firing (await directives)
from .trigger import (
    TriggerNotFoundError,
    TriggerResult,
    fire_trigger,
    has_trigger_fired,
)

# Visualization
from .visualization import (
    GraphEdge,
    GraphNode,
    WorkflowGraph,
    build_workflow_graph,
    get_workflow_graph,
)

# Workflow lifecycle
from .workflow import (
    WorkflowAlreadyActiveError,
    WorkflowNotFoundError,
    cancel_charter_run,
    complete_charter_run,
    get_run_status,
    is_workflow_complete,
    start_workflow,
)

__all__ = (
    # Phase state machine
    "PhaseState",
    "PHASE_TRANSITIONS",
    "is_valid_transition",
    "get_terminal_states",
    "InvalidPhaseTransition",
    # Require evaluation (Phase 1)
    "RequireResult",
    "evaluate_requires",
    "evaluate_single_require",
    # Conditions (when_blocks, situations)
    "ConditionResult",
    "WhenBlockResult",
    "SituationOverrides",
    "evaluate_predicate",
    "evaluate_when_block",
    "evaluate_when_blocks",
    "evaluate_situations",
    # Cascade engine (Phase 1)
    "CascadeResult",
    "on_phase_completed",
    "on_phase_failed",
    "activate_phase",
    "find_downstream_phases",
    # Grants
    "GrantResult",
    "AccessCheckResult",
    "check_document_access",
    "record_document_access",
    "create_phase_grant",
    "revoke_phase_grants",
    "transfer_phase_grants",
    "get_active_grants",
    "document_type_to_purpose",
    # Evidence
    "EvidenceEventType",
    "EvidenceResult",
    "record_phase_evidence",
    "record_grant_evidence",
    "record_workflow_evidence",
    # Inbox
    "InboxItem",
    "get_user_inbox",
    "get_inbox_count",
    "get_inbox_by_role",
    "get_overdue_phases",
    "OVERDUE_DAYS",
    "PRIORITY_DAYS",
    # Workflow
    "start_workflow",
    "complete_charter_run",
    "cancel_charter_run",
    "get_run_status",
    "is_workflow_complete",
    "WorkflowNotFoundError",
    "WorkflowAlreadyActiveError",
    # Triggers
    "TriggerResult",
    "TriggerNotFoundError",
    "fire_trigger",
    "has_trigger_fired",
    # Roles
    "RoleCheckResult",
    "MFARequiredError",
    "BreakGlassRequiredError",
    "find_role_for_phase",
    "verify_role_requirements",
    "enforce_role_requirements",
    # Registry
    "get_compiled_charter",
    "get_registry",
    "register_charter",
    "CharterRegistry",
    "CharterNotFoundError",
    # Visualization
    "GraphNode",
    "GraphEdge",
    "WorkflowGraph",
    "build_workflow_graph",
    "get_workflow_graph",
)
